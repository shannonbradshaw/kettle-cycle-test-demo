package kettlecycletest

import (
	"context"
	"fmt"
	"time"

	"go.viam.com/rdk/components/arm"
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
	return []string{cfg.Arm, cfg.RestingPosition, cfg.PourPrepPosition}, nil, nil
}

type kettleCycleTestController struct {
	resource.AlwaysRebuild

	name   resource.Name
	logger logging.Logger
	cfg    *Config

	arm      arm.Arm
	resting  toggleswitch.Switch
	pourPrep toggleswitch.Switch

	cancelCtx  context.Context
	cancelFunc func()
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

	cancelCtx, cancelFunc := context.WithCancel(context.Background())

	s := &kettleCycleTestController{
		name:       name,
		logger:     logger,
		cfg:        conf,
		arm:        a,
		resting:    resting,
		pourPrep:   pourPrep,
		cancelCtx:  cancelCtx,
		cancelFunc: cancelFunc,
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

	if err := s.resting.SetPosition(ctx, 2, nil); err != nil {
		return nil, fmt.Errorf("returning to resting position: %w", err)
	}

	return map[string]interface{}{"status": "completed"}, nil
}

func (s *kettleCycleTestController) Close(context.Context) error {
	// Put close code here
	s.cancelFunc()
	return nil
}
