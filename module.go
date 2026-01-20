package kettlecycletest

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.viam.com/rdk/components/arm"
	"go.viam.com/rdk/components/sensor"
	toggleswitch "go.viam.com/rdk/components/switch"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
	generic "go.viam.com/rdk/services/generic"
)

var Controller = resource.NewModel("viamdemo", "kettle-cycle-test", "controller")

func init() {
	resource.RegisterService(generic.API, Controller,
		resource.Registration[resource.Resource, *Config]{
			Constructor: newKettleCycleTestController,
		},
	)
}

type Config struct {
	Arm              string `json:"arm"`
	RestingPosition  string `json:"resting_position"`
	PourPrepPosition string `json:"pour_prep_position"`
	ForceSensor      string `json:"force_sensor,omitempty"`
}

type trialState struct {
	trialID     string
	cycleCount  int
	startedAt   time.Time
	lastCycleAt time.Time
	stopCh      chan struct{}
}

func (cfg *Config) Validate(path string) ([]string, []string, error) {
	if cfg.Arm == "" {
		return nil, nil, fmt.Errorf("%s: arm is required", path)
	}
	if cfg.RestingPosition == "" {
		return nil, nil, fmt.Errorf("%s: resting_position is required", path)
	}
	if cfg.PourPrepPosition == "" {
		return nil, nil, fmt.Errorf("%s: pour_prep_position is required", path)
	}
	deps := []string{cfg.Arm, cfg.RestingPosition, cfg.PourPrepPosition}
	if cfg.ForceSensor != "" {
		deps = append(deps, cfg.ForceSensor)
	}
	return deps, nil, nil
}

type kettleCycleTestController struct {
	resource.AlwaysRebuild

	name   resource.Name
	logger logging.Logger
	cfg    *Config

	arm         arm.Arm
	resting     toggleswitch.Switch
	pourPrep    toggleswitch.Switch
	forceSensor sensor.Sensor // optional, may be nil

	cancelCtx  context.Context
	cancelFunc func()

	mu          sync.Mutex
	activeTrial *trialState
}

func newKettleCycleTestController(ctx context.Context, deps resource.Dependencies, rawConf resource.Config, logger logging.Logger) (resource.Resource, error) {
	conf, err := resource.NativeConfig[*Config](rawConf)
	if err != nil {
		return nil, err
	}

	return NewController(ctx, deps, rawConf.ResourceName(), conf, logger)

}

func NewController(ctx context.Context, deps resource.Dependencies, name resource.Name, conf *Config, logger logging.Logger) (resource.Resource, error) {
	a, err := arm.FromDependencies(deps, conf.Arm)
	if err != nil {
		return nil, fmt.Errorf("getting arm: %w", err)
	}

	resting, err := toggleswitch.FromDependencies(deps, conf.RestingPosition)
	if err != nil {
		return nil, fmt.Errorf("getting resting position switch: %w", err)
	}

	pourPrep, err := toggleswitch.FromDependencies(deps, conf.PourPrepPosition)
	if err != nil {
		return nil, fmt.Errorf("getting pour_prep position switch: %w", err)
	}

	var fs sensor.Sensor
	if conf.ForceSensor != "" {
		fs, err = sensor.FromDependencies(deps, conf.ForceSensor)
		if err != nil {
			return nil, fmt.Errorf("getting force sensor: %w", err)
		}
		logger.Infof("controller using force sensor: %s", conf.ForceSensor)
	}

	cancelCtx, cancelFunc := context.WithCancel(context.Background())

	s := &kettleCycleTestController{
		name:        name,
		logger:      logger,
		cfg:         conf,
		arm:         a,
		resting:     resting,
		pourPrep:    pourPrep,
		forceSensor: fs,
		cancelCtx:   cancelCtx,
		cancelFunc:  cancelFunc,
	}
	return s, nil
}

func (s *kettleCycleTestController) Name() resource.Name {
	return s.name
}

func (s *kettleCycleTestController) DoCommand(ctx context.Context, cmd map[string]interface{}) (map[string]interface{}, error) {
	command, ok := cmd["command"].(string)
	if !ok {
		return nil, fmt.Errorf("missing or invalid 'command' field")
	}

	switch command {
	case "execute_cycle":
		return s.handleExecuteCycle(ctx)
	case "start":
		return s.handleStart()
	case "stop":
		return s.handleStop()
	case "status":
		return s.handleStatus()
	default:
		return nil, fmt.Errorf("unknown command: %s", command)
	}
}

func (s *kettleCycleTestController) handleExecuteCycle(ctx context.Context) (map[string]interface{}, error) {
	if err := s.pourPrep.SetPosition(ctx, 2, nil); err != nil {
		return nil, fmt.Errorf("moving to pour_prep position: %w", err)
	}

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-time.After(1 * time.Second):
	}

	// Start force capture if sensor is configured
	if s.forceSensor != nil {
		s.mu.Lock()
		captureCmd := map[string]interface{}{"command": "start_capture"}
		if s.activeTrial != nil {
			captureCmd["trial_id"] = s.activeTrial.trialID
			captureCmd["cycle_count"] = s.activeTrial.cycleCount
		}
		s.mu.Unlock()

		_, err := s.forceSensor.DoCommand(ctx, captureCmd)
		if err != nil {
			s.logger.Warnf("failed to start force capture: %v", err)
		}
	}

	if err := s.resting.SetPosition(ctx, 2, nil); err != nil {
		// Try to end capture on error
		if s.forceSensor != nil {
			s.forceSensor.DoCommand(ctx, map[string]interface{}{"command": "end_capture"})
		}
		return nil, fmt.Errorf("returning to resting position: %w", err)
	}

	// Wait for arm to stop moving
	if err := s.waitForArmStopped(ctx); err != nil {
		s.logger.Warnf("error waiting for arm to stop: %v", err)
	}

	// End force capture
	var captureResult map[string]interface{}
	if s.forceSensor != nil {
		var err error
		captureResult, err = s.forceSensor.DoCommand(ctx, map[string]interface{}{"command": "end_capture"})
		if err != nil {
			s.logger.Warnf("failed to end force capture: %v", err)
		} else {
			s.logger.Infof("force capture: %v", captureResult)
		}
	}

	s.mu.Lock()
	if s.activeTrial != nil {
		s.activeTrial.cycleCount++
		s.activeTrial.lastCycleAt = time.Now()
	}
	s.mu.Unlock()

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-time.After(1 * time.Second):
	}

	result := map[string]interface{}{"status": "completed"}
	if captureResult != nil {
		result["force_capture"] = captureResult
	}
	return result, nil
}

func (s *kettleCycleTestController) waitForArmStopped(ctx context.Context) error {
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()

	timeout := time.After(10 * time.Second)
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-timeout:
			return fmt.Errorf("timeout waiting for arm to stop")
		case <-ticker.C:
			moving, err := s.arm.IsMoving(ctx)
			if err != nil {
				return fmt.Errorf("checking arm movement: %w", err)
			}
			if !moving {
				return nil
			}
		}
	}
}

func (s *kettleCycleTestController) handleStart() (map[string]interface{}, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.activeTrial != nil {
		return nil, fmt.Errorf("trial already running: %s", s.activeTrial.trialID)
	}

	now := time.Now()
	trialID := fmt.Sprintf("trial-%s", now.Format("20060102-150405"))
	stopCh := make(chan struct{})

	s.activeTrial = &trialState{
		trialID:   trialID,
		startedAt: now,
		stopCh:    stopCh,
	}

	// Start background cycling loop
	go s.cycleLoop(stopCh)

	return map[string]interface{}{
		"trial_id": trialID,
	}, nil
}

func (s *kettleCycleTestController) cycleLoop(stopCh chan struct{}) {
	for {
		select {
		case <-stopCh:
			return
		case <-s.cancelCtx.Done():
			return
		default:
			s.handleExecuteCycle(s.cancelCtx)
		}
	}
}

func (s *kettleCycleTestController) handleStop() (map[string]interface{}, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.activeTrial == nil {
		return nil, fmt.Errorf("no active trial to stop")
	}

	// Signal the loop to stop
	close(s.activeTrial.stopCh)

	result := map[string]interface{}{
		"trial_id":    s.activeTrial.trialID,
		"cycle_count": s.activeTrial.cycleCount,
	}
	s.activeTrial = nil

	return result, nil
}

func (s *kettleCycleTestController) handleStatus() (map[string]interface{}, error) {
	return s.GetState(), nil
}

func (s *kettleCycleTestController) GetState() map[string]interface{} {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.activeTrial == nil {
		return map[string]interface{}{
			"state":         "idle",
			"trial_id":      "",
			"cycle_count":   0,
			"last_cycle_at": "",
			"should_sync":   false,
		}
	}

	lastCycleAt := ""
	if !s.activeTrial.lastCycleAt.IsZero() {
		lastCycleAt = s.activeTrial.lastCycleAt.Format(time.RFC3339)
	}

	return map[string]interface{}{
		"state":         "running",
		"trial_id":      s.activeTrial.trialID,
		"cycle_count":   s.activeTrial.cycleCount,
		"last_cycle_at": lastCycleAt,
		"should_sync":   true,
	}
}

func (s *kettleCycleTestController) Close(context.Context) error {
	s.cancelFunc()
	return nil
}
