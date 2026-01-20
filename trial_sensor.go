package kettlecycletest

import (
	"context"
	"fmt"

	"go.viam.com/rdk/components/sensor"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
)

var TrialSensor = resource.NewModel("viamdemo", "kettle-cycle-test", "trial-sensor")

func init() {
	resource.RegisterComponent(sensor.API, TrialSensor,
		resource.Registration[sensor.Sensor, *TrialSensorConfig]{
			Constructor: newTrialSensor,
		},
	)
}

type TrialSensorConfig struct {
	Controller string `json:"controller"`
}

func (cfg *TrialSensorConfig) Validate(path string) ([]string, []string, error) {
	if cfg.Controller == "" {
		return nil, nil, fmt.Errorf("%s: controller is required", path)
	}
	// Return full resource name so Viam knows this is a generic service dependency
	dep := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), cfg.Controller)
	return []string{dep.String()}, nil, nil
}

type stateProvider interface {
	GetState() map[string]interface{}
}

type trialSensor struct {
	resource.AlwaysRebuild

	name       resource.Name
	logger     logging.Logger
	controller stateProvider
}

func newTrialSensor(ctx context.Context, deps resource.Dependencies, rawConf resource.Config, logger logging.Logger) (sensor.Sensor, error) {
	conf, err := resource.NativeConfig[*TrialSensorConfig](rawConf)
	if err != nil {
		return nil, err
	}

	controllerName := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), conf.Controller)
	ctrl, ok := deps[controllerName]
	if !ok {
		return nil, fmt.Errorf("controller %q not found in dependencies", conf.Controller)
	}

	provider, ok := ctrl.(stateProvider)
	if !ok {
		return nil, fmt.Errorf("controller %q does not implement GetState", conf.Controller)
	}

	return &trialSensor{
		name:       rawConf.ResourceName(),
		logger:     logger,
		controller: provider,
	}, nil
}

func (s *trialSensor) Name() resource.Name {
	return s.name
}

func (s *trialSensor) Readings(ctx context.Context, extra map[string]interface{}) (map[string]interface{}, error) {
	return s.controller.GetState(), nil
}

func (s *trialSensor) DoCommand(ctx context.Context, cmd map[string]interface{}) (map[string]interface{}, error) {
	return nil, fmt.Errorf("DoCommand not supported on trial-sensor")
}

func (s *trialSensor) Close(context.Context) error {
	return nil
}
