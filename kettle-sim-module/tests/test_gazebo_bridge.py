"""Tests for GazeboBridge and MockGazeboBridge.

These tests verify:
- Joint state tracking and retrieval
- Joint position commands and simulated motion
- Wrench data access
"""

import pytest
import threading
import time

from kettle_sim.gazebo_bridge import (
    MockGazeboBridge,
    JointState,
    WrenchData,
    LITE6_JOINT_NAMES,
)


class TestJointState:
    """Tests for JointState dataclass."""

    def test_get_position_list_ordering(self):
        """Position list respects provided joint name ordering."""
        state = JointState(
            positions={"joint1": 1.0, "joint3": 3.0, "joint2": 2.0}
        )
        result = state.get_position_list(["joint1", "joint2", "joint3"])
        assert result == [1.0, 2.0, 3.0]

    def test_get_position_list_missing_defaults_to_zero(self):
        """Missing joints default to 0.0 in position list."""
        state = JointState(positions={"joint1": 1.0})
        result = state.get_position_list(["joint1", "joint2"])
        assert result == [1.0, 0.0]


class TestMockGazeboBridge:
    """Tests for MockGazeboBridge state machine and motion simulation."""

    def test_initial_positions_are_zero(self):
        """All joints start at zero position."""
        bridge = MockGazeboBridge()
        state = bridge.get_joint_state()

        for name in LITE6_JOINT_NAMES:
            assert state.positions[name] == 0.0

    def test_set_joint_positions_updates_targets(self):
        """Setting joint positions updates internal targets."""
        bridge = MockGazeboBridge()
        bridge.set_joint_positions({"joint1": 1.0, "joint2": 0.5})

        # Targets are set but positions don't instantly change
        # (motion is simulated over time)
        state = bridge.get_joint_state()
        # After one get_joint_state call, some motion should occur
        assert state.positions["joint1"] != 0.0 or state.velocities["joint1"] != 0.0

    def test_set_positions_immediately_for_testing(self):
        """set_positions_immediately sets both positions and targets."""
        bridge = MockGazeboBridge()
        bridge.set_positions_immediately({"joint1": 1.5, "joint2": -0.5})

        state = bridge.get_joint_state()
        assert state.positions["joint1"] == 1.5
        assert state.positions["joint2"] == -0.5
        # Velocities should be zero since we're at target
        assert state.velocities["joint1"] == 0.0
        assert state.velocities["joint2"] == 0.0

    def test_motion_simulation_moves_toward_target(self):
        """Joint positions move toward targets over multiple calls."""
        bridge = MockGazeboBridge()
        bridge.set_joint_positions({"joint1": 1.0})

        positions = []
        for _ in range(10):
            state = bridge.get_joint_state()
            positions.append(state.positions["joint1"])

        # Positions should be monotonically increasing toward 1.0
        for i in range(1, len(positions)):
            assert positions[i] >= positions[i - 1]

    def test_motion_stops_at_target(self):
        """Motion stops when target is reached."""
        bridge = MockGazeboBridge()
        bridge._velocity = 10.0  # Fast motion for test

        bridge.set_joint_positions({"joint1": 0.1})

        # Call multiple times to let motion complete
        for _ in range(50):
            state = bridge.get_joint_state()

        # Should be at target with zero velocity
        assert abs(state.positions["joint1"] - 0.1) < bridge._position_tolerance
        assert state.velocities["joint1"] == 0.0

    def test_wrench_data_default_is_zero(self):
        """Default wrench reading is zero."""
        bridge = MockGazeboBridge()
        wrench = bridge.get_wrench()

        assert wrench.force_x == 0.0
        assert wrench.force_y == 0.0
        assert wrench.force_z == 0.0
        assert wrench.torque_x == 0.0
        assert wrench.torque_y == 0.0
        assert wrench.torque_z == 0.0

    def test_set_wrench_updates_reading(self):
        """set_wrench updates the force/torque reading."""
        bridge = MockGazeboBridge()
        bridge.set_wrench(WrenchData(force_z=10.5, torque_x=1.2))

        wrench = bridge.get_wrench()
        assert wrench.force_z == 10.5
        assert wrench.torque_x == 1.2

    def test_thread_safety_concurrent_access(self):
        """Bridge handles concurrent access safely."""
        bridge = MockGazeboBridge()
        errors = []

        def reader():
            for _ in range(100):
                try:
                    bridge.get_joint_state()
                    bridge.get_wrench()
                except Exception as e:
                    errors.append(e)

        def writer():
            for i in range(100):
                try:
                    bridge.set_joint_positions({"joint1": float(i) * 0.01})
                    bridge.set_wrench(WrenchData(force_z=float(i)))
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

        assert len(errors) == 0


class TestWrenchData:
    """Tests for WrenchData dataclass."""

    def test_default_values(self):
        """WrenchData defaults to all zeros."""
        wrench = WrenchData()
        assert wrench.force_x == 0.0
        assert wrench.force_y == 0.0
        assert wrench.force_z == 0.0
        assert wrench.torque_x == 0.0
        assert wrench.torque_y == 0.0
        assert wrench.torque_z == 0.0

    def test_initialization_with_values(self):
        """WrenchData accepts initialization values."""
        wrench = WrenchData(
            force_x=1.0,
            force_y=2.0,
            force_z=3.0,
            torque_x=0.1,
            torque_y=0.2,
            torque_z=0.3,
        )
        assert wrench.force_x == 1.0
        assert wrench.force_y == 2.0
        assert wrench.force_z == 3.0
        assert wrench.torque_x == 0.1
        assert wrench.torque_y == 0.2
        assert wrench.torque_z == 0.3
