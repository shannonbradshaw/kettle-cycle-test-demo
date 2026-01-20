package kettlecycletest

import (
	"context"
	"testing"

	"go.viam.com/rdk/components/sensor"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
)

type mockStateProvider struct {
	state map[string]interface{}
}

func (m *mockStateProvider) GetState() map[string]interface{} {
	return m.state
}

func TestSensor_GetReadings_ReturnsControllerState(t *testing.T) {
	logger := logging.NewTestLogger(t)
	name := resource.NewName(sensor.API, "test-sensor")

	expectedState := map[string]interface{}{
		"state":         "running",
		"trial_id":      "trial-20260120-143052",
		"cycle_count":   5,
		"last_cycle_at": "2026-01-20T14:32:00Z",
	}

	mock := &mockStateProvider{state: expectedState}
	sensor := &cycleSensor{
		name:       name,
		logger:     logger,
		controller: mock,
	}

	readings, err := sensor.Readings(context.Background(), nil)
	if err != nil {
		t.Fatalf("Readings failed: %v", err)
	}

	if readings["state"] != expectedState["state"] {
		t.Errorf("state: expected %v, got %v", expectedState["state"], readings["state"])
	}
	if readings["trial_id"] != expectedState["trial_id"] {
		t.Errorf("trial_id: expected %v, got %v", expectedState["trial_id"], readings["trial_id"])
	}
	if readings["cycle_count"] != expectedState["cycle_count"] {
		t.Errorf("cycle_count: expected %v, got %v", expectedState["cycle_count"], readings["cycle_count"])
	}
	if readings["last_cycle_at"] != expectedState["last_cycle_at"] {
		t.Errorf("last_cycle_at: expected %v, got %v", expectedState["last_cycle_at"], readings["last_cycle_at"])
	}
}
