"""Tests for MuJoCoSimulation and MockSimulation.

These tests verify:
- Joint state tracking and retrieval
- Joint position control and simulated motion
- Wrench data access
- Thread safety
"""

import pytest
import threading
import time

from kettle_sim.mujoco_sim import (
    MockSimulation,
    JointState,
    WrenchData,
    JOINT_NAMES,
)


class TestJointState:
    """Tests for JointState dataclass."""

    def test_positions_stored_as_dict(self):
        """Joint positions are stored in a dict."""
        state = JointState(
            positions={"joint1": 1.0, "joint2": 2.0, "joint3": 3.0},
            velocities={"joint1": 0.1, "joint2": 0.2, "joint3": 0.3},
        )
        assert state.positions["joint1"] == 1.0
        assert state.positions["joint2"] == 2.0
        assert state.velocities["joint1"] == 0.1


class TestMockSimulation:
    """Tests for MockSimulation state machine and motion simulation."""

    def test_initial_positions_are_zero(self):
        """All joints start at zero position."""
        sim = MockSimulation()
        state = sim.get_joint_state()

        for name in JOINT_NAMES:
            assert state.positions[name] == 0.0

    def test_set_joint_targets_updates_targets(self):
        """Setting joint targets updates internal targets."""
        sim = MockSimulation()
        sim.start()
        try:
            sim.set_joint_targets({"joint1": 1.0, "joint2": 0.5})

            # Give time for motion to begin
            time.sleep(0.05)
            state = sim.get_joint_state()

            # Position should have started moving or velocity should be non-zero
            assert state.positions["joint1"] != 0.0 or state.velocities["joint1"] != 0.0
        finally:
            sim.stop()

    def test_motion_simulation_moves_toward_target(self):
        """Joint positions move toward targets over time."""
        sim = MockSimulation()
        sim.start()
        try:
            sim.set_joint_targets({"joint1": 1.0})

            positions = []
            for _ in range(10):
                state = sim.get_joint_state()
                positions.append(state.positions["joint1"])
                time.sleep(0.03)

            # Positions should be monotonically increasing toward 1.0
            for i in range(1, len(positions)):
                assert positions[i] >= positions[i - 1]
        finally:
            sim.stop()

    def test_motion_stops_at_target(self):
        """Motion stops when target is reached."""
        sim = MockSimulation(velocity=10.0)  # Fast motion for test
        sim.start()
        try:
            sim.set_joint_targets({"joint1": 0.1})

            # Wait for motion to complete
            time.sleep(0.2)

            state = sim.get_joint_state()

            # Should be at target with zero velocity
            assert abs(state.positions["joint1"] - 0.1) < sim._position_tolerance
            assert state.velocities["joint1"] == 0.0
        finally:
            sim.stop()

    def test_wrench_data_default_is_zero(self):
        """Default wrench reading is zero."""
        sim = MockSimulation()
        wrench = sim.get_wrench_data()

        assert wrench.fx == 0.0
        assert wrench.fy == 0.0
        assert wrench.fz == 0.0
        assert wrench.tx == 0.0
        assert wrench.ty == 0.0
        assert wrench.tz == 0.0

    def test_set_wrench_updates_reading(self):
        """set_wrench_data updates the force/torque reading."""
        sim = MockSimulation()
        sim.set_wrench_data(WrenchData(fz=10.5, tx=1.2))

        wrench = sim.get_wrench_data()
        assert wrench.fz == 10.5
        assert wrench.tx == 1.2

    def test_thread_safety_concurrent_access(self):
        """Simulation handles concurrent access safely."""
        sim = MockSimulation()
        sim.start()
        errors = []

        def reader():
            for _ in range(100):
                try:
                    sim.get_joint_state()
                    sim.get_wrench_data()
                except Exception as e:
                    errors.append(e)

        def writer():
            for i in range(100):
                try:
                    sim.set_joint_targets({"joint1": float(i) * 0.01})
                    sim.set_wrench_data(WrenchData(fz=float(i)))
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        sim.stop()

        assert len(errors) == 0

    def test_reset_clears_state(self):
        """reset() returns simulation to initial state."""
        sim = MockSimulation()
        sim.set_joint_targets({"joint1": 1.0})
        sim.set_wrench_data(WrenchData(fz=10.0))

        # Manually set position for test
        with sim._lock:
            sim._positions["joint1"] = 0.5

        sim.reset()

        state = sim.get_joint_state()
        wrench = sim.get_wrench_data()

        assert state.positions["joint1"] == 0.0
        assert wrench.fz == 0.0


class TestWrenchData:
    """Tests for WrenchData dataclass."""

    def test_default_values(self):
        """WrenchData defaults to all zeros."""
        wrench = WrenchData()
        assert wrench.fx == 0.0
        assert wrench.fy == 0.0
        assert wrench.fz == 0.0
        assert wrench.tx == 0.0
        assert wrench.ty == 0.0
        assert wrench.tz == 0.0

    def test_initialization_with_values(self):
        """WrenchData accepts initialization values."""
        wrench = WrenchData(
            fx=1.0,
            fy=2.0,
            fz=3.0,
            tx=0.1,
            ty=0.2,
            tz=0.3,
        )
        assert wrench.fx == 1.0
        assert wrench.fy == 2.0
        assert wrench.fz == 3.0
        assert wrench.tx == 0.1
        assert wrench.ty == 0.2
        assert wrench.tz == 0.3
