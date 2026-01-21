"""Simulated arm component using MuJoCo.

This module provides a Viam arm component that controls a simulated
Lite6 robot arm using MuJoCo physics.
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

from .mujoco_sim import (
    JOINT_NAMES,
    SimulationInterface,
    get_global_simulation,
)

logger = getLogger(__name__)

# Model definition for Viam registry
LITE6_MODEL = Model(ModelFamily("viamdemo", "kettle-sim"), "lite6")


class SimulatedArm(Arm):
    """Simulated Lite6 arm using MuJoCo physics.

    This component implements the Viam arm interface by controlling
    a simulated robot arm using MuJoCo.

    Configuration attributes:
        model_path: Path to MJCF model file (optional, uses default if not set)
        use_mock: Use mock simulation without MuJoCo (default: false)
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
        self._sim: Optional[SimulationInterface] = None
        self._joint_names = JOINT_NAMES
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
        model_path = attrs.get("model_path", {}).string_value or None
        use_mock = attrs.get("use_mock", {}).bool_value or False

        logger.info(
            f"Configuring SimulatedArm: model_path={model_path}, use_mock={use_mock}"
        )

        # Get or create global simulation instance
        self._sim = get_global_simulation(use_mock=use_mock, model_path=model_path)
        logger.info("Connected to MuJoCo simulation")

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
        if self._sim is None:
            raise RuntimeError("Arm not initialized")

        state = self._sim.get_joint_state()

        # Get positions in order
        positions = [state.positions.get(name, 0.0) for name in self._joint_names]

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
        if self._sim is None:
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

        # Send command to simulation
        self._sim.set_joint_targets(target_rad)

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
            state = self._sim.get_joint_state()

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
        if self._sim is None:
            return False

        state = self._sim.get_joint_state()

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
        if self._sim is None:
            return

        # Command current position to stop motion
        state = self._sim.get_joint_state()
        self._sim.set_joint_targets(state.positions)

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
        # Don't stop global simulation here - other components may be using it
        pass


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
