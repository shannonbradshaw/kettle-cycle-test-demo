# Introduction to Viam

Viam is a software platform for building, deploying, and managing robotics applications. It handles the infrastructure so you can focus on your application logic.

---

## The Core Idea

With Viam, you:

1. **Declare your hardware in JSON config** — Viam pulls drivers automatically
2. **Write control logic against well-defined APIs** — Same code works across hardware
3. **Develop from anywhere** — Run code on your laptop against remote hardware
4. **Deploy through a registry** — Push updates, machines pull them automatically

Without Viam, you'd need to write device drivers, configure networking, build data pipelines, and figure out software deployment. Viam handles all of that.

---

## Key Concepts

### Machines

A **machine** is any device running `viam-server` — the service that manages your hardware and runs your application code. A machine can be a robot arm, a Raspberry Pi with sensors, or a full industrial work cell.

Every machine has:
- A unique identity in Viam's cloud
- A JSON configuration defining its components and services
- Remote access through Viam's infrastructure (no VPN required)

### Components

**Components** are hardware abstractions. Each component type has a standard API:

| Component Type | Examples | API Methods |
|----------------|----------|-------------|
| `arm` | Robot arms | `MoveToPosition`, `JointPositions`, `IsMoving` |
| `camera` | USB cameras, depth cameras | `GetImage`, `GetPointCloud` |
| `sensor` | Temperature, force, humidity | `Readings` |
| `motor` | DC motors, steppers, servos | `SetPower`, `GoFor`, `Position` |
| `switch` | Digital I/O, relays | `GetPosition`, `SetPosition` |

**Why this matters:** Your code calls `arm.MoveToPosition()`, not `xArm6.MoveToPosition()`. Swap hardware by changing config, not code.

### Services

**Services** provide capabilities that work across components:

| Service | What It Does |
|---------|--------------|
| `motion` | Plans collision-free paths for arms and bases |
| `vision` | Runs ML models for detection and classification |
| `data_manager` | Captures and syncs data to cloud |
| `mlmodel` | Loads and runs ML models on device |

Services are configured in JSON and accessed through consistent APIs.

### Modules

**Modules** extend Viam with custom functionality. A module can provide:
- New component types (drivers for unsupported hardware)
- New services (custom business logic)
- Both (like this demo's controller + sensors)

Modules are packaged and distributed through the **Viam Registry**. Add a module to your config:

```json
{
  "module_id": "viamdemo:kettle-cycle-test",
  "version": "latest"
}
```

Viam downloads it, installs dependencies, and manages its lifecycle.

### Data Capture

Viam can automatically capture data from any component:

```json
{
  "name": "my-sensor",
  "service_configs": [{
    "type": "data_manager",
    "attributes": {
      "capture_methods": [{
        "method": "Readings",
        "capture_frequency_hz": 1
      }]
    }
  }]
}
```

This captures sensor readings once per second and syncs them to Viam's cloud. Data survives network interruptions, queues locally, and syncs when connectivity returns.

### Fragments

**Fragments** are reusable configuration blocks. Define a camera-arm combination once, apply it to any number of machines. Fragments support variable substitution for machine-specific values.

---

## Development Workflow

Viam supports a progression from experimentation to production:

### Stage 1: Develop from Your IDE

Write code on your laptop. Run it against remote hardware over the network:

```
┌─────────────┐         ┌─────────────────┐
│ Your Laptop │ ──────► │ Remote Machine  │
│ (runs code) │   API   │ (has hardware)  │
└─────────────┘         └─────────────────┘
```

No SSH, no copying files. Your code calls `camera.GetImage()` and the image comes from the remote camera. Iterate quickly.

### Stage 2: Package as a Module

When your code is stable, package it as a module:

```
┌─────────────────────────────────────────┐
│            Machine                      │
│  ┌─────────────┐    ┌───────────────┐   │
│  │ Your Module │───►│ Hardware      │   │
│  │ (runs code) │    │ (same machine)│   │
│  └─────────────┘    └───────────────┘   │
└─────────────────────────────────────────┘
```

Now viam-server manages your code: starts on boot, restarts on failure, reconfigures when settings change.

### Stage 3: Deploy to Fleet

Push module updates to the Viam Registry. Machines pull updates automatically based on version policies. Roll out changes incrementally. Roll back if something goes wrong.

---

## Relevant Capabilities for Cycle Testing

| Capability | How It Helps |
|------------|--------------|
| **Hardware abstraction** | Swap arms, sensors, or cameras without rewriting code |
| **Remote access** | Monitor and control tests from anywhere |
| **Data capture** | Automatically log force profiles, images, state |
| **Conditional sync** | Only upload data during active trials |
| **Module system** | Package your test logic for deployment |
| **Hot reload** | Update code without full machine restart |
| **Fleet management** | Scale from one test rig to many |

---

## Learn More

- [Viam Documentation](https://docs.viam.com)
- [Module Registry](https://app.viam.com/registry)
- [SDKs](https://docs.viam.com/sdks/) (Python, Go, TypeScript, Flutter)

---

## Next

[Architecture →](./02-architecture.md) — How the demo components fit together
