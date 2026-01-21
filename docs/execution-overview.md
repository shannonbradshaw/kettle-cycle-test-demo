# Execution Overview — Code-Level Reference

This document maps the cycle test demo behavior to specific locations in the source code.

---

## Cycle Execution

**File:** `module.go` (lines 153-233)

The `handleExecuteCycle()` method implements the cycle sequence:

```go
func (s *kettleCycleTestController) handleExecuteCycle(ctx context.Context) (map[string]interface{}, error) {
    // 1. Move to pour_prep position (arm lifts kettle)
    if err := s.pourPrep.SetPosition(ctx, 2, nil); err != nil {
        return nil, fmt.Errorf("moving to pour_prep position: %w", err)
    }

    // 2. Pause 1 second
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    case <-time.After(1 * time.Second):
    }

    // 3. Start force capture (passes trial metadata if active)
    if s.forceSensor != nil {
        s.mu.Lock()
        captureCmd := map[string]interface{}{"command": "start_capture"}
        if s.activeTrial != nil {
            captureCmd["trial_id"] = s.activeTrial.trialID
            captureCmd["cycle_count"] = s.activeTrial.cycleCount
        }
        s.mu.Unlock()
        _, err := s.forceSensor.DoCommand(ctx, captureCmd)
        // ...
    }

    // 4. Move to resting position (arm puts kettle down)
    if err := s.resting.SetPosition(ctx, 2, nil); err != nil {
        // ...
    }

    // 5. Wait for arm to stop moving
    if err := s.waitForArmStopped(ctx); err != nil {
        // ...
    }

    // 6. End force capture
    if s.forceSensor != nil {
        captureResult, err = s.forceSensor.DoCommand(ctx, map[string]interface{}{"command": "end_capture"})
        // ...
    }

    // 7. Increment cycle count (if trial active)
    s.mu.Lock()
    if s.activeTrial != nil {
        s.activeTrial.cycleCount++
        s.activeTrial.lastCycleAt = time.Now()
    }
    s.mu.Unlock()

    // 8. Pause 1 second
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    case <-time.After(1 * time.Second):
    }

    return result, nil
}
```

---

## Trial Lifecycle

**File:** `module.go`

### Trial State Structure (lines 34-40)

```go
type trialState struct {
    trialID     string
    cycleCount  int
    startedAt   time.Time
    lastCycleAt time.Time
    stopCh      chan struct{}
}
```

### Starting a Trial — `handleStart()` (lines 248-272)

```go
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
```

### Background Cycling — `cycleLoop()` (lines 274-285)

```go
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
```

### Stopping a Trial — `handleStop()` (lines 287-305)

```go
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
```

### State Exposure — `GetState()` (lines 311-337)

```go
func (s *kettleCycleTestController) GetState() map[string]interface{} {
    s.mu.Lock()
    defer s.mu.Unlock()

    if s.activeTrial == nil {
        return map[string]interface{}{
            "state":         "idle",
            "trial_id":      "",
            "cycle_count":   0,
            "last_cycle_at": "",
            "should_sync":   false,  // No sync when idle
        }
    }

    // ...
    return map[string]interface{}{
        "state":         "running",
        "trial_id":      s.activeTrial.trialID,
        "cycle_count":   s.activeTrial.cycleCount,
        "last_cycle_at": lastCycleAt,
        "should_sync":   true,  // Sync during active trial
    }
}
```

---

## Force Sensor State Machine

**File:** `force_sensor.go`

### Capture States (lines 120-126)

```go
type captureState int

const (
    captureIdle captureState = iota
    captureWaiting  // waiting for first non-zero reading
    captureActive   // actively capturing samples
)
```

### Sampling Loop — State Transitions (lines 257-295)

```go
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
            // ...

            fs.mu.Lock()
            // Transition: waiting → active when force exceeds threshold
            if fs.state == captureWaiting && force >= fs.zeroThreshold {
                fs.state = captureActive
                fs.samples = fs.samples[:0]
                fs.logger.Infof("force capture started (first reading: %.2f)", force)
            }

            // Buffer samples during active capture
            if fs.state == captureActive {
                if len(fs.samples) >= fs.bufferSize {
                    fs.samples = fs.samples[1:]  // Rolling buffer
                }
                fs.samples = append(fs.samples, force)
            }
            fs.mu.Unlock()
        }
    }
}
```

### Start Capture — `handleStartCapture()` (lines 313-354)

```go
func (fs *forceSensor) handleStartCapture(cmd map[string]interface{}) (map[string]interface{}, error) {
    fs.mu.Lock()
    defer fs.mu.Unlock()

    if fs.state != captureIdle {
        return nil, fmt.Errorf("capture already in progress (state: %d)", fs.state)
    }

    // Extract trial metadata from command parameters
    fs.trialID = ""
    fs.cycleCount = 0
    if trialID, ok := cmd["trial_id"].(string); ok {
        fs.trialID = trialID
    }
    if cycleCount, ok := cmd["cycle_count"].(float64); ok {
        fs.cycleCount = int(cycleCount)
    }

    fs.state = captureWaiting  // Transition: idle → waiting
    fs.samples = fs.samples[:0]

    // Start timeout timer
    fs.timeoutTimer = time.AfterFunc(fs.captureTimeout, func() {
        // Auto-reset to idle if end_capture not called
    })

    return map[string]interface{}{"status": "waiting"}, nil
}
```

### End Capture — `handleEndCapture()` (lines 356-408)

```go
func (fs *forceSensor) handleEndCapture() (map[string]interface{}, error) {
    fs.mu.Lock()
    defer fs.mu.Unlock()

    if fs.state == captureIdle {
        return nil, fmt.Errorf("no capture in progress")
    }

    // Cancel timeout
    if fs.timeoutTimer != nil {
        fs.timeoutTimer.Stop()
    }

    // Calculate max force
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

    fs.state = captureIdle  // Transition: waiting/active → idle

    // Clear trial metadata (makes should_sync false)
    trialID := fs.trialID
    cycleCount := fs.cycleCount
    fs.trialID = ""
    fs.cycleCount = 0

    return map[string]interface{}{
        "status":       "completed",
        "sample_count": sampleCount,
        "max_force":    maxForce,
        "trial_id":     trialID,
        "cycle_count":  cycleCount,
    }, nil
}
```

---

## Trial Sensor — Wrapper Pattern

**File:** `trial_sensor.go`

### State Provider Interface (lines 35-37)

```go
type stateProvider interface {
    GetState() map[string]interface{}
}
```

### Readings Returns Controller State (lines 75-77)

```go
func (s *trialSensor) Readings(ctx context.Context, extra map[string]interface{}) (map[string]interface{}, error) {
    return s.controller.GetState(), nil
}
```

This wrapper pattern allows Viam's data capture system to poll the sensor's `Readings()` method, which transparently returns the controller's internal state including the `should_sync` field that controls conditional data capture.
