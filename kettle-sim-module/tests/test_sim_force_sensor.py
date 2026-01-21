"""Tests for SimulatedForceSensor.

These tests verify:
- Capture state machine transitions (idle -> waiting -> active -> idle)
- Trial metadata handling (trial_id, cycle_count, should_sync)
- Timeout handling
- Sample buffer behavior
"""

import pytest
import asyncio
import time
import threading

from kettle_sim.sim_force_sensor import SimulatedForceSensor, CaptureState
from kettle_sim.mujoco_sim import MockSimulation, WrenchData


@pytest.fixture
def sensor():
    """Create a sensor with mock simulation for testing."""
    s = SimulatedForceSensor("test-force-sensor")
    # Create and start mock simulation
    s._sim = MockSimulation()
    s._sim.start()
    s._sample_rate_hz = 100  # Fast sampling for tests
    s._buffer_size = 10
    s._zero_threshold = 5.0
    s._capture_timeout = 5.0
    s._running = True
    s._stop_event = threading.Event()
    s._sampling_thread = threading.Thread(target=s._sampling_loop, daemon=True)
    s._sampling_thread.start()
    yield s
    s._cleanup()
    s._sim.stop()


class TestCaptureStateMachine:
    """Tests for capture state machine transitions."""

    def test_initial_state_is_idle(self, sensor):
        """Sensor starts in idle state."""
        assert sensor._state == CaptureState.IDLE

    def test_start_capture_transitions_to_waiting(self, sensor):
        """start_capture moves from idle to waiting state."""
        result = sensor._handle_start_capture({})

        assert result["status"] == "waiting"
        assert sensor._state == CaptureState.WAITING

    def test_start_capture_while_not_idle_errors(self, sensor):
        """start_capture fails if not in idle state."""
        sensor._handle_start_capture({})  # Move to waiting

        with pytest.raises(RuntimeError, match="Capture already in progress"):
            sensor._handle_start_capture({})

    def test_first_nonzero_reading_transitions_to_active(self, sensor):
        """First reading above threshold moves from waiting to active."""
        sensor._handle_start_capture({})
        assert sensor._state == CaptureState.WAITING

        # Simulate force above threshold
        sensor._sim.set_wrench_data(WrenchData(fz=10.0))

        # Wait for sampling loop to process
        time.sleep(0.1)

        assert sensor._state == CaptureState.ACTIVE

    def test_end_capture_transitions_to_idle(self, sensor):
        """end_capture returns to idle state."""
        sensor._handle_start_capture({})

        result = sensor._handle_end_capture()

        assert result["status"] == "completed"
        assert sensor._state == CaptureState.IDLE

    def test_end_capture_when_idle_errors(self, sensor):
        """end_capture fails if already idle."""
        with pytest.raises(RuntimeError, match="No capture in progress"):
            sensor._handle_end_capture()


class TestTrialMetadata:
    """Tests for trial metadata handling."""

    def test_start_capture_stores_trial_id(self, sensor):
        """start_capture stores provided trial_id."""
        sensor._handle_start_capture({
            "trial_id": "test-trial-123",
            "cycle_count": 5,
        })

        assert sensor._trial_id == "test-trial-123"
        assert sensor._cycle_count == 5

    def test_end_capture_returns_trial_metadata(self, sensor):
        """end_capture returns the trial metadata."""
        sensor._handle_start_capture({
            "trial_id": "test-trial-456",
            "cycle_count": 10,
        })

        result = sensor._handle_end_capture()

        assert result["trial_id"] == "test-trial-456"
        assert result["cycle_count"] == 10

    def test_end_capture_clears_trial_metadata(self, sensor):
        """end_capture clears trial metadata."""
        sensor._handle_start_capture({"trial_id": "test"})
        sensor._handle_end_capture()

        assert sensor._trial_id == ""
        assert sensor._cycle_count == 0

    @pytest.mark.asyncio
    async def test_should_sync_true_during_capture(self, sensor):
        """should_sync is true when trial_id is set."""
        sensor._handle_start_capture({"trial_id": "sync-test"})

        readings = await sensor.get_readings()

        assert readings["should_sync"] is True

    @pytest.mark.asyncio
    async def test_should_sync_false_when_idle(self, sensor):
        """should_sync is false when no active trial."""
        readings = await sensor.get_readings()

        assert readings["should_sync"] is False


class TestSampleBuffer:
    """Tests for sample buffer behavior."""

    def test_samples_collected_during_active_capture(self, sensor):
        """Samples are collected when in active state."""
        sensor._handle_start_capture({})
        sensor._sim.set_wrench_data(WrenchData(fz=10.0))

        # Wait for samples to be collected
        time.sleep(0.15)

        result = sensor._handle_end_capture()
        assert result["sample_count"] > 0

    def test_buffer_rolls_when_full(self, sensor):
        """Buffer maintains max size by dropping oldest samples."""
        sensor._buffer_size = 5
        sensor._handle_start_capture({})
        sensor._sim.set_wrench_data(WrenchData(fz=10.0))

        # Wait for buffer to fill and roll
        time.sleep(0.2)

        with sensor._lock:
            assert len(sensor._samples) <= 5

    def test_max_force_calculated_correctly(self, sensor):
        """max_force returns highest sample value."""
        sensor._handle_start_capture({})
        sensor._state = CaptureState.ACTIVE  # Skip waiting
        sensor._samples = [5.0, 15.0, 10.0, 8.0]

        result = sensor._handle_end_capture()

        assert result["max_force"] == 15.0

    def test_samples_cleared_on_start_capture(self, sensor):
        """Samples are cleared when starting new capture."""
        # Manually add some samples
        sensor._samples = [1.0, 2.0, 3.0]

        sensor._handle_start_capture({})

        assert len(sensor._samples) == 0


class TestCaptureTimeout:
    """Tests for capture timeout handling."""

    def test_timeout_resets_state_to_idle(self, sensor):
        """Capture timeout resets state to idle."""
        sensor._capture_timeout = 0.1  # Short timeout for test
        sensor._handle_start_capture({"trial_id": "timeout-test"})

        # Wait for timeout
        time.sleep(0.2)

        assert sensor._state == CaptureState.IDLE
        assert sensor._trial_id == ""

    def test_end_capture_cancels_timeout(self, sensor):
        """end_capture cancels the timeout timer."""
        sensor._capture_timeout = 10.0  # Long timeout
        sensor._handle_start_capture({})

        assert sensor._timeout_timer is not None

        sensor._handle_end_capture()

        # Timer should be cancelled (not None but cancelled)
        assert sensor._timeout_timer is None or not sensor._timeout_timer.is_alive()


class TestDoCommand:
    """Tests for DoCommand dispatch."""

    @pytest.mark.asyncio
    async def test_do_command_start_capture(self, sensor):
        """DoCommand routes start_capture correctly."""
        result = await sensor.do_command({"command": "start_capture"})

        assert result["status"] == "waiting"

    @pytest.mark.asyncio
    async def test_do_command_end_capture(self, sensor):
        """DoCommand routes end_capture correctly."""
        await sensor.do_command({"command": "start_capture"})
        result = await sensor.do_command({"command": "end_capture"})

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_do_command_unknown_errors(self, sensor):
        """DoCommand raises error for unknown command."""
        with pytest.raises(ValueError, match="Unknown command"):
            await sensor.do_command({"command": "invalid"})

    @pytest.mark.asyncio
    async def test_do_command_missing_command_errors(self, sensor):
        """DoCommand raises error when command field missing."""
        with pytest.raises(ValueError, match="Missing 'command'"):
            await sensor.do_command({})


class TestGetReadings:
    """Tests for get_readings output."""

    @pytest.mark.asyncio
    async def test_readings_include_wrench_data(self, sensor):
        """get_readings includes force/torque data."""
        sensor._sim.set_wrench_data(WrenchData(fx=1.0, fy=2.0, fz=3.0, tx=0.1, ty=0.2, tz=0.3))

        readings = await sensor.get_readings()

        assert readings["fx"] == 1.0
        assert readings["fy"] == 2.0
        assert readings["fz"] == 3.0
        assert readings["tx"] == 0.1
        assert readings["ty"] == 0.2
        assert readings["tz"] == 0.3

    @pytest.mark.asyncio
    async def test_readings_include_capture_state(self, sensor):
        """get_readings includes capture state."""
        readings = await sensor.get_readings()

        assert readings["capture_state"] == "idle"

        sensor._handle_start_capture({})
        readings = await sensor.get_readings()

        assert readings["capture_state"] == "waiting"
