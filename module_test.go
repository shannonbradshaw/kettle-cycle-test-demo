package kettlecycletest

import (
	"context"
	"sync"
	"testing"

	"go.viam.com/rdk/components/arm"
	toggleswitch "go.viam.com/rdk/components/switch"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
	"go.viam.com/rdk/testutils/inject"
)

func testDeps() (resource.Dependencies, *Config) {
	cfg := &Config{
		Arm:              "test-arm",
		RestingPosition:  "resting",
		PourPrepPosition: "pour-prep",
	}
	testArm := inject.NewArm("test-arm")
	testArm.IsMovingFunc = func(ctx context.Context) (bool, error) {
		return false, nil
	}
	restingSwitch := inject.NewSwitch("resting")
	restingSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
		return nil
	}
	pourPrepSwitch := inject.NewSwitch("pour-prep")
	pourPrepSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
		return nil
	}
	deps := resource.Dependencies{
		resource.NewName(arm.API, "test-arm"):           testArm,
		resource.NewName(toggleswitch.API, "resting"):   restingSwitch,
		resource.NewName(toggleswitch.API, "pour-prep"): pourPrepSwitch,
	}
	return deps, cfg
}

func newTestController(t *testing.T) *kettleCycleTestController {
	logger := logging.NewTestLogger(t)
	name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
	deps, cfg := testDeps()
	ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
	if err != nil {
		t.Fatalf("NewController failed: %v", err)
	}
	return ctrl.(*kettleCycleTestController)
}

// --- Unit: Controller Lifecycle ---

func TestNewController(t *testing.T) {
	logger := logging.NewTestLogger(t)
	name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
	deps, cfg := testDeps()

	ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
	if err != nil {
		t.Fatalf("NewController failed: %v", err)
	}
	if ctrl == nil {
		t.Fatal("NewController returned nil")
	}
	if ctrl.Name() != name {
		t.Errorf("Name() = %v, want %v", ctrl.Name(), name)
	}
}

func TestClose(t *testing.T) {
	kctrl := newTestController(t)
	err := kctrl.Close(context.Background())
	if err != nil {
		t.Errorf("Close failed: %v", err)
	}
}

func TestConfigValidate(t *testing.T) {
	t.Run("returns dependencies for valid config", func(t *testing.T) {
		cfg := &Config{
			Arm:              "my-arm",
			RestingPosition:  "resting-switch",
			PourPrepPosition: "pour-prep-switch",
		}
		deps, _, err := cfg.Validate("test")
		if err != nil {
			t.Fatalf("Validate failed: %v", err)
		}
		if len(deps) != 3 {
			t.Errorf("expected 3 dependencies, got %d", len(deps))
		}
	})

	t.Run("errors when arm missing", func(t *testing.T) {
		cfg := &Config{
			RestingPosition:  "resting-switch",
			PourPrepPosition: "pour-prep-switch",
		}
		_, _, err := cfg.Validate("test")
		if err == nil {
			t.Error("expected error for missing arm")
		}
	})

	t.Run("errors when resting_position missing", func(t *testing.T) {
		cfg := &Config{
			Arm:              "my-arm",
			PourPrepPosition: "pour-prep-switch",
		}
		_, _, err := cfg.Validate("test")
		if err == nil {
			t.Error("expected error for missing resting_position")
		}
	})

	t.Run("errors when pour_prep_position missing", func(t *testing.T) {
		cfg := &Config{
			Arm:             "my-arm",
			RestingPosition: "resting-switch",
		}
		_, _, err := cfg.Validate("test")
		if err == nil {
			t.Error("expected error for missing pour_prep_position")
		}
	})
}

// --- Unit: execute_cycle State ---

func TestExecuteCycle_Standalone_NoCycleCountTracked(t *testing.T) {
	kctrl := newTestController(t)

	// No active trial
	if kctrl.activeTrial != nil {
		t.Fatal("expected no active trial")
	}

	// Execute cycle
	_, err := kctrl.handleExecuteCycle(context.Background())
	if err != nil {
		t.Fatalf("handleExecuteCycle failed: %v", err)
	}

	// State remains idle, no cycle count tracked
	state := kctrl.GetState()
	if state["state"] != "idle" {
		t.Errorf("expected state=idle, got %v", state["state"])
	}
	if state["cycle_count"] != 0 {
		t.Errorf("expected cycle_count=0 (standalone), got %v", state["cycle_count"])
	}
}

func TestExecuteCycle_DuringTrial_IncrementsCycleCount(t *testing.T) {
	kctrl := newTestController(t)

	// Manually set up trial state (without starting background loop)
	// This tests the cycle count increment logic in isolation
	kctrl.mu.Lock()
	kctrl.activeTrial = &trialState{
		trialID: "test-trial",
		stopCh:  make(chan struct{}),
	}
	kctrl.mu.Unlock()

	state := kctrl.GetState()
	if state["cycle_count"] != 0 {
		t.Fatalf("expected initial cycle_count=0, got %v", state["cycle_count"])
	}

	// Execute cycle
	_, err := kctrl.handleExecuteCycle(context.Background())
	if err != nil {
		t.Fatalf("handleExecuteCycle failed: %v", err)
	}

	// Verify cycle_count = 1, lastCycleAt updated
	state = kctrl.GetState()
	if state["cycle_count"] != 1 {
		t.Errorf("expected cycle_count=1, got %v", state["cycle_count"])
	}
	if state["last_cycle_at"] == "" {
		t.Error("expected last_cycle_at to be set")
	}

	// Cleanup - manually clear trial
	kctrl.mu.Lock()
	kctrl.activeTrial = nil
	kctrl.mu.Unlock()
}

// --- Unit: Thread Safety ---

func TestController_ThreadSafety(t *testing.T) {
	kctrl := newTestController(t)

	// Start active trial
	kctrl.handleStart()

	// Spawn goroutines doing concurrent operations
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 10; j++ {
				kctrl.GetState()
				kctrl.handleStatus()
			}
		}()
	}

	wg.Wait()
	kctrl.handleStop()
}

// --- Integration: Trial State Machine ---

func TestTrial_StartWhileRunning_Errors(t *testing.T) {
	kctrl := newTestController(t)

	kctrl.handleStart()
	_, err := kctrl.handleStart()
	if err == nil {
		t.Error("expected error when starting already-running trial")
	}
	kctrl.handleStop()
}

func TestTrial_StopWhileIdle_Errors(t *testing.T) {
	kctrl := newTestController(t)

	_, err := kctrl.handleStop()
	if err == nil {
		t.Error("expected error when stopping with no active trial")
	}
}

func TestTrial_Start_InitializesState(t *testing.T) {
	kctrl := newTestController(t)

	// Before start: no active trial
	if kctrl.activeTrial != nil {
		t.Error("expected nil activeTrial before start")
	}

	result, err := kctrl.handleStart()
	if err != nil {
		t.Fatalf("handleStart failed: %v", err)
	}

	// After start: active trial exists with initialized channels
	if kctrl.activeTrial == nil {
		t.Fatal("expected activeTrial after start")
	}
	if kctrl.activeTrial.stopCh == nil {
		t.Error("expected stopCh to be initialized")
	}
	if kctrl.activeTrial.trialID == "" {
		t.Error("expected trialID to be set")
	}
	if result["trial_id"] != kctrl.activeTrial.trialID {
		t.Error("returned trial_id doesn't match activeTrial.trialID")
	}

	kctrl.handleStop()
}

func TestTrial_Stop_CleansState(t *testing.T) {
	kctrl := newTestController(t)

	kctrl.handleStart()
	trialID := kctrl.activeTrial.trialID

	result, err := kctrl.handleStop()
	if err != nil {
		t.Fatalf("handleStop failed: %v", err)
	}

	// After stop: no active trial
	if kctrl.activeTrial != nil {
		t.Error("expected nil activeTrial after stop")
	}
	if result["trial_id"] != trialID {
		t.Error("expected trial_id in stop result")
	}
}

func TestTrial_CycleCountStartsAtZero(t *testing.T) {
	kctrl := newTestController(t)

	// Start trial, immediately check status
	kctrl.handleStart()
	state := kctrl.GetState()

	// Verify cycle_count = 0
	if state["cycle_count"] != 0 {
		t.Errorf("expected cycle_count=0 at start, got %v", state["cycle_count"])
	}
	if state["state"] != "running" {
		t.Errorf("expected state=running, got %v", state["state"])
	}

	kctrl.handleStop()
}

func TestTrial_StatusReturnsTrialState(t *testing.T) {
	kctrl := newTestController(t)

	// Idle state
	status, _ := kctrl.handleStatus()
	if status["state"] != "idle" {
		t.Errorf("expected state=idle, got %v", status["state"])
	}

	// Running state
	kctrl.handleStart()
	status, _ = kctrl.handleStatus()
	if status["state"] != "running" {
		t.Errorf("expected state=running, got %v", status["state"])
	}

	kctrl.handleStop()
}
