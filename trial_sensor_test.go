package kettlecycletest

import (
	"context"
	"testing"

	"go.viam.com/rdk/components/arm"
	"go.viam.com/rdk/components/sensor"
	toggleswitch "go.viam.com/rdk/components/switch"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
	"go.viam.com/rdk/testutils/inject"
)

func TestTrialSensorConfig(t *testing.T) {
	t.Run("requires controller", func(t *testing.T) {
		cfg := &TrialSensorConfig{}
		_, _, err := cfg.Validate("test")
		if err == nil {
			t.Error("expected error for missing controller")
		}
	})

	t.Run("valid config returns controller as dependency", func(t *testing.T) {
		cfg := &TrialSensorConfig{
			Controller: "my-controller",
		}
		deps, _, err := cfg.Validate("test")
		if err != nil {
			t.Fatalf("Validate failed: %v", err)
		}
		if len(deps) != 1 {
			t.Errorf("expected 1 dependency, got %d", len(deps))
		}
	})
}

func TestTrialSensor_Constructor(t *testing.T) {
	t.Run("fails if controller not found", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		name := resource.NewName(sensor.API, "test-sensor")
		rawConf := resource.Config{
			Name:                name.Name,
			API:                 sensor.API,
			Model:               TrialSensor,
			ConvertedAttributes: &TrialSensorConfig{Controller: "missing-controller"},
		}

		_, err := newTrialSensor(context.Background(), resource.Dependencies{}, rawConf, logger)
		if err == nil {
			t.Error("expected error when controller not found")
		}
	})

	t.Run("succeeds with valid controller", func(t *testing.T) {
		logger := logging.NewTestLogger(t)
		sensorName := resource.NewName(sensor.API, "test-sensor")

		// Create a real controller
		testArm := inject.NewArm("test-arm")
		testArm.IsMovingFunc = func(ctx context.Context) (bool, error) {
			return false, nil
		}
		deps := resource.Dependencies{
			resource.NewName(arm.API, "test-arm"):           testArm,
			resource.NewName(toggleswitch.API, "resting"):   inject.NewSwitch("resting"),
			resource.NewName(toggleswitch.API, "pour-prep"): inject.NewSwitch("pour-prep"),
		}
		cfg := &Config{
			Arm:              "test-arm",
			RestingPosition:  "resting",
			PourPrepPosition: "pour-prep",
		}
		ctrlName := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test-controller")
		ctrl, err := NewController(context.Background(), deps, ctrlName, cfg, logger)
		if err != nil {
			t.Fatalf("NewController failed: %v", err)
		}

		// Now create sensor with controller as dependency
		sensorDeps := resource.Dependencies{
			ctrlName: ctrl,
		}
		rawConf := resource.Config{
			Name:                sensorName.Name,
			API:                 sensor.API,
			Model:               TrialSensor,
			ConvertedAttributes: &TrialSensorConfig{Controller: "test-controller"},
		}

		s, err := newTrialSensor(context.Background(), sensorDeps, rawConf, logger)
		if err != nil {
			t.Fatalf("newTrialSensor failed: %v", err)
		}
		if s == nil {
			t.Fatal("expected non-nil sensor")
		}
	})
}

func TestTrialSensor_ReadingsMatchesControllerState(t *testing.T) {
	// Documentation test: proves Readings() returns exactly what GetState() returns
	logger := logging.NewTestLogger(t)

	// 1. Create real controller with mock dependencies
	testArm := inject.NewArm("test-arm")
	testArm.IsMovingFunc = func(ctx context.Context) (bool, error) {
		return false, nil
	}
	deps := resource.Dependencies{
		resource.NewName(arm.API, "test-arm"):           testArm,
		resource.NewName(toggleswitch.API, "resting"):   inject.NewSwitch("resting"),
		resource.NewName(toggleswitch.API, "pour-prep"): inject.NewSwitch("pour-prep"),
	}
	cfg := &Config{
		Arm:              "test-arm",
		RestingPosition:  "resting",
		PourPrepPosition: "pour-prep",
	}
	ctrlName := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test-controller")
	ctrl, err := NewController(context.Background(), deps, ctrlName, cfg, logger)
	if err != nil {
		t.Fatalf("NewController failed: %v", err)
	}

	// Create sensor wrapping controller
	sensorName := resource.NewName(sensor.API, "test-sensor")
	sensorDeps := resource.Dependencies{
		ctrlName: ctrl,
	}
	rawConf := resource.Config{
		Name:                sensorName.Name,
		API:                 sensor.API,
		Model:               TrialSensor,
		ConvertedAttributes: &TrialSensorConfig{Controller: "test-controller"},
	}
	s, err := newTrialSensor(context.Background(), sensorDeps, rawConf, logger)
	if err != nil {
		t.Fatalf("newTrialSensor failed: %v", err)
	}

	// 2. Inject known state (start trial)
	kctrl := ctrl.(*kettleCycleTestController)
	kctrl.handleStart()

	// 3. Call sensor.Readings()
	readings, err := s.Readings(context.Background(), nil)
	if err != nil {
		t.Fatalf("Readings failed: %v", err)
	}

	// 4. Call controller.GetState()
	state := kctrl.GetState()

	// 5. Assert they are identical
	if readings["state"] != state["state"] {
		t.Errorf("state mismatch: readings=%v, controller=%v", readings["state"], state["state"])
	}
	if readings["trial_id"] != state["trial_id"] {
		t.Errorf("trial_id mismatch: readings=%v, controller=%v", readings["trial_id"], state["trial_id"])
	}
	if readings["cycle_count"] != state["cycle_count"] {
		t.Errorf("cycle_count mismatch: readings=%v, controller=%v", readings["cycle_count"], state["cycle_count"])
	}
	if readings["should_sync"] != state["should_sync"] {
		t.Errorf("should_sync mismatch: readings=%v, controller=%v", readings["should_sync"], state["should_sync"])
	}

	// Cleanup
	kctrl.handleStop()
}
