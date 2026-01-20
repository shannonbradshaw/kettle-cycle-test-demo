package kettlecycletest

import (
	"context"
	"fmt"

	"go.viam.com/rdk/components/sensor"
	"go.viam.com/rdk/logging"
	"go.viam.com/rdk/resource"
)

var CycleSensor = resource.NewModel("viamdemo", "kettle-cycle-test", "cycle-sensor")

func init() {
	resource.RegisterComponent(sensor.API, CycleSensor,
		resource.Registration[sensor.Sensor, *SensorConfig]{
			Constructor: newCycleSensor,
		},
	)
}

type SensorConfig struct {
	Controller string `json:"controller"`
}

func (cfg *SensorConfig) Validate(path string) ([]string, []string, error) {
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

type cycleSensor struct {
	resource.AlwaysRebuild

	name       resource.Name
	logger     logging.Logger
	controller stateProvider
}

func newCycleSensor(ctx context.Context, deps resource.Dependencies, rawConf resource.Config, logger logging.Logger) (sensor.Sensor, error) {
	conf, err := resource.NativeConfig[*SensorConfig](rawConf)
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

	return &cycleSensor{
		name:       rawConf.ResourceName(),
		logger:     logger,
		controller: provider,
	}, nil
}

func (s *cycleSensor) Name() resource.Name {
	return s.name
}

func (s *cycleSensor) Readings(ctx context.Context, extra map[string]interface{}) (map[string]interface{}, error) {
	return s.controller.GetState(), nil
}

func (s *cycleSensor) DoCommand(ctx context.Context, cmd map[string]interface{}) (map[string]interface{}, error) {
	return nil, fmt.Errorf("DoCommand not supported on cycle-sensor")
}

func (s *cycleSensor) Close(context.Context) error {
	return nil
}
