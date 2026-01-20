package kettlecycletest

import (
	"context"
	"sync"
	"testing"
	"time"

	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
)

func TestForceSensorConfig(t *testing.T) {
	t.Run("requires load_cell", func(t *testing.T) {
		cfg := &ForceSensorConfig{}
		_, _, err := cfg.Validate("test")
		if err == nil {
			t.Error("expected error for missing load_cell")
		}
	})

	t.Run("valid config returns load_cell as dependency", func(t *testing.T) {
		cfg := &ForceSensorConfig{
			LoadCell: "my-adc-sensor",
		}
		deps, _, err := cfg.Validate("test")
		if err != nil {
			t.Fatalf("Validate failed: %v", err)
		}
		if len(deps) != 1 || deps[0] != "my-adc-sensor" {
			t.Errorf("expected [my-adc-sensor], got %v", deps)
		}
	})

	t.Run("use_mock_curve is optional flag", func(t *testing.T) {
		cfg := &ForceSensorConfig{
			LoadCell:     "my-adc-sensor",
			UseMockCurve: true,
		}
		deps, _, err := cfg.Validate("test")
		if err != nil {
			t.Fatalf("Validate failed: %v", err)
		}
		// Still declares dependency even with mock (for config validation)
		if len(deps) != 1 {
			t.Errorf("expected 1 dependency, got %d", len(deps))
		}
	})
}

// newTestForceSensor creates a force sensor with mock reader for testing
func newTestForceSensor(t *testing.T) *forceSensor {
	return &forceSensor{
		name:           resource.NewName(resource.APINamespaceRDK.WithComponentType("sensor"), "test"),
		logger:         logging.NewTestLogger(t),
		reader:         newMockForceReader(),
		sampleRateHz:   100,
		bufferSize:     100,
		zeroThreshold:  5.0,
		captureTimeout: 10 * time.Second,
		samples:        make([]float64, 0, 100),
		state:          captureIdle,
	}
}

func TestForceSensor_StateMachine(t *testing.T) {
	t.Run("starts in idle state", func(t *testing.T) {
		fs := newTestForceSensor(t)
		readings, _ := fs.Readings(context.Background(), nil)
		if readings["capture_state"] != "idle" {
			t.Errorf("expected capture_state=idle, got %v", readings["capture_state"])
		}
	})

	t.Run("start_capture transitions to waiting", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		result, err := fs.handleStartCapture(map[string]interface{}{})
		if err != nil {
			t.Fatalf("handleStartCapture failed: %v", err)
		}
		if result["status"] != "waiting" {
			t.Errorf("expected status=waiting, got %v", result["status"])
		}

		readings, _ := fs.Readings(context.Background(), nil)
		if readings["capture_state"] != "waiting" {
			t.Errorf("expected capture_state=waiting, got %v", readings["capture_state"])
		}

		fs.handleEndCapture()
	})

	t.Run("first reading above threshold transitions to active", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		fs.handleStartCapture(map[string]interface{}{})

		// Mock reader triggers contact on start_capture, wait for transition
		time.Sleep(50 * time.Millisecond)

		readings, _ := fs.Readings(context.Background(), nil)
		if readings["capture_state"] != "capturing" {
			t.Errorf("expected capture_state=capturing, got %v", readings["capture_state"])
		}

		fs.handleEndCapture()
	})

	t.Run("end_capture transitions back to idle", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		fs.handleStartCapture(map[string]interface{}{})
		time.Sleep(50 * time.Millisecond)

		result, err := fs.handleEndCapture()
		if err != nil {
			t.Fatalf("handleEndCapture failed: %v", err)
		}
		if result["status"] != "completed" {
			t.Errorf("expected status=completed, got %v", result["status"])
		}

		readings, _ := fs.Readings(context.Background(), nil)
		if readings["capture_state"] != "idle" {
			t.Errorf("expected capture_state=idle, got %v", readings["capture_state"])
		}
	})

	t.Run("double start_capture errors", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		_, err := fs.handleStartCapture(map[string]interface{}{})
		if err != nil {
			t.Fatalf("first start_capture failed: %v", err)
		}

		_, err = fs.handleStartCapture(map[string]interface{}{})
		if err == nil {
			t.Error("expected error on double start_capture")
		}

		fs.handleEndCapture()
	})

	t.Run("end_capture without start errors", func(t *testing.T) {
		fs := newTestForceSensor(t)

		_, err := fs.handleEndCapture()
		if err == nil {
			t.Error("expected error when ending capture that wasn't started")
		}
	})
}

func TestForceSensor_ShouldSync(t *testing.T) {
	t.Run("false when idle", func(t *testing.T) {
		fs := newTestForceSensor(t)

		readings, _ := fs.Readings(context.Background(), nil)
		if readings["should_sync"] != false {
			t.Errorf("expected should_sync=false, got %v", readings["should_sync"])
		}
	})

	t.Run("true during capture with trial metadata", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		fs.handleStartCapture(map[string]interface{}{
			"trial_id":    "trial-123",
			"cycle_count": 5,
		})

		readings, _ := fs.Readings(context.Background(), nil)
		if readings["should_sync"] != true {
			t.Errorf("expected should_sync=true, got %v", readings["should_sync"])
		}
		if readings["trial_id"] != "trial-123" {
			t.Errorf("expected trial_id=trial-123, got %v", readings["trial_id"])
		}
		if readings["cycle_count"] != 5 {
			t.Errorf("expected cycle_count=5, got %v", readings["cycle_count"])
		}

		fs.handleEndCapture()
	})

	t.Run("false after end_capture", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		fs.handleStartCapture(map[string]interface{}{"trial_id": "trial-123"})
		fs.handleEndCapture()

		readings, _ := fs.Readings(context.Background(), nil)
		if readings["should_sync"] != false {
			t.Errorf("expected should_sync=false after end_capture, got %v", readings["should_sync"])
		}
		if readings["trial_id"] != "" {
			t.Errorf("expected empty trial_id after end_capture, got %v", readings["trial_id"])
		}
	})
}

func TestForceSensor_Buffer(t *testing.T) {
	t.Run("respects max size with rolling behavior", func(t *testing.T) {
		bufferSize := 10
		fs := &forceSensor{
			name:           resource.NewName(resource.APINamespaceRDK.WithComponentType("sensor"), "test"),
			logger:         logging.NewTestLogger(t),
			reader:         newMockForceReader(),
			sampleRateHz:   500, // Fast sampling to fill buffer
			bufferSize:     bufferSize,
			zeroThreshold:  5.0,
			captureTimeout: 10 * time.Second,
			samples:        make([]float64, 0, bufferSize),
			state:          captureIdle,
		}

		go fs.samplingLoop()

		fs.handleStartCapture(map[string]interface{}{})
		time.Sleep(100 * time.Millisecond)

		readings, _ := fs.Readings(context.Background(), nil)
		samples := readings["samples"].([]interface{})

		if len(samples) > bufferSize {
			t.Errorf("buffer exceeded max size: got %d, max %d", len(samples), bufferSize)
		}

		fs.handleEndCapture()
	})
}

func TestForceSensor_MaxForce(t *testing.T) {
	t.Run("correctly identifies max from samples", func(t *testing.T) {
		fs := newTestForceSensor(t)
		// Inject known samples directly
		fs.samples = []float64{10.0, 50.0, 30.0, 25.0}

		readings, _ := fs.Readings(context.Background(), nil)
		maxForce, ok := readings["max_force"].(float64)
		if !ok {
			t.Fatal("max_force not present or not float64")
		}
		if maxForce != 50.0 {
			t.Errorf("expected max_force=50.0, got %v", maxForce)
		}
	})
}

func TestForceSensor_ThreadSafety(t *testing.T) {
	t.Run("concurrent reads during active sampling", func(t *testing.T) {
		fs := newTestForceSensor(t)
		go fs.samplingLoop()

		fs.handleStartCapture(map[string]interface{}{})

		var wg sync.WaitGroup
		for i := 0; i < 10; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for j := 0; j < 10; j++ {
					_, err := fs.Readings(context.Background(), nil)
					if err != nil {
						t.Errorf("concurrent Readings failed: %v", err)
					}
					time.Sleep(5 * time.Millisecond)
				}
			}()
		}

		wg.Wait()
		fs.handleEndCapture()
	})
}
