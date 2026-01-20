package kettlecycletest

import (
	"context"
	"errors"
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
	deps := resource.Dependencies{
		resource.NewName(arm.API, "test-arm"):           inject.NewArm("test-arm"),
		resource.NewName(toggleswitch.API, "resting"):   inject.NewSwitch("resting"),
		resource.NewName(toggleswitch.API, "pour-prep"): inject.NewSwitch("pour-prep"),
	}
	return deps, cfg
}

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

func TestDoCommand(t *testing.T) {
	logger := logging.NewTestLogger(t)
	name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
	deps, cfg := testDeps()

	ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
	if err != nil {
		t.Fatalf("NewController failed: %v", err)
	}

	_, err = ctrl.(*kettleCycleTestController).DoCommand(context.Background(), map[string]interface{}{})
	if err == nil {
		t.Error("DoCommand should return error for missing command")
	}
}

func TestClose(t *testing.T) {
	logger := logging.NewTestLogger(t)
	name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
	deps, cfg := testDeps()

	ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
	if err != nil {
		t.Fatalf("NewController failed: %v", err)
	}

	err = ctrl.(*kettleCycleTestController).Close(context.Background())
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

		// Should return arm and both switch names as required dependencies
		if len(deps) != 3 {
			t.Errorf("expected 3 dependencies, got %d", len(deps))
		}

		// Check all dependencies are present
		found := map[string]bool{}
		for _, dep := range deps {
			found[dep] = true
		}
		if !found["my-arm"] {
			t.Error("missing my-arm in dependencies")
		}
		if !found["resting-switch"] {
			t.Error("missing resting-switch in dependencies")
		}
		if !found["pour-prep-switch"] {
			t.Error("missing pour-prep-switch in dependencies")
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

func TestTrialLifecycle(t *testing.T) {
	t.Run("start creates active trial with stop channel", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
		deps, cfg := testDeps()

		ctrl, _ := NewController(context.Background(), deps, name, cfg, logger)
		kctrl := ctrl.(*kettleCycleTestController)

		// Before start: no active trial
		if kctrl.activeTrial != nil {
			t.Error("expected nil activeTrial before start")
		}

		result, err := kctrl.DoCommand(context.Background(), map[string]interface{}{
			"command": "start",
		})
		if err != nil {
			t.Fatalf("start failed: %v", err)
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
			t.Errorf("returned trial_id doesn't match activeTrial.trialID")
		}

		// Clean up
		kctrl.DoCommand(context.Background(), map[string]interface{}{"command": "stop"})
	})

	t.Run("stop clears active trial", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
		deps, cfg := testDeps()

		ctrl, _ := NewController(context.Background(), deps, name, cfg, logger)
		kctrl := ctrl.(*kettleCycleTestController)

		kctrl.DoCommand(context.Background(), map[string]interface{}{"command": "start"})

		result, err := kctrl.DoCommand(context.Background(), map[string]interface{}{
			"command": "stop",
		})
		if err != nil {
			t.Fatalf("stop failed: %v", err)
		}

		// After stop: no active trial
		if kctrl.activeTrial != nil {
			t.Error("expected nil activeTrial after stop")
		}
		if result["trial_id"] == "" {
			t.Error("expected trial_id in stop result")
		}
	})

	t.Run("start when already running returns error", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
		deps, cfg := testDeps()

		ctrl, _ := NewController(context.Background(), deps, name, cfg, logger)
		kctrl := ctrl.(*kettleCycleTestController)

		kctrl.DoCommand(context.Background(), map[string]interface{}{"command": "start"})

		_, err := kctrl.DoCommand(context.Background(), map[string]interface{}{
			"command": "start",
		})
		if err == nil {
			t.Error("expected error when starting already-running trial")
		}

		// Clean up
		kctrl.DoCommand(context.Background(), map[string]interface{}{"command": "stop"})
	})

	t.Run("stop when idle returns error", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
		deps, cfg := testDeps()

		ctrl, _ := NewController(context.Background(), deps, name, cfg, logger)
		kctrl := ctrl.(*kettleCycleTestController)

		_, err := kctrl.DoCommand(context.Background(), map[string]interface{}{
			"command": "stop",
		})
		if err == nil {
			t.Error("expected error when stopping with no active trial")
		}
	})

	t.Run("status returns trial state", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")
		deps, cfg := testDeps()

		ctrl, _ := NewController(context.Background(), deps, name, cfg, logger)
		kctrl := ctrl.(*kettleCycleTestController)

		// Idle state
		status, _ := kctrl.DoCommand(context.Background(), map[string]interface{}{
			"command": "status",
		})
		if status["state"] != "idle" {
			t.Errorf("expected state=idle, got %v", status["state"])
		}

		// Running state
		kctrl.DoCommand(context.Background(), map[string]interface{}{"command": "start"})
		status, _ = kctrl.DoCommand(context.Background(), map[string]interface{}{
			"command": "status",
		})
		if status["state"] != "running" {
			t.Errorf("expected state=running, got %v", status["state"])
		}

		// Clean up
		kctrl.DoCommand(context.Background(), map[string]interface{}{"command": "stop"})
	})
}

func TestExecuteCycle(t *testing.T) {
	t.Run("moves to pour_prep then back to resting", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")

		var restingCalls, pourPrepCalls []uint32

		restingSwitch := inject.NewSwitch("resting")
		restingSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
			restingCalls = append(restingCalls, position)
			return nil
		}

		pourPrepSwitch := inject.NewSwitch("pour-prep")
		pourPrepSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
			pourPrepCalls = append(pourPrepCalls, position)
			return nil
		}

		deps := resource.Dependencies{
			resource.NewName(arm.API, "test-arm"):           inject.NewArm("test-arm"),
			resource.NewName(toggleswitch.API, "resting"):   restingSwitch,
			resource.NewName(toggleswitch.API, "pour-prep"): pourPrepSwitch,
		}

		cfg := &Config{
			Arm:              "test-arm",
			RestingPosition:  "resting",
			PourPrepPosition: "pour-prep",
		}

		ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
		if err != nil {
			t.Fatalf("NewController failed: %v", err)
		}

		result, err := ctrl.(*kettleCycleTestController).DoCommand(context.Background(), map[string]interface{}{
			"command": "execute_cycle",
		})
		if err != nil {
			t.Fatalf("execute_cycle failed: %v", err)
		}

		// Verify pour_prep switch was triggered (position 2)
		if len(pourPrepCalls) != 1 || pourPrepCalls[0] != 2 {
			t.Errorf("pour_prep switch: expected [2], got %v", pourPrepCalls)
		}

		// Verify resting switch was triggered (position 2)
		if len(restingCalls) != 1 || restingCalls[0] != 2 {
			t.Errorf("resting switch: expected [2], got %v", restingCalls)
		}

		// Verify success response
		if result["status"] != "completed" {
			t.Errorf("expected status=completed, got %v", result["status"])
		}
	})

	t.Run("returns error when pour_prep switch fails", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")

		var restingCalls []uint32

		restingSwitch := inject.NewSwitch("resting")
		restingSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
			restingCalls = append(restingCalls, position)
			return nil
		}

		pourPrepSwitch := inject.NewSwitch("pour-prep")
		pourPrepSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
			return errors.New("switch error")
		}

		deps := resource.Dependencies{
			resource.NewName(arm.API, "test-arm"):           inject.NewArm("test-arm"),
			resource.NewName(toggleswitch.API, "resting"):   restingSwitch,
			resource.NewName(toggleswitch.API, "pour-prep"): pourPrepSwitch,
		}

		cfg := &Config{
			Arm:              "test-arm",
			RestingPosition:  "resting",
			PourPrepPosition: "pour-prep",
		}

		ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
		if err != nil {
			t.Fatalf("NewController failed: %v", err)
		}

		_, err = ctrl.(*kettleCycleTestController).DoCommand(context.Background(), map[string]interface{}{
			"command": "execute_cycle",
		})
		if err == nil {
			t.Error("expected error when pour_prep switch fails")
		}

		// Resting switch should NOT have been called since pour_prep failed
		if len(restingCalls) != 0 {
			t.Errorf("resting switch should not be called after pour_prep fails, got %v calls", len(restingCalls))
		}
	})

	t.Run("returns error when resting switch fails", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")

		var pourPrepCalls []uint32

		restingSwitch := inject.NewSwitch("resting")
		restingSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
			return errors.New("switch error")
		}

		pourPrepSwitch := inject.NewSwitch("pour-prep")
		pourPrepSwitch.SetPositionFunc = func(ctx context.Context, position uint32, extra map[string]interface{}) error {
			pourPrepCalls = append(pourPrepCalls, position)
			return nil
		}

		deps := resource.Dependencies{
			resource.NewName(arm.API, "test-arm"):           inject.NewArm("test-arm"),
			resource.NewName(toggleswitch.API, "resting"):   restingSwitch,
			resource.NewName(toggleswitch.API, "pour-prep"): pourPrepSwitch,
		}

		cfg := &Config{
			Arm:              "test-arm",
			RestingPosition:  "resting",
			PourPrepPosition: "pour-prep",
		}

		ctrl, err := NewController(context.Background(), deps, name, cfg, logger)
		if err != nil {
			t.Fatalf("NewController failed: %v", err)
		}

		_, err = ctrl.(*kettleCycleTestController).DoCommand(context.Background(), map[string]interface{}{
			"command": "execute_cycle",
		})
		if err == nil {
			t.Error("expected error when resting switch fails")
		}

		// Pour prep should have been called before resting failed
		if len(pourPrepCalls) != 1 {
			t.Errorf("pour_prep switch should have been called once, got %v", len(pourPrepCalls))
		}
	})
}
