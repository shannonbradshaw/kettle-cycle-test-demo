# Kettle Cycle Test Demo

A demonstration of automated cycle testing using the Viam robotics platform. A robotic arm repeatedly lifts a kettle, performs a pour motion, and sets it back down while capturing force profiles and images to detect handle degradation over time.

---

## What This Demo Shows

This demo demonstrates how Viam can power automated cycle testing for product R&D:

| Capability | What You'll See |
|------------|-----------------|
| **Hardware abstraction** | Swap arms or sensors by changing config, not code |
| **Hardware orchestration** | Robotic arm executing repeatable test cycles |
| **Trial management** | Start/stop continuous testing, track cycle counts |
| **Cloud data capture** | Force profiles, counts, and state captured automatically |
| **Conditional sync** | Only upload data during active trials |
| **Remote operation** | Control tests from anywhere via Viam app, CLI, or API |
| **Hot reload** | Update control code from anywhere without full redeployment |

---

## Quick Start

**Run a single test cycle:**
```bash
make test-cycle
```

**Start a continuous trial:**
```bash
make trial-start
```

**Check status:**
```bash
make trial-status
```

**Stop the trial:**
```bash
make trial-stop
```

---

## Documentation Guide

| Document | What You'll Learn |
|----------|-------------------|
| [Viam Introduction](./01-viam-introduction.md) | What Viam is and core concepts |
| [Demo Architecture](./02-architecture.md) | How the demo components fit together |

---

## Hardware

| Component | Model | Purpose |
|-----------|-------|---------|
| Robot arm | UFactory Lite6 | Lifts and moves the kettle |
| Load cell | (via MCP3008 ADC) | Measures force during put-down |
| Compute | Raspberry Pi / Linux host | Runs viam-server and module |

---

## Software Components

| Component | Type | Purpose |
|-----------|------|---------|
| `cycle-tester` | Service | Orchestrates cycles, manages trial lifecycle |
| `trial-sensor` | Sensor | Exposes controller state for data capture |
| `force-sensor` | Sensor | Captures force profiles during put-down |
| `resting-position` | Switch | Saved arm pose for "kettle down" |
| `pour-prep-position` | Switch | Saved arm pose for "kettle lifted" |

---

## Current Status

**Milestone 4 of 14 complete.** The demo currently implements:

- Single cycle execution (lift → pour prep → put down)
- Trial lifecycle (start/stop continuous cycling)
- Force sensor capturing load cell data during put-down
- Conditional data capture (only syncs during active trials)

Future milestones will add:
- Camera integration for visual failure detection
- CV-based crack/defect detection
- Alerting on detected failures
- Multi-rig fleet management

---

## Getting Started

1. **New to Viam?** Start with [Viam Introduction](./01-viam-introduction.md)
2. **Want to understand the structure?** Read [Architecture](./02-architecture.md)
