# Kettle Simulation Module

Gazebo Harmonic-based simulation module for the kettle cycle test demo. Provides simulated xArm6 robot arm, cameras, and force sensors that can be controlled via Viam's standard component APIs.

## Architecture

The simulation uses Gazebo Harmonic for physics and rendering, with Viam bridge modules that translate between Gazebo topics and Viam component APIs. This allows the simulation configuration to be nearly identical to real hardware configuration - just change the module, keep everything else.

```
┌────────────────────────────────────────────────────────────────┐
│  Docker Container                                              │
│  ┌──────────────────┐    ┌──────────────────────────────────┐ │
│  │  Gazebo Harmonic │    │  viam-server                     │ │
│  │  ┌────────────┐  │    │  ┌────────────────────────────┐  │ │
│  │  │ xArm6      │◄─┼────┼─►│ gazebo-arm module         │  │ │
│  │  │ Kettle     │  │    │  │ (Viam arm ↔ Gazebo joints) │  │ │
│  │  │ Camera     │◄─┼────┼─►│ gazebo-camera module      │  │ │
│  │  │ Force Plate│◄─┼────┼─►│ gazebo-sensor module      │  │ │
│  │  └────────────┘  │    │  └────────────────────────────┘  │ │
│  └──────────────────┘    └──────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
           ▲                                ▲
           │ gz-transport                   │ gRPC/WebRTC
           ▼                                ▼
    Gazebo Topics                     Viam Clients
```

## Bridge Modules

### gazebo-arm (`viam-labs:arm:gazebo`)

Bridges Viam arm API to Gazebo joint position commands.

**Configuration:**
```json
{
  "name": "arm",
  "namespace": "rdk",
  "type": "arm",
  "model": "viam-labs:arm:gazebo",
  "attributes": {
    "model_name": "xarm6",
    "num_joints": 6
  }
}
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_name` | string | "xarm6" | Gazebo model name |
| `world_name` | string | "kettle_test" | Gazebo world name |
| `num_joints` | int | 6 | Number of arm joints |

### gazebo-camera (`viam-labs:camera:gazebo`)

Bridges Gazebo camera images to Viam camera API.

**Configuration:**
```json
{
  "name": "overhead-camera",
  "namespace": "rdk",
  "type": "camera",
  "model": "viam-labs:camera:gazebo",
  "attributes": {
    "topic": "/overhead_camera/image",
    "width": 1280,
    "height": 720
  }
}
```

### gazebo-sensor (`viam-labs:sensor:gazebo-contact`)

Bridges Gazebo contact sensors to Viam sensor API. Supports capture mode for cycle testing.

**Configuration:**
```json
{
  "name": "force-plate-sensor",
  "namespace": "rdk",
  "type": "sensor",
  "model": "viam-labs:sensor:gazebo-contact",
  "attributes": {
    "topic": "/force_plate/contact",
    "use_mock": false
  }
}
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `topic` | string | "/force_plate/contact" | Gazebo contact topic |
| `use_mock` | bool | false | Use mock data if contact sensing unavailable |

**DoCommand Interface:**
- `start_capture`: Begin force capture (params: `trial_id`, `cycle_count`)
- `end_capture`: End capture and return statistics (max_force, avg_force, contact_detected)
- `get_capture_status`: Check capture state

## Models

### xArm6

A 6-DOF robot arm based on the UFACTORY xArm6 specifications:
- 6 revolute joints with realistic limits and inertia
- Gripper attachment point
- Joint position controllers with PID gains
- RealSense D435 camera mount (optional)

### Kettle

A simulated kettle with:
- Body, handle, spout, and lid geometry
- Contact sensor on bottom for force detection
- Appropriate mass and inertia

### World: kettle_test.sdf

Complete simulation world including:
- Ground plane and work table
- Force plate with contact sensor
- xArm6 mounted on table
- Kettle on force plate
- Overhead camera

## Quick Start

### Docker Deployment

1. Build and run:
   ```bash
   cd kettle-sim-module
   docker-compose up --build
   ```

2. For SSH tunnel deployment (recommended for security):
   ```bash
   # On server
   docker-compose up --build

   # From client
   ssh -L 8080:localhost:8080 user@server
   ```

3. Connect to viam-server at `localhost:8080`

### Prerequisites

The Docker image includes all dependencies. For local development:

- Ubuntu 22.04+
- Gazebo Harmonic (`apt install gz-harmonic`)
- Python 3.10+
- `python3-gz-transport13` and `python3-gz-msgs10`
- viam-sdk (`pip install viam-sdk`)

## File Structure

```
kettle-sim-module/
├── models/
│   ├── kettle/
│   │   ├── model.config
│   │   └── model.sdf
│   └── xarm6/
│       ├── model.config
│       └── model.sdf
├── modules/
│   ├── gazebo-arm/
│   │   ├── main.py
│   │   ├── meta.json
│   │   └── requirements.txt
│   ├── gazebo-camera/
│   │   ├── main.py
│   │   ├── meta.json
│   │   └── requirements.txt
│   └── gazebo-sensor/
│       ├── main.py
│       ├── meta.json
│       └── requirements.txt
├── worlds/
│   └── kettle_test.sdf
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── viam-config.json
└── README.md
```

## Simulation vs Real Hardware

The key principle: **change the module, keep everything else.**

| Component | Simulation | Real Hardware |
|-----------|------------|---------------|
| Arm | `viam-labs:arm:gazebo` | `ufactory:arm:xarm6` |
| Camera | `viam-labs:camera:gazebo` | `viam:camera:realsense` |
| Force Sensor | `viam-labs:sensor:gazebo-contact` | `viam:sensor:load-cell` |

All other configuration (services, data capture, business logic) stays the same.

## License

Apache-2.0
