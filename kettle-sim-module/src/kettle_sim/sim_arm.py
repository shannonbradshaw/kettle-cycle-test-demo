"""Simulated arm component using Gazebo.

This module provides a Viam arm component that controls a simulated
Lite6 robot arm in Gazebo.
"""

import asyncio
import logging
import math
import threading
import time
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Tuple

from viam.components.arm import Arm, JointPositions, KinematicsFileFormat, Pose
from viam.logging import getLogger
from viam.proto.common import Geometry
from viam.resource.base import ResourceBase
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.resource.types import Model, ModelFamily

from .gazebo_bridge import (
    GazeboBridge,
    GazeboBridgeInterface,
    MockGazeboBridge,
    LITE6_JOINT_NAMES,
)
from .gazebo_manager import (
    GazeboConfig,
    GazeboManager,
    GazeboMode,
    get_global_manager,
    set_global_manager,
)

logger = getLogger(__name__)

# Model definition for Viam registry
LITE6_MODEL = Model(ModelFamily("viamdemo", "kettle-sim"), "lite6")


class SimulatedArm(Arm):
    """Simulated Lite6 arm using Gazebo physics.

    This component implements the Viam arm interface by controlling
    a simulated robot arm in Gazebo via gz-transport.

    Configuration attributes:
        world_name: Name of the Gazebo world (default: "kettle_world")
        model_name: Name of the robot model in Gazebo (default: "lite6")
        use_mock: Use mock bridge without Gazebo (default: false)
        gazebo_mode: "headless", "gui", or "external" (default: "headless")
        world_file: Path to world SDF file (optional, uses default if not set)
    """

    MODEL: ClassVar[Model] = LITE6_MODEL

    # Joint limits for Lite6 (radians) - from xarm_ros URDF
    JOINT_LIMITS: ClassVar[List[Tuple[float, float]]] = [
        (-6.2832, 6.2832),   # joint1
        (-2.059, 2.094),     # joint2
        (-0.192, 3.927),     # joint3
        (-6.2832, 6.2832),   # joint4
        (-1.692, 3.141),     # joint5
        (-6.2832, 6.2832),   # joint6
    ]

    def __init__(self, name: str):
        """Initialize the simulated arm."""
        super().__init__(name)
        self._bridge: Optional[GazeboBridgeInterface] = None
        self._manager: Optional[GazeboManager] = None
        self._joint_names = LITE6_JOINT_NAMES
        self._target_positions: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._position_tolerance = 0.05  # radians
        self._move_timeout = 30.0  # seconds

    @classmethod
    def new(
        cls,
        config: "ComponentConfig",  # type: ignore
        dependencies: Mapping[ResourceBase, ResourceBase],
    ) -> "SimulatedArm":
        """Create a new SimulatedArm instance.

        This is called by the Viam module system when instantiating the component.
        """
        arm = cls(config.name)
        arm.reconfigure(config, dependencies)
        return arm

    def reconfigure(
        self,
        config: "ComponentConfig",  # type: ignore
        dependencies: Mapping[ResourceBase, ResourceBase],
    ) -> None:
        """Reconfigure the arm with new settings."""
        attrs = config.attributes.fields if config.attributes else {}

        # Extract configuration
        world_name = attrs.get("world_name", {}).string_value or "kettle_world"
        model_name = attrs.get("model_name", {}).string_value or "lite6"
        use_mock = attrs.get("use_mock", {}).bool_value or False
        gazebo_mode_str = attrs.get("gazebo_mode", {}).string_value or "headless"
        world_file = attrs.get("world_file", {}).string_value or ""

        logger.info(
            f"Configuring SimulatedArm: world={world_name}, model={model_name}, "
            f"use_mock={use_mock}, mode={gazebo_mode_str}"
        )

        # Clean up existing resources
        self._cleanup()

        if use_mock:
            # Use mock bridge for testing without Gazebo
            self._bridge = MockGazeboBridge(self._joint_names)
            logger.info("Using mock Gazebo bridge")
        else:
            # Start or connect to Gazebo
            gazebo_mode = GazeboMode(gazebo_mode_str)

            # Use global manager if available, otherwise create new one
            manager = get_global_manager()
            if manager is None:
                if not world_file:
                    world_file = str(GazeboManager.get_default_world_path())

                gz_config = GazeboConfig(
                    world_file=world_file,
                    mode=gazebo_mode,
                )
                manager = GazeboManager(gz_config)
                manager.start()
                set_global_manager(manager)
                self._manager = manager  # Track for cleanup

            # Create bridge to Gazebo
            self._bridge = GazeboBridge(
                world_name=world_name,
                model_name=model_name,
                joint_names=self._joint_names,
            )
            logger.info(f"Connected to Gazebo simulation")

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._bridge is not None:
            self._bridge.close()
            self._bridge = None

        # Don't stop global manager here - other components may be using it

    async def get_end_position(
        self,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> Pose:
        """Get the current end effector position.

        Note: Forward kinematics not implemented in MVP.
        Returns a placeholder pose.
        """
        # MVP: FK not implemented, return placeholder
        logger.debug("get_end_position called (FK not implemented)")
        return Pose(
            x=0.0, y=0.0, z=0.0,
            o_x=0.0, o_y=0.0, o_z=0.0, theta=0.0,
        )

    async def move_to_position(
        self,
        pose: Pose,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Move to a Cartesian position.

        Note: Inverse kinematics not implemented in MVP.
        Raises NotImplementedError.
        """
        raise NotImplementedError(
            "move_to_position (inverse kinematics) not implemented. "
            "Use move_to_joint_positions instead."
        )

    async def get_joint_positions(
        self,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> JointPositions:
        """Get current joint positions."""
        if self._bridge is None:
            raise RuntimeError("Arm not initialized")

        state = self._bridge.get_joint_state()
        positions = state.get_position_list(self._joint_names)

        # Convert to degrees for Viam API
        positions_deg = [math.degrees(p) for p in positions]

        return JointPositions(values=positions_deg)

    async def move_to_joint_positions(
        self,
        positions: JointPositions,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Move arm to specified joint positions.

        Args:
            positions: Target joint positions in degrees
        """
        if self._bridge is None:
            raise RuntimeError("Arm not initialized")

        if len(positions.values) != len(self._joint_names):
            raise ValueError(
                f"Expected {len(self._joint_names)} joint positions, "
                f"got {len(positions.values)}"
            )

        # Convert from degrees to radians
        target_rad = {
            name: math.radians(pos)
            for name, pos in zip(self._joint_names, positions.values)
        }

        # Validate joint limits
        for i, (name, pos) in enumerate(target_rad.items()):
            min_val, max_val = self.JOINT_LIMITS[i]
            if pos < min_val or pos > max_val:
                raise ValueError(
                    f"Joint {name} position {math.degrees(pos):.1f}deg "
                    f"out of range [{math.degrees(min_val):.1f}, "
                    f"{math.degrees(max_val):.1f}] degrees"
                )

        # Store target for is_moving check
        with self._lock:
            self._target_positions = target_rad.copy()

        # Send command to Gazebo
        self._bridge.set_joint_positions(target_rad)

        # Wait for movement to complete
        await self._wait_for_position(target_rad)

    async def _wait_for_position(
        self,
        target: Dict[str, float],
        timeout: Optional[float] = None,
    ) -> None:
        """Wait for arm to reach target position.

        Args:
            target: Target joint positions in radians
            timeout: Timeout in seconds (uses default if not set)
        """
        if timeout is None:
            timeout = self._move_timeout

        start_time = time.time()

        while time.time() - start_time < timeout:
            state = self._bridge.get_joint_state()

            # Check if all joints are at target
            all_at_target = True
            for name, target_pos in target.items():
                current = state.positions.get(name, 0.0)
                if abs(current - target_pos) > self._position_tolerance:
                    all_at_target = False
                    break

            if all_at_target:
                return

            await asyncio.sleep(0.05)  # 20Hz check rate

        raise TimeoutError(
            f"Arm did not reach target position within {timeout}s"
        )

    async def is_moving(self, **kwargs) -> bool:
        """Check if the arm is currently moving."""
        if self._bridge is None:
            return False

        state = self._bridge.get_joint_state()

        # Check if any joint has significant velocity
        velocity_threshold = 0.01  # rad/s
        for name in self._joint_names:
            vel = abs(state.velocities.get(name, 0.0))
            if vel > velocity_threshold:
                return True

        # Also check if we're not at target position
        with self._lock:
            if self._target_positions:
                for name, target in self._target_positions.items():
                    current = state.positions.get(name, 0.0)
                    if abs(current - target) > self._position_tolerance:
                        return True

        return False

    async def stop(self, extra: Optional[Mapping[str, Any]] = None, **kwargs) -> None:
        """Stop the arm immediately."""
        if self._bridge is None:
            return

        # Command current position to stop motion
        state = self._bridge.get_joint_state()
        self._bridge.set_joint_positions(state.positions)

        with self._lock:
            self._target_positions = {}

        logger.info("Arm stopped")

    async def get_geometries(
        self,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> List[Geometry]:
        """Get arm geometries for collision checking."""
        # MVP: Return empty list
        return []

    async def get_kinematics(
        self,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> Tuple[KinematicsFileFormat, bytes]:
        """Get kinematics file (URDF)."""
        # MVP: Not implemented
        return (KinematicsFileFormat.KINEMATICS_FILE_FORMAT_UNSPECIFIED, b"")

    async def close(self) -> None:
        """Clean up resources when component is closed."""
        self._cleanup()


# Register the component with Viam
def register() -> None:
    """Register SimulatedArm with the Viam registry."""
    Registry.register_resource_creator(
        Arm.SUBTYPE,
        LITE6_MODEL,
        ResourceCreatorRegistration(SimulatedArm.new, SimulatedArm.validate_config),
    )


# Validation function
@staticmethod
def validate_config(config: "ComponentConfig") -> Sequence[str]:  # type: ignore
    """Validate component configuration."""
    # No dependencies required
    return []


# Attach to class
SimulatedArm.validate_config = validate_config
