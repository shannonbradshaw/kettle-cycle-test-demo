# Kettle Simulation Module

MuJoCo-based simulation module for the kettle cycle test demo. Provides a simulated Lite6 robot arm and force sensor that can be controlled via Viam's standard component APIs.

## Features

- **MuJoCo Physics**: High-fidelity physics simulation using MuJoCo
- **Viam Integration**: Standard arm and sensor component interfaces
- **Web Visualizer**: Browser-based 3D visualization using Three.js
- **Docker Deployment**: Easy containerized deployment

## Components

### SimulatedArm (`viamdemo:kettle-sim:lite6`)

A 6-DOF simulated robot arm implementing Viam's arm interface.

**Configuration:**
```json
{
  "name": "arm",
  "api": "rdk:component:arm",
  "model": "viamdemo:kettle-sim:lite6",
  "attributes": {
    "use_mock": false,
    "model_path": "/path/to/custom/model.xml"
  }
}
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_mock` | bool | false | Use mock simulation (no MuJoCo required) |
| `model_path` | string | (built-in) | Path to custom MJCF model file |

### SimulatedForceSensor (`viamdemo:kettle-sim:force-sensor`)

A force/torque sensor with capture state machine for cycle testing.

**Configuration:**
```json
{
  "name": "force-sensor",
  "api": "rdk:component:sensor",
  "model": "viamdemo:kettle-sim:force-sensor",
  "attributes": {
    "use_mock": false,
    "sample_rate_hz": 50,
    "buffer_size": 100,
    "zero_threshold": 5.0,
    "capture_timeout_ms": 10000
  }
}
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_mock` | bool | false | Use mock simulation |
| `sample_rate_hz` | int | 50 | Sampling rate during capture |
| `buffer_size` | int | 100 | Max samples to store |
| `zero_threshold` | float | 5.0 | Force (N) below which is "zero" |
| `capture_timeout_ms` | int | 10000 | Capture timeout in milliseconds |

**DoCommand Interface:**
- `start_capture`: Begin force capture (params: `trial_id`, `cycle_count`)
- `end_capture`: End capture and return statistics

## Quick Start

### Local Development

1. Install dependencies:
   ```bash
   pip install -e .
   ```

2. Run the module:
   ```bash
   python -m kettle_sim
   ```

### Docker Deployment

1. Build and run:
   ```bash
   docker-compose up --build
   ```

2. For SSH tunnel deployment:
   ```bash
   # On server
   docker-compose up --build

   # From client
   ssh -L 3000:localhost:3000 -L 8080:localhost:8080 user@server
   ```

3. Open browser to `http://localhost:3000`

## Web Visualizer

The web visualizer provides a real-time 3D view of the simulated robot arm.

### Features

- Real-time joint position rendering
- Force sensor data display
- Trial control (start/stop)
- Single cycle execution
- Connection status monitoring

### Development

```bash
cd web
npm install
npm run dev
```

### Building

```bash
cd web
npm run build
```

## Testing

Run unit tests:
```bash
pytest tests/
```

Tests use `MockSimulation` to avoid MuJoCo dependency.

## Architecture

```
┌──────────────────────┐          ┌─────────────────────────────────┐
│  Browser             │  WebRTC/ │  Server (Docker Container)      │
│  ┌────────────────┐  │  gRPC    │  ┌───────────────────────────┐  │
│  │ Web App        │  │◄────────►│  │ viam-server               │  │
│  │ - Three.js viz │  │          │  │  ├── kettle-sim-module    │  │
│  │ - Viam TS SDK  │  │          │  │  │   └── MuJoCo physics   │  │
│  │ - Controls UI  │  │          │  │  └── cycle-test-controller│  │
│  └────────────────┘  │          │  └───────────────────────────┘  │
└──────────────────────┘          └─────────────────────────────────┘
```

## File Structure

```
kettle-sim-module/
├── src/kettle_sim/
│   ├── __init__.py
│   ├── __main__.py          # Module entry point
│   ├── mujoco_sim.py        # MuJoCo wrapper
│   ├── sim_arm.py           # Simulated arm component
│   └── sim_force_sensor.py  # Simulated force sensor
├── models/
│   └── lite6.xml            # MJCF robot model
├── tests/
│   ├── test_mujoco_sim.py
│   ├── test_sim_arm.py
│   └── test_sim_force_sensor.py
├── web/
│   ├── src/
│   │   ├── main.ts
│   │   ├── viam-client.ts
│   │   └── robot-visualizer.ts
│   ├── index.html
│   └── package.json
├── docker/
│   ├── machine-config.json
│   └── start.sh
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

## License

Apache-2.0
