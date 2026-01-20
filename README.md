# Kettle Cycle Testing Demo

A Viam robotics platform demo for appliance R&D labs, demonstrating cycle testing, failure detection, data capture, and alerting.

> **Status:** Milestone 3 complete — trial lifecycle with continuous cycling and data capture readiness. See [product_spec.md](product_spec.md) for full roadmap.

## What This Demo Does

This demo shows how to use Viam's robotics platform for automated product testing. A robotic arm grips a kettle by its handle, lifts it, performs a pouring motion, and sets it back down—repeatedly—to stress-test the handle. Computer vision detects when the handle fails, triggering alerts and stopping the test. All sensor data, images, and events are captured and synced to the cloud for analysis.

Key Viam features demonstrated:
- Modular services for orchestrating complex routines
- Motion planning with constraints (keeping the kettle level during movement)
- Tag-based data correlation across sensors and cameras
- Vision service integration with custom ML models
- Built-in alerting and monitoring
- Hot-reload deployment for rapid iteration

## Module Structure

This project is a Viam module providing two resources:

**Controller Service:**
- **API:** `rdk:service:generic`
- **Model:** `viamdemo:kettle-cycle-test:controller`
- **Implementation:** `module.go`
- **Tests:** `module_test.go`

The controller orchestrates arm movements, trial lifecycle, and cycle execution. Using a generic service allows it to coordinate multiple hardware resources without implementing hardware-specific interfaces.

**Cycle Sensor Component:**
- **API:** `rdk:component:sensor`
- **Model:** `viamdemo:kettle-cycle-test:cycle-sensor`
- **Implementation:** `sensor.go`
- **Tests:** `sensor_test.go`

The sensor exposes controller state (trial ID, cycle count, running status) for Viam data capture. Its `should_sync` field enables conditional data capture—only syncing data when a trial is active.

**Entry Point:**
- `cmd/module/main.go` - Registers both resources with the Viam module system

## Setup

### Machine Configuration

Create a `machine.json` file in the project root with your Viam machine details:

```json
{
  "org_id": "your-org-id",
  "location_id": "your-location-id",
  "machine_id": "your-machine-id",
  "part_id": "your-part-id",
  "machine_address": "your-machine.viam.cloud"
}
```

You can find these values in the Viam app under your machine's settings.

### Adding the Controller Service

In the Viam app, add a generic service to your machine:
- **Name:** `cycle-tester`
- **API:** `rdk:service:generic`
- **Model:** `viamdemo:kettle-cycle-test:controller`

**Configuration attributes:**
```json
{
  "arm": "your-arm-name",
  "resting_position": "resting-switch-name",
  "pour_prep_position": "pour-prep-switch-name"
}
```

All three fields are required:
- `arm` - Name of the arm component (explicit dependency)
- `resting_position` - Position-saver switch for the resting pose
- `pour_prep_position` - Position-saver switch for the pour-prep pose

### Adding the Cycle Sensor

Add a sensor component to expose controller state for data capture:
- **Name:** `cycle-sensor`
- **API:** `rdk:component:sensor`
- **Model:** `viamdemo:kettle-cycle-test:cycle-sensor`

**Configuration attributes:**
```json
{
  "controller": "cycle-tester"
}
```

The sensor depends on the controller service and exposes its state through the standard sensor `Readings()` interface.

## Milestone 1: Foundation

The module foundation is now in place:

**What's Working:**
- Generic service scaffolding generated with `viam module generate`
- Module builds and packages correctly (see `Makefile` for build targets)
- Hot-reload deployment to remote machines via `viam module reload-local`
- Service registers with Viam RDK and responds to lifecycle events
- DoCommand stub returns "not implemented" (ready for command routing)
- Three unit tests validate resource creation, command handling, and cleanup

**Key Files:**
- `module.go` - Controller implementation
- `module_test.go` - Unit tests
- `cmd/module/main.go` - Module entry point
- `meta.json` - Module metadata for Viam registry
- `Makefile` - Build and test targets

**Viam Concepts Introduced:**
- **Generic services** - orchestration layer that coordinates multiple components
- **Module structure** - how to package and deploy custom Viam functionality
- **Resource lifecycle** - constructor, DoCommand interface, Close method
- **Hot reload** - rapid iteration with `viam module reload-local`

**Next:** Milestone 4 will add load cell data capture via MCP3008 ADC.

## Milestone 2: Arm Movement

The controller now moves the arm between saved positions using position-saver switches.

**What's Working:**
- `execute_cycle` DoCommand moves arm through a test cycle
- Sequence: resting → pour_prep → pause (1 second) → resting
- Config validation ensures required dependencies (arm, switches) are present
- Position-saver switches (from vmodutils module) trigger arm movements
- Arm is an explicit dependency for clarity in the service dependency chain
- Comprehensive unit tests for config validation and execute_cycle behavior
- Makefile targets for hot-reload deployment and cycle testing

**Key Implementation Details:**
- `/Users/apr/Developer/kettle-cycle-test-demo/module.go` - Config struct with required fields, Validate method, handleExecuteCycle logic
- `/Users/apr/Developer/kettle-cycle-test-demo/module_test.go` - Tests for config validation errors, successful cycle execution, error handling
- `/Users/apr/Developer/kettle-cycle-test-demo/Makefile` - `reload-module` and `test-cycle` targets for development workflow

**Viam Concepts Introduced:**
- **Position-saver switches** - vmodutils module provides switches that trigger arm movements to saved positions
- **Explicit dependencies** - arm declared in config.Validate() for clear dependency ordering
- **Config validation** - Validate method returns required dependencies and validates user input
- **DoCommand routing** - switch statement handles different commands (currently just "execute_cycle")

**Testing the cycle:**
```bash
make reload-module  # Deploy to robot
make test-cycle     # Trigger execute_cycle via CLI
```

Or manually via Viam CLI:
```bash
viam machine part run --part <part_id> \
  --method 'viam.service.generic.v1.GenericService.DoCommand' \
  --data '{"name": "cycle-tester", "command": {"command": "execute_cycle"}}'
```

## Milestone 3: Trial Lifecycle and Data Capture Readiness

The controller now manages trial lifecycle with continuous cycling and exposes state for data capture.

**What's Working:**
- `start` DoCommand begins a trial and starts continuous background cycling
- `stop` DoCommand ends the trial and returns cycle count
- `status` DoCommand returns current trial state
- Automatic cycle counting during active trials
- `GetState()` method exposes trial metadata for the sensor component
- `should_sync` field in state enables conditional data capture (true during trials, false when idle)
- New cycle-sensor component provides Viam data capture integration
- Makefile targets for trial management: `trial-start`, `trial-stop`, `trial-status`
- Background cycling loop runs until stopped or module closes

**Key Implementation Details:**
- `/Users/apr/Developer/kettle-cycle-test-demo/module.go` - `trialState` struct, `cycleLoop` goroutine, `GetState()` method, trial management commands
- `/Users/apr/Developer/kettle-cycle-test-demo/sensor.go` - Sensor component that wraps controller state, `stateProvider` interface for dependency injection
- `/Users/apr/Developer/kettle-cycle-test-demo/cmd/module/main.go` - Dual resource registration (controller service + cycle sensor component)
- `/Users/apr/Developer/kettle-cycle-test-demo/Makefile` - `trial-start`, `trial-stop`, `trial-status` targets

**Viam Concepts Introduced:**
- **Trial lifecycle** - DoCommand patterns for stateful operations (start/stop/status)
- **Background routines** - Goroutines with cancellation for continuous operation
- **State exposure** - Sensor component wraps service state for data capture
- **Conditional sync** - `should_sync` field controls when data is captured to cloud
- **Service dependencies** - Sensor depends on generic service, not just components
- **Interface-based design** - `stateProvider` interface decouples sensor from controller implementation

**Cycle Sequence:**
Each cycle when a trial is running:
1. Move to pour_prep position
2. Pause 1 second
3. Return to resting position
4. Pause 1 second
5. Increment cycle count
6. Repeat until stopped

**Managing Trials:**
```bash
# Start a trial (begins continuous cycling)
make trial-start

# Check trial status
make trial-status

# Stop the trial
make trial-stop
```

Or manually via Viam CLI:
```bash
# Start
viam machine part run --part <part_id> \
  --method 'viam.service.generic.v1.GenericService.DoCommand' \
  --data '{"name": "cycle-tester", "command": {"command": "start"}}'

# Status
viam machine part run --part <part_id> \
  --method 'viam.service.generic.v1.GenericService.DoCommand' \
  --data '{"name": "cycle-tester", "command": {"command": "status"}}'

# Stop
viam machine part run --part <part_id> \
  --method 'viam.service.generic.v1.GenericService.DoCommand' \
  --data '{"name": "cycle-tester", "command": {"command": "stop"}}'
```

**Sensor Readings:**
Query the cycle-sensor to see trial state:
```bash
viam machine part run --part <part_id> \
  --method 'viam.component.sensor.v1.SensorService.GetReadings' \
  --data '{"name": "cycle-sensor"}'
```

Returns:
```json
{
  "state": "running",
  "trial_id": "trial-20260120-143052",
  "cycle_count": 42,
  "last_cycle_at": "2026-01-20T14:35:12Z",
  "should_sync": true
}
```

When idle:
```json
{
  "state": "idle",
  "trial_id": "",
  "cycle_count": 0,
  "last_cycle_at": "",
  "should_sync": false
}
```

## Development

### Build and Deploy

```bash
make reload-module
```

Builds for the target architecture, uploads, and restarts the module on the configured machine. Uses PART_ID from `machine.json`.

Alternatively, use the Viam CLI directly:
```bash
viam module reload-local --part-id <part_id from machine.json>
```

### Run Tests

```bash
go test ./...
```

### Local Build

```bash
make module.tar.gz
```

Creates a packaged module ready for upload to the Viam registry.

---

*Full documentation will be added as development progresses. See the [README Target Outline](product_spec.md#readme-target-outline) for planned content.*
