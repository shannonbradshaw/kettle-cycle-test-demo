"""Gazebo transport bridge for communication with simulation.

This module provides an abstraction layer over gz-transport for communicating
with Gazebo simulation. It handles:
- Joint state subscriptions
- Joint position commands
- Force/torque sensor readings
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lite6 joint names (matching xarm_ros URDF)
LITE6_JOINT_NAMES = [
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
]


@dataclass
class JointState:
    """Current state of robot joints."""
    positions: Dict[str, float] = field(default_factory=dict)
    velocities: Dict[str, float] = field(default_factory=dict)

    def get_position_list(self, joint_names: List[str]) -> List[float]:
        """Get positions as ordered list matching joint_names."""
        return [self.positions.get(name, 0.0) for name in joint_names]


@dataclass
class WrenchData:
    """Force/torque sensor reading."""
    force_x: float = 0.0
    force_y: float = 0.0
    force_z: float = 0.0
    torque_x: float = 0.0
    torque_y: float = 0.0
    torque_z: float = 0.0


class GazeboBridgeInterface(ABC):
    """Abstract interface for Gazebo communication.

    This interface allows for mock implementations in testing.
    """

    @abstractmethod
    def get_joint_state(self) -> JointState:
        """Get current joint positions and velocities."""
        pass

    @abstractmethod
    def set_joint_positions(self, positions: Dict[str, float]) -> None:
        """Command joints to move to target positions."""
        pass

    @abstractmethod
    def get_wrench(self) -> WrenchData:
        """Get current force/torque sensor reading."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
        pass


class GazeboBridge(GazeboBridgeInterface):
    """Real implementation using gz-transport.

    Communicates with Gazebo simulation via gz-transport topics:
    - Subscribes to: /world/{world}/model/{model}/joint_state
    - Publishes to: /model/{model}/joint/{joint}/0/cmd_pos
    - Subscribes to: /world/{world}/model/{model}/link/{link}/sensor/force_torque/wrench
    """

    def __init__(
        self,
        world_name: str = "kettle_world",
        model_name: str = "lite6",
        joint_names: Optional[List[str]] = None,
        force_sensor_link: str = "link6",
    ):
        """Initialize the Gazebo bridge.

        Args:
            world_name: Name of the Gazebo world
            model_name: Name of the robot model
            joint_names: List of joint names (defaults to LITE6_JOINT_NAMES)
            force_sensor_link: Link containing the force/torque sensor
        """
        self.world_name = world_name
        self.model_name = model_name
        self.joint_names = joint_names or LITE6_JOINT_NAMES
        self.force_sensor_link = force_sensor_link

        self._joint_state = JointState()
        self._wrench = WrenchData()
        self._lock = threading.Lock()
        self._node = None
        self._running = False

        self._init_transport()

    def _init_transport(self) -> None:
        """Initialize gz-transport node and subscriptions."""
        try:
            # Import gz-transport (Harmonic bindings)
            from gz.transport14 import Node
            from gz.msgs11.joint_states_pb2 import JointStates
            from gz.msgs11.wrench_pb2 import Wrench

            self._node = Node()
            self._running = True

            # Subscribe to joint states
            joint_state_topic = f"/world/{self.world_name}/model/{self.model_name}/joint_state"
            self._node.subscribe(
                JointStates,
                joint_state_topic,
                self._on_joint_state,
            )
            logger.info(f"Subscribed to joint states: {joint_state_topic}")

            # Subscribe to force/torque sensor
            wrench_topic = (
                f"/world/{self.world_name}/model/{self.model_name}"
                f"/link/{self.force_sensor_link}/sensor/force_torque/wrench"
            )
            self._node.subscribe(
                Wrench,
                wrench_topic,
                self._on_wrench,
            )
            logger.info(f"Subscribed to wrench: {wrench_topic}")

        except ImportError as e:
            logger.error(f"Failed to import gz-transport: {e}")
            logger.error("Ensure Gazebo Harmonic is installed with Python bindings")
            raise RuntimeError(
                "gz-transport14 not available. Install Gazebo Harmonic."
            ) from e

    def _on_joint_state(self, msg) -> None:
        """Callback for joint state messages."""
        with self._lock:
            for i, name in enumerate(msg.name):
                if i < len(msg.position):
                    self._joint_state.positions[name] = msg.position[i]
                if i < len(msg.velocity):
                    self._joint_state.velocities[name] = msg.velocity[i]

    def _on_wrench(self, msg) -> None:
        """Callback for wrench messages."""
        with self._lock:
            self._wrench = WrenchData(
                force_x=msg.force.x,
                force_y=msg.force.y,
                force_z=msg.force.z,
                torque_x=msg.torque.x,
                torque_y=msg.torque.y,
                torque_z=msg.torque.z,
            )

    def get_joint_state(self) -> JointState:
        """Get current joint positions and velocities."""
        with self._lock:
            # Return a copy to avoid race conditions
            return JointState(
                positions=dict(self._joint_state.positions),
                velocities=dict(self._joint_state.velocities),
            )

    def set_joint_positions(self, positions: Dict[str, float]) -> None:
        """Command joints to move to target positions.

        Publishes position commands to each joint's control topic.
        """
        try:
            from gz.msgs11.double_pb2 import Double

            for joint_name, position in positions.items():
                topic = f"/model/{self.model_name}/joint/{joint_name}/0/cmd_pos"
                msg = Double()
                msg.data = position
                self._node.request(topic, msg, Double, timeout=100)

        except ImportError as e:
            logger.error(f"Failed to publish joint command: {e}")
            raise

    def get_wrench(self) -> WrenchData:
        """Get current force/torque sensor reading."""
        with self._lock:
            return WrenchData(
                force_x=self._wrench.force_x,
                force_y=self._wrench.force_y,
                force_z=self._wrench.force_z,
                torque_x=self._wrench.torque_x,
                torque_y=self._wrench.torque_y,
                torque_z=self._wrench.torque_z,
            )

    def close(self) -> None:
        """Clean up resources."""
        self._running = False
        # gz-transport Node handles cleanup on deletion


class MockGazeboBridge(GazeboBridgeInterface):
    """Mock implementation for testing without Gazebo.

    Simulates joint positions moving toward targets and provides
    configurable force readings.
    """

    def __init__(self, joint_names: Optional[List[str]] = None):
        """Initialize mock bridge.

        Args:
            joint_names: List of joint names (defaults to LITE6_JOINT_NAMES)
        """
        self.joint_names = joint_names or LITE6_JOINT_NAMES
        self._positions = {name: 0.0 for name in self.joint_names}
        self._targets = {name: 0.0 for name in self.joint_names}
        self._velocities = {name: 0.0 for name in self.joint_names}
        self._wrench = WrenchData()
        self._lock = threading.Lock()

        # Simulation parameters
        self._position_tolerance = 0.01  # radians
        self._velocity = 1.0  # rad/s

    def get_joint_state(self) -> JointState:
        """Get current joint positions and velocities."""
        with self._lock:
            # Simulate movement toward targets
            self._simulate_step()
            return JointState(
                positions=dict(self._positions),
                velocities=dict(self._velocities),
            )

    def _simulate_step(self) -> None:
        """Simulate one step of motion toward targets."""
        dt = 0.02  # Assume 50Hz update rate
        for name in self.joint_names:
            current = self._positions[name]
            target = self._targets[name]
            diff = target - current

            if abs(diff) < self._position_tolerance:
                self._velocities[name] = 0.0
            else:
                # Move toward target
                step = min(abs(diff), self._velocity * dt)
                if diff > 0:
                    self._positions[name] += step
                    self._velocities[name] = self._velocity
                else:
                    self._positions[name] -= step
                    self._velocities[name] = -self._velocity

    def set_joint_positions(self, positions: Dict[str, float]) -> None:
        """Command joints to move to target positions."""
        with self._lock:
            for name, pos in positions.items():
                if name in self._targets:
                    self._targets[name] = pos

    def get_wrench(self) -> WrenchData:
        """Get current force/torque sensor reading."""
        with self._lock:
            return WrenchData(
                force_x=self._wrench.force_x,
                force_y=self._wrench.force_y,
                force_z=self._wrench.force_z,
                torque_x=self._wrench.torque_x,
                torque_y=self._wrench.torque_y,
                torque_z=self._wrench.torque_z,
            )

    def set_wrench(self, wrench: WrenchData) -> None:
        """Set mock wrench reading (for testing)."""
        with self._lock:
            self._wrench = wrench

    def set_positions_immediately(self, positions: Dict[str, float]) -> None:
        """Set positions immediately without simulating motion (for testing)."""
        with self._lock:
            for name, pos in positions.items():
                if name in self._positions:
                    self._positions[name] = pos
                    self._targets[name] = pos

    def close(self) -> None:
        """Clean up resources (no-op for mock)."""
        pass
