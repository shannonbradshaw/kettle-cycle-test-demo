package main

import (
	"kettlecycletest"

	"go.viam.com/rdk/components/sensor"
	"go.viam.com/rdk/module"
	"go.viam.com/rdk/resource"
	generic "go.viam.com/rdk/services/generic"
)

func main() {
	module.ModularMain(
		resource.APIModel{generic.API, kettlecycletest.Controller},
		resource.APIModel{sensor.API, kettlecycletest.TrialSensor},
		resource.APIModel{sensor.API, kettlecycletest.ForceSensor},
	)
}
