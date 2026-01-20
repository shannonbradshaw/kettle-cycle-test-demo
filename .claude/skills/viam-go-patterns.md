---
name: viam-go-patterns
description: Common Viam RDK patterns for Go module development
---

## Accessing Dependencies in Constructor

```go
func NewController(ctx context.Context, deps resource.Dependencies, name resource.Name, conf *Config, logger logging.Logger) (resource.Resource, error) {
    // Access a dependency declared in Validate()
    arm, err := arm.FromDependencies(deps, conf.ArmName)
    if err != nil {
        return nil, fmt.Errorf("failed to get arm %q: %w", conf.ArmName, err)
    }

    return &controller{
        name:   name,
        logger: logger,
        cfg:    conf,
        arm:    arm,
    }, nil
}
```

## Declaring Dependencies in Validate

```go
func (cfg *Config) Validate(path string) ([]string, []string, error) {
    if cfg.ArmName == "" {
        return nil, nil, fmt.Errorf("%s: missing required field 'arm'", path)
    }
    // First return: required dependencies
    // Second return: optional dependencies
    return []string{cfg.ArmName}, nil, nil
}
```

## DoCommand Pattern with Command Routing

```go
func (c *controller) DoCommand(ctx context.Context, cmd map[string]interface{}) (map[string]interface{}, error) {
    cmdName, ok := cmd["command"].(string)
    if !ok {
        return nil, errors.New("missing 'command' field")
    }

    switch cmdName {
    case "start_cycle":
        return c.handleStartCycle(ctx, cmd)
    case "stop_cycle":
        return c.handleStopCycle(ctx)
    case "get_status":
        return c.handleGetStatus(ctx)
    default:
        return nil, fmt.Errorf("unknown command: %s", cmdName)
    }
}
```

## Testing with Mock Dependencies

```go
func TestDoCommand(t *testing.T) {
    logger := logging.NewTestLogger(t)
    name := resource.NewName(resource.APINamespaceRDK.WithServiceType("generic"), "test")

    ctrl, err := NewController(context.Background(), nil, name, &Config{}, logger)
    require.NoError(t, err)

    cmd := map[string]interface{}{
        "command": "get_status",
    }

    resp, err := ctrl.(*controller).DoCommand(context.Background(), cmd)
    require.NoError(t, err)
    assert.Equal(t, "ok", resp["status"])
}
```

## Background Goroutine with Cancellation

```go
type controller struct {
    cancelCtx  context.Context
    cancelFunc func()
    // ...
}

func NewController(...) (resource.Resource, error) {
    cancelCtx, cancelFunc := context.WithCancel(context.Background())

    c := &controller{
        cancelCtx:  cancelCtx,
        cancelFunc: cancelFunc,
    }

    // Start background work
    go c.runBackgroundLoop()

    return c, nil
}

func (c *controller) runBackgroundLoop() {
    ticker := time.NewTicker(time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-c.cancelCtx.Done():
            return
        case <-ticker.C:
            // Do periodic work
        }
    }
}

func (c *controller) Close(ctx context.Context) error {
    c.cancelFunc() // Signals background goroutines to stop
    return nil
}
```
