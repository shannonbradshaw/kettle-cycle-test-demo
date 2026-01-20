package kettlecycletest

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.viam.com/rdk/components/sensor"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
)

var ForceSensor = resource.NewModel("viamdemo", "kettle-cycle-test", "force-sensor")

func init() {
	resource.RegisterComponent(sensor.API, ForceSensor,
		resource.Registration[sensor.Sensor, *ForceSensorConfig]{
			Constructor: newForceSensor,
		},
	)
}

type ForceSensorConfig struct {
	LoadCell       string  `json:"load_cell"`                    // REQUIRED: name of load cell sensor
	UseMockCurve   bool    `json:"use_mock_curve,omitempty"`     // optional: use mock force curve instead of hardware
	ForceKey       string  `json:"force_key,omitempty"`
	SampleRateHz   int     `json:"sample_rate_hz,omitempty"`
	BufferSize     int     `json:"buffer_size,omitempty"`
	ZeroThreshold  float64 `json:"zero_threshold,omitempty"`     // readings below this are "zero" (default: 5.0)
	CaptureTimeout int     `json:"capture_timeout_ms,omitempty"` // timeout in ms (default: 10000)
}

func (cfg *ForceSensorConfig) Validate(path string) ([]string, []string, error) {
	if cfg.LoadCell == "" {
		return nil, nil, fmt.Errorf("%s: load_cell is required", path)
	}
	return []string{cfg.LoadCell}, nil, nil
}

// forceReader abstracts force reading for mock vs hardware implementations
type forceReader interface {
	ReadForce(ctx context.Context) (float64, error)
}

// mockForceReader simulates realistic force profile: zeros while lifted, ramp on contact
type mockForceReader struct {
	mu           sync.Mutex
	inContact    bool
	contactCount int
}

func newMockForceReader() *mockForceReader {
	return &mockForceReader{}
}

func (m *mockForceReader) ReadForce(ctx context.Context) (float64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if !m.inContact {
		// Kettle is lifted - return near-zero with small noise
		return 0.5, nil
	}

	// Kettle is in contact - simulate force ramp
	m.contactCount++
	// Ramp from 50 to 200 over 50 samples, then hold
	if m.contactCount < 50 {
		return 50.0 + float64(m.contactCount)*3.0, nil
	}
	return 200.0, nil
}

func (m *mockForceReader) SetContact(inContact bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.inContact = inContact
	if inContact {
		m.contactCount = 0
	}
}

// sensorForceReader wraps a Viam sensor component to read force values
type sensorForceReader struct {
	sensor   sensor.Sensor
	forceKey string
}

func newSensorForceReader(s sensor.Sensor, forceKey string) *sensorForceReader {
	if forceKey == "" {
		forceKey = "value"
	}
	return &sensorForceReader{sensor: s, forceKey: forceKey}
}

func (r *sensorForceReader) ReadForce(ctx context.Context) (float64, error) {
	readings, err := r.sensor.Readings(ctx, nil)
	if err != nil {
		return 0, err
	}

	val, ok := readings[r.forceKey]
	if !ok {
		return 0, fmt.Errorf("sensor readings missing %q key", r.forceKey)
	}

	switch v := val.(type) {
	case float64:
		return v, nil
	case int:
		return float64(v), nil
	case int64:
		return float64(v), nil
	default:
		return 0, fmt.Errorf("sensor reading %q is not numeric: %T", r.forceKey, val)
	}
}

type captureState int

const (
	captureIdle captureState = iota
	captureWaiting  // waiting for first non-zero reading
	captureActive   // actively capturing samples
)

type forceSensor struct {
	resource.AlwaysRebuild

	name   resource.Name
	logger logging.Logger
	reader forceReader

	sampleRateHz   int
	bufferSize     int
	zeroThreshold  float64
	captureTimeout time.Duration

	mu           sync.Mutex
	samples      []float64
	state        captureState
	timeoutTimer *time.Timer

	// Trial metadata passed via start_capture
	trialID    string
	cycleCount int
}

func newForceSensor(ctx context.Context, deps resource.Dependencies, rawConf resource.Config, logger logging.Logger) (sensor.Sensor, error) {
	conf, err := resource.NativeConfig[*ForceSensorConfig](rawConf)
	if err != nil {
		return nil, err
	}

	sampleRate := conf.SampleRateHz
	if sampleRate <= 0 {
		sampleRate = 50
	}

	bufferSize := conf.BufferSize
	if bufferSize <= 0 {
		bufferSize = 100
	}

	zeroThreshold := conf.ZeroThreshold
	if zeroThreshold <= 0 {
		zeroThreshold = 5.0
	}

	captureTimeout := conf.CaptureTimeout
	if captureTimeout <= 0 {
		captureTimeout = 10000 // 10 seconds default
	}

	var reader forceReader
	if conf.UseMockCurve {
		reader = newMockForceReader()
		logger.Infof("force-sensor using mock curve (use_mock_curve=true)")
	} else {
		loadCellSensor, err := sensor.FromDependencies(deps, conf.LoadCell)
		if err != nil {
			return nil, fmt.Errorf("getting load_cell sensor: %w", err)
		}
		reader = newSensorForceReader(loadCellSensor, conf.ForceKey)
		logger.Infof("force-sensor wrapping load cell %q (key: %q)", conf.LoadCell, conf.ForceKey)
	}

	fs := &forceSensor{
		name:           rawConf.ResourceName(),
		logger:         logger,
		reader:         reader,
		sampleRateHz:   sampleRate,
		bufferSize:     bufferSize,
		zeroThreshold:  zeroThreshold,
		captureTimeout: time.Duration(captureTimeout) * time.Millisecond,
		samples:        make([]float64, 0, bufferSize),
		state:          captureIdle,
	}

	go fs.samplingLoop()

	return fs, nil
}

func (fs *forceSensor) Name() resource.Name {
	return fs.name
}

func (fs *forceSensor) Readings(ctx context.Context, extra map[string]interface{}) (map[string]interface{}, error) {
	fs.mu.Lock()
	samplesCopy := make([]float64, len(fs.samples))
	copy(samplesCopy, fs.samples)
	state := fs.state
	trialID := fs.trialID
	cycleCount := fs.cycleCount
	fs.mu.Unlock()

	samplesInterface := make([]interface{}, len(samplesCopy))
	for i, v := range samplesCopy {
		samplesInterface[i] = v
	}

	stateStr := "idle"
	switch state {
	case captureWaiting:
		stateStr = "waiting"
	case captureActive:
		stateStr = "capturing"
	}

	// should_sync is true when we have an active trial (trialID is set)
	shouldSync := trialID != ""

	result := map[string]interface{}{
		"trial_id":      trialID,
		"cycle_count":   cycleCount,
		"should_sync":   shouldSync,
		"samples":       samplesInterface,
		"sample_count":  len(samplesCopy),
		"capture_state": stateStr,
	}

	if len(samplesCopy) > 0 {
		max := samplesCopy[0]
		for _, v := range samplesCopy[1:] {
			if v > max {
				max = v
			}
		}
		result["max_force"] = max
	}

	return result, nil
}

func (fs *forceSensor) samplingLoop() {
	ticker := time.NewTicker(time.Second / time.Duration(fs.sampleRateHz))
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			fs.mu.Lock()
			currentState := fs.state
			fs.mu.Unlock()

			if currentState == captureIdle {
				continue
			}

			force, err := fs.reader.ReadForce(context.Background())
			if err != nil {
				fs.logger.Warnf("failed to read force: %v", err)
				continue
			}

			fs.mu.Lock()
			if fs.state == captureWaiting && force >= fs.zeroThreshold {
				// First non-zero reading - start capturing
				fs.state = captureActive
				fs.samples = fs.samples[:0]
				fs.logger.Infof("force capture started (first reading: %.2f)", force)
			}

			if fs.state == captureActive {
				if len(fs.samples) >= fs.bufferSize {
					fs.samples = fs.samples[1:]
				}
				fs.samples = append(fs.samples, force)
			}
			fs.mu.Unlock()
		}
	}
}

func (fs *forceSensor) DoCommand(ctx context.Context, cmd map[string]interface{}) (map[string]interface{}, error) {
	command, ok := cmd["command"].(string)
	if !ok {
		return nil, fmt.Errorf("missing or invalid 'command' field")
	}

	switch command {
	case "start_capture":
		return fs.handleStartCapture(cmd)
	case "end_capture":
		return fs.handleEndCapture()
	default:
		return nil, fmt.Errorf("unknown command: %s", command)
	}
}

func (fs *forceSensor) handleStartCapture(cmd map[string]interface{}) (map[string]interface{}, error) {
	fs.mu.Lock()
	defer fs.mu.Unlock()

	if fs.state != captureIdle {
		return nil, fmt.Errorf("capture already in progress (state: %d)", fs.state)
	}

	// Reset and extract trial metadata from command
	// This ensures should_sync is only true during active trials
	fs.trialID = ""
	fs.cycleCount = 0
	if trialID, ok := cmd["trial_id"].(string); ok {
		fs.trialID = trialID
	}
	if cycleCount, ok := cmd["cycle_count"].(float64); ok {
		fs.cycleCount = int(cycleCount)
	} else if cycleCount, ok := cmd["cycle_count"].(int); ok {
		fs.cycleCount = cycleCount
	}

	fs.state = captureWaiting
	fs.samples = fs.samples[:0]

	// Start timeout timer
	fs.timeoutTimer = time.AfterFunc(fs.captureTimeout, func() {
		fs.mu.Lock()
		defer fs.mu.Unlock()
		if fs.state != captureIdle {
			fs.logger.Errorf("capture timeout: end_capture not called within %v", fs.captureTimeout)
			fs.state = captureIdle
		}
	})

	// If using mock reader, simulate contact starting
	if mock, ok := fs.reader.(*mockForceReader); ok {
		mock.SetContact(true)
	}

	fs.logger.Infof("capture started, waiting for non-zero reading (threshold: %.2f)", fs.zeroThreshold)
	return map[string]interface{}{"status": "waiting"}, nil
}

func (fs *forceSensor) handleEndCapture() (map[string]interface{}, error) {
	fs.mu.Lock()
	defer fs.mu.Unlock()

	if fs.state == captureIdle {
		return nil, fmt.Errorf("no capture in progress")
	}

	// Cancel timeout
	if fs.timeoutTimer != nil {
		fs.timeoutTimer.Stop()
		fs.timeoutTimer = nil
	}

	// If using mock reader, simulate contact ending
	if mock, ok := fs.reader.(*mockForceReader); ok {
		mock.SetContact(false)
	}

	sampleCount := len(fs.samples)
	var maxForce float64
	if sampleCount > 0 {
		maxForce = fs.samples[0]
		for _, v := range fs.samples[1:] {
			if v > maxForce {
				maxForce = v
			}
		}
	}

	prevState := fs.state
	fs.state = captureIdle

	// Clear trial metadata so should_sync becomes false
	trialID := fs.trialID
	cycleCount := fs.cycleCount
	fs.trialID = ""
	fs.cycleCount = 0

	stateStr := "waiting"
	if prevState == captureActive {
		stateStr = "capturing"
	}

	fs.logger.Infof("capture ended (was %s): %d samples, max force: %.2f", stateStr, sampleCount, maxForce)
	return map[string]interface{}{
		"status":       "completed",
		"sample_count": sampleCount,
		"max_force":    maxForce,
		"trial_id":     trialID,
		"cycle_count":  cycleCount,
	}, nil
}

func (fs *forceSensor) Close(context.Context) error {
	fs.mu.Lock()
	if fs.timeoutTimer != nil {
		fs.timeoutTimer.Stop()
	}
	fs.mu.Unlock()
	return nil
}
