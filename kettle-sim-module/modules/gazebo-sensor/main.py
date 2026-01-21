#!/usr/bin/env python3
"""
Viam module that bridges Gazebo contact sensors to Viam's sensor API.

This module:
- Subscribes to Gazebo contact sensor topics
- Provides force readings based on contact events
- Supports both force plate and kettle contact sensors
- Can fall back to mock data if contact sensing isn't available
"""

import asyncio
import time
from threading import Lock
from typing import Any, Dict, List, Mapping, Optional

from viam.components.sensor import Sensor
from viam.logging import getLogger
from viam.module.module import Module
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.resource.types import Model, ModelFamily

# Gazebo transport imports
try:
    from gz.transport13 import Node
    from gz.msgs10.contacts_pb2 import Contacts
    GZ_AVAILABLE = True
except ImportError:
    GZ_AVAILABLE = False
    print("WARNING: gz-transport13 not available.")

LOGGER = getLogger(__name__)


class GazeboContactSensor(Sensor):
    """
    A Viam sensor that reads contact/force data from Gazebo.

    Can be configured to read from:
    - Force plate contact sensor (detects kettle placement)
    - Kettle contact sensor (detects contact with gripper/table)

    If Gazebo contact data isn't available, can fall back to mock mode.
    """

    MODEL = Model(ModelFamily("viam-labs", "sensor"), "gazebo-contact")

    def __init__(self, name: str):
        super().__init__(name)
        self._node: Optional[Any] = None
        self._topic: str = "/force_plate/contact"
        self._use_mock: bool = False
        self._lock = Lock()

        # Contact state
        self._in_contact: bool = False
        self._contact_force: float = 0.0
        self._contact_count: int = 0
        self._last_contact_time: float = 0.0

        # Capture state (for cycle testing)
        self._capturing: bool = False
        self._capture_samples: List[Dict[str, Any]] = []
        self._capture_start_time: float = 0.0
        self._trial_id: str = ""
        self._cycle_count: int = 0

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> "GazeboContactSensor":
        """Create a new GazeboContactSensor instance."""
        sensor = cls(config.name)
        sensor.reconfigure(config, dependencies)
        return sensor

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> List[str]:
        """Validate the component configuration."""
        errors = []
        attrs = config.attributes.fields
        if "topic" not in attrs and "use_mock" not in attrs:
            # At least one must be specified
            pass  # Will use defaults
        return errors

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> None:
        """Reconfigure the sensor with new settings."""
        attrs = config.attributes.fields

        if "topic" in attrs:
            self._topic = attrs["topic"].string_value
        if "use_mock" in attrs:
            self._use_mock = attrs["use_mock"].bool_value

        if not self._use_mock:
            self._setup_subscription()
        else:
            LOGGER.info(f"GazeboContactSensor '{self.name}' running in mock mode")

        LOGGER.info(f"Configured GazeboContactSensor '{self.name}' on topic: {self._topic}")

    def _setup_subscription(self) -> None:
        """Subscribe to the Gazebo contact sensor topic."""
        if not GZ_AVAILABLE:
            LOGGER.warning("gz-transport not available, using mock mode")
            self._use_mock = True
            return

        if self._node is None:
            self._node = Node()

        def callback(msg: Contacts) -> None:
            """Called when contact data is received."""
            with self._lock:
                if msg.contact:
                    # Contact detected
                    self._in_contact = True
                    self._contact_count = len(msg.contact)
                    self._last_contact_time = time.time()

                    # Sum up forces from all contacts
                    total_force = 0.0
                    for contact in msg.contact:
                        for wrench in contact.wrench:
                            # Magnitude of force vector
                            fx = wrench.body_1_wrench.force.x
                            fy = wrench.body_1_wrench.force.y
                            fz = wrench.body_1_wrench.force.z
                            force_mag = (fx**2 + fy**2 + fz**2) ** 0.5
                            total_force += force_mag
                    self._contact_force = total_force

                    # If capturing, record sample
                    if self._capturing:
                        self._capture_samples.append({
                            "timestamp": time.time() - self._capture_start_time,
                            "force": total_force,
                            "contact_count": self._contact_count,
                        })
                else:
                    self._in_contact = False
                    self._contact_force = 0.0
                    self._contact_count = 0

        success = self._node.subscribe(Contacts, self._topic, callback)
        if success:
            LOGGER.info(f"Subscribed to contact topic: {self._topic}")
        else:
            LOGGER.warning(f"Failed to subscribe to {self._topic}, using mock mode")
            self._use_mock = True

    async def get_readings(
        self,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Mapping[str, Any]:
        """Get current sensor readings."""
        with self._lock:
            if self._use_mock:
                # Return mock data
                return {
                    "in_contact": False,
                    "force_n": 0.0,
                    "contact_count": 0,
                    "mock": True,
                    "capturing": self._capturing,
                    "trial_id": self._trial_id,
                    "cycle_count": self._cycle_count,
                }

            return {
                "in_contact": self._in_contact,
                "force_n": self._contact_force,
                "contact_count": self._contact_count,
                "last_contact_age_s": time.time() - self._last_contact_time if self._last_contact_time > 0 else -1,
                "capturing": self._capturing,
                "trial_id": self._trial_id,
                "cycle_count": self._cycle_count,
                "samples_captured": len(self._capture_samples),
            }

    async def do_command(
        self,
        command: Mapping[str, Any],
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Mapping[str, Any]:
        """Handle custom commands for capture control."""
        cmd = command.get("command", "")

        if cmd == "start_capture":
            trial_id = command.get("trial_id", "unknown")
            cycle_count = command.get("cycle_count", 0)

            with self._lock:
                self._capturing = True
                self._capture_samples = []
                self._capture_start_time = time.time()
                self._trial_id = trial_id
                self._cycle_count = cycle_count

            LOGGER.info(f"Started capture: trial={trial_id}, cycle={cycle_count}")
            return {
                "status": "capturing",
                "trial_id": trial_id,
                "cycle_count": cycle_count,
            }

        elif cmd == "end_capture":
            with self._lock:
                self._capturing = False
                samples = self._capture_samples.copy()

                # Calculate statistics
                if samples:
                    forces = [s["force_n"] if "force_n" in s else s.get("force", 0) for s in samples]
                    max_force = max(forces) if forces else 0
                    avg_force = sum(forces) / len(forces) if forces else 0
                    contact_detected = any(s.get("in_contact", s.get("contact_count", 0) > 0) for s in samples)
                else:
                    max_force = 0
                    avg_force = 0
                    contact_detected = False

            LOGGER.info(f"Ended capture: {len(samples)} samples, max_force={max_force:.2f}N")
            return {
                "status": "complete",
                "trial_id": self._trial_id,
                "cycle_count": self._cycle_count,
                "sample_count": len(samples),
                "max_force_n": max_force,
                "avg_force_n": avg_force,
                "contact_detected": contact_detected,
                "samples": samples,
            }

        elif cmd == "get_capture_status":
            with self._lock:
                return {
                    "capturing": self._capturing,
                    "trial_id": self._trial_id,
                    "cycle_count": self._cycle_count,
                    "samples_captured": len(self._capture_samples),
                    "duration_s": time.time() - self._capture_start_time if self._capturing else 0,
                }

        else:
            return {"error": f"Unknown command: {cmd}"}

    async def close(self) -> None:
        """Clean up resources."""
        LOGGER.info(f"Closing GazeboContactSensor '{self.name}'")


async def main():
    """Main entry point for the module."""
    Registry.register_resource_creator(
        Sensor.SUBTYPE,
        GazeboContactSensor.MODEL,
        ResourceCreatorRegistration(GazeboContactSensor.new, GazeboContactSensor.validate_config),
    )

    module = Module.from_args()
    module.add_model_from_registry(Sensor.SUBTYPE, GazeboContactSensor.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
