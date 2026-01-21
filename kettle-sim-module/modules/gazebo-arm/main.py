#!/usr/bin/env python3
"""
Viam module that bridges a Gazebo simulated arm to Viam's arm API.

This module:
- Subscribes to Gazebo joint state topics to read current positions
- Publishes to Gazebo joint command topics to control the arm
- Exposes the standard Viam arm component interface
"""

import asyncio
import math
from threading import Lock
from typing import Any, Dict, List, Mapping, Optional, Tuple

from viam.components.arm import Arm, JointPositions, KinematicsFileFormat, Pose
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
    from gz.msgs10.double_pb2 import Double
    from gz.msgs10.model_pb2 import Model as GzModel
    GZ_AVAILABLE = True
except ImportError:
    GZ_AVAILABLE = False
    print("WARNING: gz-transport13 not available. Install with: apt install python3-gz-transport13 python3-gz-msgs10")

LOGGER = getLogger(__name__)


class GazeboArm(Arm):
    """
    A Viam arm component that controls a simulated arm in Gazebo.

    Attributes:
        model_name: The Gazebo model name (e.g., "xarm6")
        joint_names: List of joint names in order
        num_joints: Number of joints (default 6 for xArm6)
    """

    MODEL = Model(ModelFamily("viam-labs", "arm"), "gazebo")

    # xArm6 joint limits (radians)
    JOINT_LIMITS = [
        (-6.28, 6.28),    # joint1: ±360°
        (-2.06, 2.09),    # joint2: -118° to +120°
        (-3.93, 0.19),    # joint3: -225° to +11°
        (-6.28, 6.28),    # joint4: ±360°
        (-1.69, 3.14),    # joint5: -97° to +180°
        (-6.28, 6.28),    # joint6: ±360°
    ]

    def __init__(self, name: str):
        super().__init__(name)
        self._node: Optional[Any] = None
        self._model_name: str = "xarm6"
        self._world_name: str = "kettle_test"
        self._num_joints: int = 6
        self._joint_names: List[str] = [f"joint{i+1}" for i in range(6)]
        self._current_positions: List[float] = [0.0] * 6
        self._position_lock = Lock()
        self._publishers: List[Any] = []

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> "GazeboArm":
        """Create a new GazeboArm instance."""
        arm = cls(config.name)
        arm.reconfigure(config, dependencies)
        return arm

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> List[str]:
        """Validate the component configuration."""
        errors = []
        if not GZ_AVAILABLE:
            errors.append("gz-transport13 Python bindings not available")
        return errors

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> None:
        """Reconfigure the arm with new settings."""
        attrs = config.attributes.fields

        if "model_name" in attrs:
            self._model_name = attrs["model_name"].string_value
        if "world_name" in attrs:
            self._world_name = attrs["world_name"].string_value
        if "num_joints" in attrs:
            self._num_joints = int(attrs["num_joints"].number_value)
            self._joint_names = [f"joint{i+1}" for i in range(self._num_joints)]
            self._current_positions = [0.0] * self._num_joints

        self._setup_gazebo_connection()
        LOGGER.info(f"Configured GazeboArm '{self.name}' for model: {self._model_name}")

    def _setup_gazebo_connection(self) -> None:
        """Set up Gazebo transport publishers and subscribers."""
        if not GZ_AVAILABLE:
            LOGGER.error("Cannot setup: gz-transport13 not available")
            return

        if self._node is None:
            self._node = Node()

        # Create publishers for each joint position command
        self._publishers = []
        for joint_name in self._joint_names:
            topic = f"/model/{self._model_name}/joint/{joint_name}/0/cmd_pos"
            pub = self._node.advertise(topic, Double)
            self._publishers.append(pub)
            LOGGER.debug(f"Created publisher for topic: {topic}")

        # Note: Joint state subscription would go here if Gazebo publishes states
        # For now, we track commanded positions locally

        LOGGER.info(f"Set up Gazebo connection for {self._num_joints} joints")

    async def get_end_position(
        self,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Pose:
        """Get the current end effector pose."""
        # For simulation, we'd compute forward kinematics here
        # For now, return a placeholder
        raise NotImplementedError(
            "Forward kinematics not implemented. Use get_joint_positions() instead."
        )

    async def move_to_position(
        self,
        pose: Pose,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> None:
        """Move to a Cartesian pose."""
        # Would require inverse kinematics
        raise NotImplementedError(
            "Inverse kinematics not implemented. Use move_to_joint_positions() instead."
        )

    async def get_joint_positions(
        self,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> JointPositions:
        """Get current joint positions in degrees."""
        with self._position_lock:
            # Convert radians to degrees for Viam API
            positions_deg = [math.degrees(p) for p in self._current_positions]
            return JointPositions(values=positions_deg)

    async def move_to_joint_positions(
        self,
        positions: JointPositions,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> None:
        """Move to specified joint positions (in degrees)."""
        if len(positions.values) != self._num_joints:
            raise ValueError(
                f"Expected {self._num_joints} joint positions, got {len(positions.values)}"
            )

        # Convert degrees to radians
        positions_rad = [math.radians(p) for p in positions.values]

        # Validate joint limits
        for i, (pos, (lower, upper)) in enumerate(zip(positions_rad, self.JOINT_LIMITS)):
            if pos < lower or pos > upper:
                raise ValueError(
                    f"Joint {i+1} position {math.degrees(pos):.1f}° out of range "
                    f"[{math.degrees(lower):.1f}°, {math.degrees(upper):.1f}°]"
                )

        # Publish commands to Gazebo
        for i, (pub, pos) in enumerate(zip(self._publishers, positions_rad)):
            msg = Double()
            msg.data = pos
            pub.publish(msg)
            LOGGER.debug(f"Published joint{i+1} position: {math.degrees(pos):.1f}°")

        # Update local tracking
        with self._position_lock:
            self._current_positions = positions_rad

        LOGGER.info(f"Commanded joint positions: {[f'{p:.1f}°' for p in positions.values]}")

    async def stop(
        self,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> None:
        """Stop the arm."""
        # In simulation, we don't have velocity control, so just log
        LOGGER.info("Stop requested (no-op in position control mode)")

    async def is_moving(
        self,
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> bool:
        """Check if arm is currently moving."""
        # Would need to track commanded vs actual positions
        # For now, return False
        return False

    async def get_kinematics(
        self,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Tuple[KinematicsFileFormat, bytes]:
        """Return kinematics file (URDF or similar)."""
        # Could return xArm6 URDF here
        raise NotImplementedError("Kinematics file not available")

    async def close(self) -> None:
        """Clean up resources."""
        LOGGER.info(f"Closing GazeboArm '{self.name}'")


async def main():
    """Main entry point for the module."""
    Registry.register_resource_creator(
        Arm.SUBTYPE,
        GazeboArm.MODEL,
        ResourceCreatorRegistration(GazeboArm.new, GazeboArm.validate_config),
    )

    module = Module.from_args()
    module.add_model_from_registry(Arm.SUBTYPE, GazeboArm.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
