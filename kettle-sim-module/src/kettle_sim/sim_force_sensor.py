"""Simulated force sensor component using MuJoCo.

This module provides a Viam sensor component that reads force/torque
data from a simulated sensor in MuJoCo. It mirrors the capture state
machine pattern from the Go implementation (force_sensor.go).
"""

import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence

from viam.components.sensor import Sensor
from viam.logging import getLogger
from viam.proto.common import Geometry
from viam.resource.base import ResourceBase
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.resource.types import Model, ModelFamily

from .mujoco_sim import (
    SimulationInterface,
    WrenchData,
    get_global_simulation,
)

logger = getLogger(__name__)

# Model definition for Viam registry
FORCE_SENSOR_MODEL = Model(ModelFamily("viamdemo", "kettle-sim"), "force-sensor")


class CaptureState(Enum):
    """Capture state machine states."""
    IDLE = "idle"
    WAITING = "waiting"  # Waiting for first non-zero reading
    ACTIVE = "capturing"  # Actively capturing samples


class SimulatedForceSensor(Sensor):
    """Simulated force/torque sensor using MuJoCo.

    This component implements the Viam sensor interface by reading
    force/torque data from a simulated sensor in MuJoCo. It includes
    a capture state machine matching the Go implementation.

    Configuration attributes:
        model_path: Path to MJCF model file (optional, uses default if not set)
        use_mock: Use mock simulation without MuJoCo (default: false)
        sample_rate_hz: Sampling rate during capture (default: 50)
        buffer_size: Maximum samples to store (default: 100)
        zero_threshold: Force below this is "zero" (default: 5.0)
        capture_timeout_ms: Capture timeout in ms (default: 10000)
    """

    MODEL: ClassVar[Model] = FORCE_SENSOR_MODEL

    def __init__(self, name: str):
        """Initialize the simulated force sensor."""
        super().__init__(name)
        self._sim: Optional[SimulationInterface] = None
        self._lock = threading.Lock()
        self._running = False

        # Configuration
        self._sample_rate_hz = 50
        self._buffer_size = 100
        self._zero_threshold = 5.0
        self._capture_timeout = 10.0  # seconds

        # Capture state
        self._state = CaptureState.IDLE
        self._samples: List[float] = []
        self._timeout_timer: Optional[threading.Timer] = None

        # Trial metadata (passed via start_capture)
        self._trial_id = ""
        self._cycle_count = 0

        # Sampling thread
        self._sampling_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @classmethod
    def new(
        cls,
        config: "ComponentConfig",  # type: ignore
        dependencies: Mapping[ResourceBase, ResourceBase],
    ) -> "SimulatedForceSensor":
        """Create a new SimulatedForceSensor instance."""
        sensor = cls(config.name)
        sensor.reconfigure(config, dependencies)
        return sensor

    def reconfigure(
        self,
        config: "ComponentConfig",  # type: ignore
        dependencies: Mapping[ResourceBase, ResourceBase],
    ) -> None:
        """Reconfigure the sensor with new settings."""
        attrs = config.attributes.fields if config.attributes else {}

        # Extract configuration
        model_path = attrs.get("model_path", {}).string_value or None
        use_mock = attrs.get("use_mock", {}).bool_value or False

        # Sampling configuration
        sample_rate = attrs.get("sample_rate_hz", {}).number_value
        self._sample_rate_hz = int(sample_rate) if sample_rate else 50

        buffer_size = attrs.get("buffer_size", {}).number_value
        self._buffer_size = int(buffer_size) if buffer_size else 100

        zero_threshold = attrs.get("zero_threshold", {}).number_value
        self._zero_threshold = zero_threshold if zero_threshold else 5.0

        capture_timeout = attrs.get("capture_timeout_ms", {}).number_value
        self._capture_timeout = (capture_timeout / 1000.0) if capture_timeout else 10.0

        logger.info(
            f"Configuring SimulatedForceSensor: model_path={model_path}, "
            f"use_mock={use_mock}"
        )

        # Clean up existing resources
        self._cleanup()

        # Get or create global simulation instance
        self._sim = get_global_simulation(use_mock=use_mock, model_path=model_path)
        logger.info("Connected to MuJoCo force sensor")

        # Start sampling thread
        self._running = True
        self._stop_event.clear()
        self._sampling_thread = threading.Thread(
            target=self._sampling_loop,
            daemon=True,
        )
        self._sampling_thread.start()

    def _cleanup(self) -> None:
        """Clean up resources."""
        # Stop sampling thread
        self._running = False
        self._stop_event.set()
        if self._sampling_thread is not None:
            self._sampling_thread.join(timeout=2.0)
            self._sampling_thread = None

        # Cancel timeout timer
        if self._timeout_timer is not None:
            self._timeout_timer.cancel()
            self._timeout_timer = None

        # Don't stop global simulation here - other components may be using it

    def _sampling_loop(self) -> None:
        """Background loop for sampling force data."""
        interval = 1.0 / self._sample_rate_hz

        while self._running and not self._stop_event.is_set():
            start = time.time()

            with self._lock:
                current_state = self._state

            if current_state != CaptureState.IDLE:
                self._sample_force()

            # Sleep for remainder of interval
            elapsed = time.time() - start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

    def _sample_force(self) -> None:
        """Sample force reading and update state machine."""
        if self._sim is None:
            return

        wrench = self._sim.get_wrench_data()
        force_z = abs(wrench.fz)

        with self._lock:
            if self._state == CaptureState.WAITING and force_z >= self._zero_threshold:
                # First non-zero reading - start capturing
                self._state = CaptureState.ACTIVE
                self._samples = []
                logger.info(f"Force capture started (first reading: {force_z:.2f})")

            if self._state == CaptureState.ACTIVE:
                # Rolling buffer
                if len(self._samples) >= self._buffer_size:
                    self._samples.pop(0)
                self._samples.append(force_z)

    async def get_readings(
        self,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> Mapping[str, Any]:
        """Get current sensor readings.

        Returns a dict matching the Go implementation:
        - trial_id: Current trial ID
        - cycle_count: Current cycle count
        - should_sync: Whether data should be synced
        - samples: List of force samples
        - sample_count: Number of samples
        - capture_state: Current state (idle/waiting/capturing)
        - max_force: Maximum force in samples (if any)
        """
        with self._lock:
            samples_copy = list(self._samples)
            state = self._state
            trial_id = self._trial_id
            cycle_count = self._cycle_count

        # should_sync is true when we have an active trial
        should_sync = bool(trial_id)

        result: Dict[str, Any] = {
            "trial_id": trial_id,
            "cycle_count": cycle_count,
            "should_sync": should_sync,
            "samples": samples_copy,
            "sample_count": len(samples_copy),
            "capture_state": state.value,
        }

        if samples_copy:
            result["max_force"] = max(samples_copy)

        # Also include current instantaneous force reading
        if self._sim is not None:
            wrench = self._sim.get_wrench_data()
            result["fx"] = wrench.fx
            result["fy"] = wrench.fy
            result["fz"] = wrench.fz
            result["tx"] = wrench.tx
            result["ty"] = wrench.ty
            result["tz"] = wrench.tz

        return result

    async def do_command(
        self,
        command: Mapping[str, Any],
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Mapping[str, Any]:
        """Handle DoCommand requests.

        Supported commands:
        - start_capture: Begin capture, optionally with trial_id and cycle_count
        - end_capture: End capture and return statistics
        """
        cmd = command.get("command")
        if not cmd:
            raise ValueError("Missing 'command' field")

        if cmd == "start_capture":
            return self._handle_start_capture(command)
        elif cmd == "end_capture":
            return self._handle_end_capture()
        else:
            raise ValueError(f"Unknown command: {cmd}")

    def _handle_start_capture(self, command: Mapping[str, Any]) -> Dict[str, Any]:
        """Handle start_capture command."""
        with self._lock:
            if self._state != CaptureState.IDLE:
                raise RuntimeError(f"Capture already in progress (state: {self._state.value})")

            # Extract trial metadata
            self._trial_id = command.get("trial_id", "")
            cycle_count = command.get("cycle_count", 0)
            if isinstance(cycle_count, float):
                cycle_count = int(cycle_count)
            self._cycle_count = cycle_count

            # Reset and start waiting
            self._state = CaptureState.WAITING
            self._samples = []

            # Start timeout timer
            self._timeout_timer = threading.Timer(
                self._capture_timeout,
                self._on_capture_timeout,
            )
            self._timeout_timer.start()

        logger.info(
            f"Capture started, waiting for non-zero reading "
            f"(threshold: {self._zero_threshold:.2f})"
        )

        return {"status": "waiting"}

    def _handle_end_capture(self) -> Dict[str, Any]:
        """Handle end_capture command."""
        with self._lock:
            if self._state == CaptureState.IDLE:
                raise RuntimeError("No capture in progress")

            # Cancel timeout
            if self._timeout_timer is not None:
                self._timeout_timer.cancel()
                self._timeout_timer = None

            sample_count = len(self._samples)
            max_force = max(self._samples) if self._samples else 0.0
            prev_state = self._state

            # Store values before clearing
            trial_id = self._trial_id
            cycle_count = self._cycle_count

            # Reset state
            self._state = CaptureState.IDLE
            self._trial_id = ""
            self._cycle_count = 0

        state_str = "waiting" if prev_state == CaptureState.WAITING else "capturing"
        logger.info(
            f"Capture ended (was {state_str}): {sample_count} samples, "
            f"max force: {max_force:.2f}"
        )

        return {
            "status": "completed",
            "sample_count": sample_count,
            "max_force": max_force,
            "trial_id": trial_id,
            "cycle_count": cycle_count,
        }

    def _on_capture_timeout(self) -> None:
        """Handle capture timeout."""
        with self._lock:
            if self._state != CaptureState.IDLE:
                logger.error(
                    f"Capture timeout: end_capture not called within "
                    f"{self._capture_timeout}s"
                )
                self._state = CaptureState.IDLE
                self._trial_id = ""
                self._cycle_count = 0

    async def get_geometries(
        self,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> List[Geometry]:
        """Get sensor geometries."""
        return []

    async def close(self) -> None:
        """Clean up resources when component is closed."""
        self._cleanup()


# Register the component with Viam
def register() -> None:
    """Register SimulatedForceSensor with the Viam registry."""
    Registry.register_resource_creator(
        Sensor.SUBTYPE,
        FORCE_SENSOR_MODEL,
        ResourceCreatorRegistration(
            SimulatedForceSensor.new,
            SimulatedForceSensor.validate_config,
        ),
    )


# Validation function
@staticmethod
def validate_config(config: "ComponentConfig") -> Sequence[str]:  # type: ignore
    """Validate component configuration."""
    attrs = config.attributes.fields if config.attributes else {}

    # Check for arm dependency if specified
    deps = []
    arm_name = attrs.get("arm", {}).string_value
    if arm_name:
        deps.append(arm_name)

    return deps


# Attach to class
SimulatedForceSensor.validate_config = validate_config
