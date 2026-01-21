# Architecture

This document explains how the demo's components fit together.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Viam Machine                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────┐                 │
│  │   Controller     │      │   UFactory Lite6 │                 │
│  │   (service)      │─────▶│   Arm            │                 │
│  │                  │      └──────────────────┘                 │
│  │  - start/stop    │                                           │
│  │  - execute_cycle │      ┌──────────────────┐                 │
│  │  - status        │─────▶│ Position-Saver   │                 │
│  └────────┬─────────┘      │ Switches (2)     │                 │
│           │                └──────────────────┘                 │
│           │                                                     │
│           │ DoCommand                                           │
│           │ start_capture / end_capture                         │
│           ▼                                                     │
│  ┌──────────────────┐      ┌──────────────────┐                 │
│  │  Force Sensor    │─────▶│  Load Cell       │                 │
│  │  (virtual)       │      │  (ADC sensor)    │                 │
│  └──────────────────┘      └──────────────────┘                 │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │  Trial Sensor    │◀──── wraps controller.GetState()          │
│  │  (virtual)       │                                           │
│  └──────────────────┘                                           │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │  Data Manager    │◀──── captures sensor readings @ 1-1000Hz  │
│  └──────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### Controller Service (`cycle-tester`)

The orchestrator. A custom service that:
- Manages trial lifecycle (start/stop continuous testing)
- Executes individual test cycles
- Coordinates arm movements via position-saver switches
- Triggers force capture at the right moment
- Exposes state for data capture

**Type:** `rdk:service:generic`
**Model:** `viamdemo:kettle-cycle-test:controller`

### Robot Arm (`arm`)

A UFactory Lite6 6-DOF robot arm that physically moves the kettle.

**Type:** `rdk:component:arm`
**Model:** `viam:ufactory:lite6`

### Position-Saver Switches

Saved arm positions as toggleable switches. When you "turn on" a switch, the arm moves to that saved position.

| Switch | Purpose |
|--------|---------|
| `resting-position` | Kettle down on the test fixture |
| `pour-prep-position` | Kettle lifted, ready for pour motion |

**Type:** `rdk:component:switch`
**Model:** `erh:vmodutils:arm-position-saver`

### Trial Sensor (`trial-sensor`)

A virtual sensor that wraps the controller's state. Viam's data manager polls this sensor to capture trial state.

Returns:
- `state`: "idle" or "running"
- `trial_id`: Identifier for current trial
- `cycle_count`: Number of cycles completed
- `should_sync`: Whether data should upload to cloud

**Type:** `rdk:component:sensor`
**Model:** `viamdemo:kettle-cycle-test:trial-sensor`

### Force Sensor (`force-sensor`)

A virtual sensor that captures force profiles during the put-down phase. Wraps a raw ADC sensor (load cell) and enriches it with cycle awareness.

Returns:
- `samples`: Array of force readings
- `max_force`: Peak force during capture
- `trial_id`, `cycle_count`: Metadata from controller
- `should_sync`: True only during active capture

**Type:** `rdk:component:sensor`
**Model:** `viamdemo:kettle-cycle-test:force-sensor`

### Load Cell (`load-cell`)

Raw force sensor connected via ADC. The force-sensor wraps this to add capture logic.

**Type:** `rdk:component:sensor`
**Model:** `viam-labs:mcp300x-adc-sensor` (or `rdk:builtin:fake` for testing)

### Data Manager

Built-in Viam service that captures sensor readings and syncs to cloud.

**Type:** `rdk:service:data_manager`

---

## Data Flow

### During a Cycle

```
1. Controller: "Move to pour-prep"
        │
        ▼
   Position-saver switch triggers arm movement
        │
        ▼
2. Controller: Pause 1 second
        │
        ▼
3. Controller → Force Sensor: DoCommand("start_capture")
   (passes trial_id, cycle_count)
        │
        ▼
4. Controller: "Move to resting"
        │
        ▼
   Arm moves down, kettle contacts fixture
        │
        ▼
   Force sensor detects contact, begins buffering samples
        │
        ▼
5. Controller: waitForArmStopped()
        │
        ▼
6. Controller → Force Sensor: DoCommand("end_capture")
   (returns sample_count, max_force)
        │
        ▼
7. Controller: Increment cycle_count
        │
        ▼
8. Controller: Pause 1 second
```

### Data Capture Flow

```
┌─────────────┐     Readings()      ┌─────────────┐
│ Data Manager│ ──────────────────► │ Trial Sensor│
│ (polling)   │                     │             │
└─────────────┘                     └──────┬──────┘
                                           │
                                           │ GetState()
                                           ▼
                                    ┌─────────────┐
                                    │ Controller  │
                                    └─────────────┘

If should_sync == true → Data syncs to Viam cloud
If should_sync == false → Data captured locally but not synced
```

---

## Trial Lifecycle

```
     ┌──────────┐     start      ┌──────────┐      stop      ┌──────────┐
     │   IDLE   │ ──────────────▶│ RUNNING  │───────────────▶│   IDLE   │
     │          │                │          │                │          │
     │ no trial │                │ cycling  │                │ returns  │
     │ count=0  │                │ in loop  │                │ count=N  │
     └──────────┘                └──────────┘                └──────────┘
```

**Commands:**
- `start` — Creates trial ID, spawns background goroutine, begins continuous cycling
- `stop` — Signals loop to stop, returns final cycle count
- `status` — Returns current state without modifying it
- `execute_cycle` — Runs single cycle (can be called standalone or during trial)

---

## Force Sensor State Machine

```
     ┌──────────┐  start_capture  ┌──────────┐  force > threshold   ┌──────────┐
     │   IDLE   │ ───────────────▶│ WAITING  │─────────────────────▶│ ACTIVE   │
     │          │                 │          │                      │          │
     │ no data  │                 │ sampling │                      │ sampling │
     │ no sync  │                 │ ignoring │                      │ buffering│
     └──────────┘                 │ zeros    │                      │ samples  │
          ▲                       └──────────┘                      └──────────┘
          │                                                               │
          │                         end_capture                           │
          └───────────────────────────────────────────────────────────────┘
```

The "waiting" state skips readings while the kettle is still in the air. Capture only begins when force exceeds the threshold (kettle contacts fixture).

---

## Dependencies

The module depends on three external Viam modules from the Registry:

| Module | Provides | Purpose |
|--------|----------|---------|
| `viam:ufactory` | Lite6 arm driver | Controls the robot arm |
| `erh:vmodutils` | Position-saver switch | Abstracts saved arm positions |
| `viamdemo:kettle-cycle-test` | Controller, trial-sensor, force-sensor | This demo's logic |

