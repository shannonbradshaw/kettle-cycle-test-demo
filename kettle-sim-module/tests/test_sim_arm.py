"""Tests for SimulatedArm.

These tests verify:
- Joint position retrieval and conversion (rad ↔ deg)
- Joint limit validation
- is_moving detection based on velocity and target distance
- Stop behavior
"""

import pytest
import asyncio
import math

from viam.components.arm import JointPositions

from kettle_sim.sim_arm import SimulatedArm, LITE6_JOINT_NAMES
from kettle_sim.gazebo_bridge import MockGazeboBridge


@pytest.fixture
def arm():
    """Create an arm with mock bridge for testing."""
    a = SimulatedArm("test-arm")
    a._bridge = MockGazeboBridge()
    a._joint_names = LITE6_JOINT_NAMES
    a._position_tolerance = 0.05
    a._move_timeout = 5.0
    yield a


class TestJointPositionRetrieval:
    """Tests for get_joint_positions."""

    @pytest.mark.asyncio
    async def test_get_joint_positions_returns_degrees(self, arm):
        """get_joint_positions returns positions in degrees."""
        # Set positions in radians via mock
        arm._bridge.set_positions_immediately({
            "joint1": math.pi / 2,  # 90 degrees
            "joint2": math.pi / 4,  # 45 degrees
        })

        positions = await arm.get_joint_positions()

        assert abs(positions.values[0] - 90.0) < 0.1
        assert abs(positions.values[1] - 45.0) < 0.1

    @pytest.mark.asyncio
    async def test_get_joint_positions_all_six_joints(self, arm):
        """get_joint_positions returns all six joint values."""
        positions = await arm.get_joint_positions()

        assert len(positions.values) == 6


class TestJointLimitValidation:
    """Tests for joint limit validation in move_to_joint_positions."""

    @pytest.mark.asyncio
    async def test_position_within_limits_accepted(self, arm):
        """Positions within limits are accepted."""
        # Joint1 limits: -360 to 360 degrees
        positions = JointPositions(values=[90, 0, 45, 0, 0, 0])

        # Should not raise
        await arm.move_to_joint_positions(positions)

    @pytest.mark.asyncio
    async def test_position_exceeding_upper_limit_rejected(self, arm):
        """Position exceeding upper limit raises ValueError."""
        # Joint2 upper limit is ~120 degrees
        positions = JointPositions(values=[0, 150, 0, 0, 0, 0])

        with pytest.raises(ValueError, match="out of range"):
            await arm.move_to_joint_positions(positions)

    @pytest.mark.asyncio
    async def test_position_below_lower_limit_rejected(self, arm):
        """Position below lower limit raises ValueError."""
        # Joint2 lower limit is ~-118 degrees
        positions = JointPositions(values=[0, -150, 0, 0, 0, 0])

        with pytest.raises(ValueError, match="out of range"):
            await arm.move_to_joint_positions(positions)

    @pytest.mark.asyncio
    async def test_wrong_number_of_positions_rejected(self, arm):
        """Wrong number of positions raises ValueError."""
        positions = JointPositions(values=[0, 0, 0])  # Only 3 instead of 6

        with pytest.raises(ValueError, match="Expected 6 joint positions"):
            await arm.move_to_joint_positions(positions)


class TestIsMoving:
    """Tests for is_moving detection."""

    @pytest.mark.asyncio
    async def test_is_moving_false_when_at_target(self, arm):
        """is_moving returns False when at target position."""
        # Set position and target to same value
        arm._bridge.set_positions_immediately({"joint1": 0.5})

        result = await arm.is_moving()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_moving_true_when_velocity_nonzero(self, arm):
        """is_moving returns True when velocity is significant."""
        # Set a target far from current position
        arm._bridge.set_joint_positions({"joint1": 2.0})
        arm._target_positions = {"joint1": 2.0}

        # Get state to trigger motion simulation
        arm._bridge.get_joint_state()

        result = await arm.is_moving()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_moving_true_when_not_at_target(self, arm):
        """is_moving returns True when position differs from target."""
        arm._bridge.set_positions_immediately({"joint1": 0.0})
        arm._target_positions = {"joint1": 1.0}  # Target differs

        result = await arm.is_moving()

        assert result is True


class TestStop:
    """Tests for stop behavior."""

    @pytest.mark.asyncio
    async def test_stop_clears_target_positions(self, arm):
        """stop clears the target positions."""
        arm._target_positions = {"joint1": 1.0, "joint2": 2.0}

        await arm.stop()

        assert arm._target_positions == {}

    @pytest.mark.asyncio
    async def test_stop_commands_current_position(self, arm):
        """stop commands joints to hold current position."""
        arm._bridge.set_positions_immediately({"joint1": 0.5})

        await arm.stop()

        # After stop, target should match current
        state = arm._bridge.get_joint_state()
        assert state.positions["joint1"] == 0.5


class TestMoveToJointPositions:
    """Tests for move_to_joint_positions behavior."""

    @pytest.mark.asyncio
    async def test_move_stores_target_positions(self, arm):
        """move_to_joint_positions stores targets for is_moving check."""
        # Use fast motion for test
        arm._bridge._velocity = 100.0
        positions = JointPositions(values=[10, 0, 0, 0, 0, 0])

        await arm.move_to_joint_positions(positions)

        # Move completes when at target, so target should still be stored
        expected_rad = math.radians(10)
        assert abs(arm._target_positions.get("joint1", 0) - expected_rad) < 0.1

    @pytest.mark.asyncio
    async def test_move_timeout_raises_error(self, arm):
        """move_to_joint_positions raises TimeoutError if target not reached."""
        arm._move_timeout = 0.1  # Very short timeout
        arm._bridge._velocity = 0.001  # Very slow motion

        positions = JointPositions(values=[180, 0, 0, 0, 0, 0])

        with pytest.raises(TimeoutError):
            await arm.move_to_joint_positions(positions)


class TestArmNotInitialized:
    """Tests for error handling when arm not initialized."""

    @pytest.mark.asyncio
    async def test_get_positions_without_bridge_errors(self):
        """get_joint_positions raises error without bridge."""
        arm = SimulatedArm("test")
        # Don't set bridge

        with pytest.raises(RuntimeError, match="not initialized"):
            await arm.get_joint_positions()

    @pytest.mark.asyncio
    async def test_move_without_bridge_errors(self):
        """move_to_joint_positions raises error without bridge."""
        arm = SimulatedArm("test")

        with pytest.raises(RuntimeError, match="not initialized"):
            await arm.move_to_joint_positions(JointPositions(values=[0]*6))
