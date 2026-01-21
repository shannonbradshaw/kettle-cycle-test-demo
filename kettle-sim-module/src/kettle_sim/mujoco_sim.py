"""MuJoCo simulation wrapper for kettle cycle testing.

This module provides a thread-safe wrapper around MuJoCo physics simulation
for the Lite6 robot arm. It handles:
- Loading and stepping the simulation
- Joint position control via actuators
- Force/torque sensor readings
- Background simulation loop
"""

import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Joint names for the Lite6 arm
JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]


@dataclass
class JointState:
    """Current state of robot joints."""
    positions: dict[str, float]  # Joint name -> position in radians
    velocities: dict[str, float]  # Joint name -> velocity in rad/s


@dataclass
class WrenchData:
    """Force/torque sensor reading."""
    fx: float = 0.0  # Force X (N)
    fy: float = 0.0  # Force Y (N)
    fz: float = 0.0  # Force Z (N)
    tx: float = 0.0  # Torque X (Nm)
    ty: float = 0.0  # Torque Y (Nm)
    tz: float = 0.0  # Torque Z (Nm)


class SimulationInterface(ABC):
    """Abstract interface for simulation backends (MuJoCo or Mock)."""

    @abstractmethod
    def step(self) -> None:
        """Advance simulation by one timestep."""
        pass

    @abstractmethod
    def get_joint_state(self) -> JointState:
        """Get current joint positions and velocities."""
        pass

    @abstractmethod
    def set_joint_targets(self, positions: dict[str, float]) -> None:
        """Set target positions for position-controlled joints."""
        pass

    @abstractmethod
    def get_wrench_data(self) -> WrenchData:
        """Get force/torque sensor reading."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the simulation loop."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the simulation loop."""
        pass


class MuJoCoSimulation(SimulationInterface):
    """MuJoCo-based physics simulation for the Lite6 arm.

    This class wraps MuJoCo to provide:
    - Thread-safe access to simulation state
    - Background physics stepping at configurable rate
    - Joint position control via actuators
    - Force/torque sensor readings

    Example:
        sim = MuJoCoSimulation("/path/to/lite6.xml")
        sim.start()
        sim.set_joint_targets({"joint1": 0.5, "joint2": 0.3})
        state = sim.get_joint_state()
        wrench = sim.get_wrench_data()
        sim.stop()
    """

    def __init__(self, model_path: Optional[str] = None, step_rate_hz: int = 1000):
        """Initialize the MuJoCo simulation.

        Args:
            model_path: Path to MJCF model file. If None, uses default lite6.xml.
            step_rate_hz: Simulation step rate in Hz (default 1000).
        """
        try:
            import mujoco
            self._mujoco = mujoco
        except ImportError as e:
            raise ImportError(
                "MuJoCo is required. Install with: pip install mujoco"
            ) from e

        if model_path is None:
            # Use default model from models/ directory
            model_path = str(
                Path(__file__).parent.parent.parent / "models" / "lite6.xml"
            )

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        logger.info(f"Loading MuJoCo model from {model_path}")
        self.model = mujoco.MjModel.from_xml_path(model_path)
        self.data = mujoco.MjData(self.model)

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._step_rate_hz = step_rate_hz

        # Build mappings for fast lookups
        self._joint_ids = {}
        self._actuator_ids = {}
        self._sensor_ids = {}

        for name in JOINT_NAMES:
            self._joint_ids[name] = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_JOINT, name
            )
            self._actuator_ids[name] = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"{name}_ctrl"
            )

        # Sensor IDs for force/torque and joint position/velocity
        self._sensor_ids["ft_force"] = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_SENSOR, "ft_force"
        )
        self._sensor_ids["ft_torque"] = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_SENSOR, "ft_torque"
        )

        for name in JOINT_NAMES:
            self._sensor_ids[f"{name}_pos"] = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_SENSOR, f"{name}_pos"
            )
            self._sensor_ids[f"{name}_vel"] = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_SENSOR, f"{name}_vel"
            )

        logger.info(f"MuJoCo simulation initialized with {len(JOINT_NAMES)} joints")

    def step(self) -> None:
        """Advance simulation by one timestep (thread-safe)."""
        with self._lock:
            self._mujoco.mj_step(self.model, self.data)

    def get_joint_state(self) -> JointState:
        """Get current joint positions and velocities (thread-safe)."""
        positions = {}
        velocities = {}

        with self._lock:
            for name in JOINT_NAMES:
                pos_sensor_id = self._sensor_ids[f"{name}_pos"]
                vel_sensor_id = self._sensor_ids[f"{name}_vel"]

                # Sensor data is stored contiguously, each sensor has an address
                pos_addr = self.model.sensor_adr[pos_sensor_id]
                vel_addr = self.model.sensor_adr[vel_sensor_id]

                positions[name] = float(self.data.sensordata[pos_addr])
                velocities[name] = float(self.data.sensordata[vel_addr])

        return JointState(positions=positions, velocities=velocities)

    def set_joint_targets(self, positions: dict[str, float]) -> None:
        """Set target positions for position-controlled joints (thread-safe).

        Args:
            positions: Dict mapping joint names to target positions in radians.
        """
        with self._lock:
            for name, pos in positions.items():
                if name in self._actuator_ids:
                    actuator_id = self._actuator_ids[name]
                    self.data.ctrl[actuator_id] = pos

    def get_wrench_data(self) -> WrenchData:
        """Get force/torque sensor reading (thread-safe)."""
        with self._lock:
            force_addr = self.model.sensor_adr[self._sensor_ids["ft_force"]]
            torque_addr = self.model.sensor_adr[self._sensor_ids["ft_torque"]]

            # Force sensor returns 3 values (fx, fy, fz)
            fx = float(self.data.sensordata[force_addr])
            fy = float(self.data.sensordata[force_addr + 1])
            fz = float(self.data.sensordata[force_addr + 2])

            # Torque sensor returns 3 values (tx, ty, tz)
            tx = float(self.data.sensordata[torque_addr])
            ty = float(self.data.sensordata[torque_addr + 1])
            tz = float(self.data.sensordata[torque_addr + 2])

        return WrenchData(fx=fx, fy=fy, fz=fz, tx=tx, ty=ty, tz=tz)

    def start(self) -> None:
        """Start the background simulation loop."""
        if self._running:
            logger.warning("Simulation already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()
        logger.info(f"Simulation loop started at {self._step_rate_hz} Hz")

    def stop(self) -> None:
        """Stop the background simulation loop."""
        if not self._running:
            return

        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("Simulation loop stopped")

    def _simulation_loop(self) -> None:
        """Run simulation at specified rate (runs in background thread)."""
        dt = 1.0 / self._step_rate_hz
        next_step = time.perf_counter()

        while self._running:
            self.step()

            # Maintain consistent step rate
            next_step += dt
            sleep_time = next_step - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Simulation running behind, reset timing
                next_step = time.perf_counter()

    def reset(self) -> None:
        """Reset simulation to initial state (thread-safe)."""
        with self._lock:
            self._mujoco.mj_resetData(self.model, self.data)


class MockSimulation(SimulationInterface):
    """Mock simulation for testing without MuJoCo dependency.

    Provides realistic motion simulation by moving joints toward targets
    at a configurable velocity, matching the behavior of MockGazeboBridge.
    """

    def __init__(self, velocity: float = 1.0, position_tolerance: float = 0.01):
        """Initialize mock simulation.

        Args:
            velocity: Simulated joint velocity in rad/s.
            position_tolerance: Position tolerance for "at target" detection.
        """
        self._positions = {name: 0.0 for name in JOINT_NAMES}
        self._velocities = {name: 0.0 for name in JOINT_NAMES}
        self._targets = {name: 0.0 for name in JOINT_NAMES}
        self._wrench = WrenchData()
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._velocity = velocity
        self._position_tolerance = position_tolerance
        self._last_step_time = time.perf_counter()

    def step(self) -> None:
        """Advance mock simulation (moves joints toward targets)."""
        current_time = time.perf_counter()
        dt = current_time - self._last_step_time
        self._last_step_time = current_time

        with self._lock:
            for name in JOINT_NAMES:
                current = self._positions[name]
                target = self._targets[name]
                diff = target - current

                if abs(diff) < self._position_tolerance:
                    self._velocities[name] = 0.0
                else:
                    # Move toward target at configured velocity
                    direction = 1.0 if diff > 0 else -1.0
                    max_move = self._velocity * dt
                    move = min(abs(diff), max_move) * direction
                    self._positions[name] = current + move
                    self._velocities[name] = self._velocity * direction

    def get_joint_state(self) -> JointState:
        """Get current joint positions and velocities."""
        with self._lock:
            return JointState(
                positions=dict(self._positions),
                velocities=dict(self._velocities),
            )

    def set_joint_targets(self, positions: dict[str, float]) -> None:
        """Set target positions for joints."""
        with self._lock:
            for name, pos in positions.items():
                if name in self._targets:
                    self._targets[name] = pos

    def get_wrench_data(self) -> WrenchData:
        """Get mock wrench data."""
        with self._lock:
            return WrenchData(
                fx=self._wrench.fx,
                fy=self._wrench.fy,
                fz=self._wrench.fz,
                tx=self._wrench.tx,
                ty=self._wrench.ty,
                tz=self._wrench.tz,
            )

    def set_wrench_data(self, wrench: WrenchData) -> None:
        """Set mock wrench data (for testing)."""
        with self._lock:
            self._wrench = wrench

    def start(self) -> None:
        """Start mock simulation loop."""
        if self._running:
            return

        self._running = True
        self._last_step_time = time.perf_counter()
        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop mock simulation loop."""
        if not self._running:
            return

        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _simulation_loop(self) -> None:
        """Run mock simulation at 50Hz (matches MockGazeboBridge)."""
        while self._running:
            self.step()
            time.sleep(0.02)  # 50Hz

    def reset(self) -> None:
        """Reset mock simulation to initial state."""
        with self._lock:
            self._positions = {name: 0.0 for name in JOINT_NAMES}
            self._velocities = {name: 0.0 for name in JOINT_NAMES}
            self._targets = {name: 0.0 for name in JOINT_NAMES}
            self._wrench = WrenchData()


# Global simulation instance (singleton pattern for shared access)
_global_simulation: Optional[SimulationInterface] = None
_global_sim_lock = threading.Lock()


def get_global_simulation(
    use_mock: bool = False, model_path: Optional[str] = None
) -> SimulationInterface:
    """Get or create the global simulation instance.

    Args:
        use_mock: If True, use MockSimulation instead of MuJoCoSimulation.
        model_path: Path to MJCF model file (only used for MuJoCo).

    Returns:
        The global simulation instance.
    """
    global _global_simulation

    with _global_sim_lock:
        if _global_simulation is None:
            if use_mock:
                logger.info("Creating global MockSimulation instance")
                _global_simulation = MockSimulation()
            else:
                logger.info("Creating global MuJoCoSimulation instance")
                _global_simulation = MuJoCoSimulation(model_path=model_path)
            _global_simulation.start()

        return _global_simulation


def shutdown_global_simulation() -> None:
    """Shutdown the global simulation instance."""
    global _global_simulation

    with _global_sim_lock:
        if _global_simulation is not None:
            _global_simulation.stop()
            _global_simulation = None
            logger.info("Global simulation shutdown complete")
