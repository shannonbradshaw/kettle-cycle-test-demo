# Viam Gazebo Camera Module

A Viam module that bridges Gazebo simulation cameras to Viam's camera API.

## Overview

This module subscribes to a Gazebo camera topic and exposes it as a standard Viam camera component. This allows you to use simulated cameras in Gazebo with the same Viam code you'd use for real cameras.

## Requirements

- Python 3.10+
- Gazebo Harmonic (gz-sim)
- Python Gazebo transport bindings:
  ```bash
  apt install python3-gz-transport13 python3-gz-msgs10
  ```
- Viam SDK:
  ```bash
  pip install viam-sdk Pillow
  ```

## Configuration

Add this module to your Viam robot configuration:

```json
{
  "modules": [
    {
      "name": "gazebo-camera",
      "executable_path": "/path/to/viam-gazebo-camera/main.py",
      "type": "local"
    }
  ],
  "components": [
    {
      "name": "sim-camera",
      "api": "rdk:component:camera",
      "model": "viam-labs:camera:gazebo",
      "attributes": {
        "topic": "/world/camera_world/model/camera_post/link/camera_link/sensor/camera/image"
      }
    }
  ]
}
```

### Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `topic` | string | Yes | The Gazebo topic to subscribe to |
| `width` | number | No | Image width (auto-detected from topic) |
| `height` | number | No | Image height (auto-detected from topic) |

## Finding the Camera Topic

In Gazebo, camera topics follow this pattern:
```
/world/{world_name}/model/{model_name}/link/{link_name}/sensor/{sensor_name}/image
```

List available topics with:
```bash
gz topic -l
```

Echo a topic to verify it's publishing:
```bash
gz topic -e -t /world/camera_world/model/camera_post/link/camera_link/sensor/camera/image
```

## Usage

Once configured, use the camera like any other Viam camera:

```python
from viam.robot.client import RobotClient
from viam.components.camera import Camera

async def main():
    robot = await RobotClient.at_address("localhost:8080", RobotClient.Options())

    camera = Camera.from_robot(robot, "sim-camera")
    image = await camera.get_image()

    # Save the image
    with open("snapshot.jpg", "wb") as f:
        f.write(image.data)

    await robot.close()
```

## Development

### Running locally

1. Start Gazebo with a world that has a camera:
   ```bash
   gz sim /path/to/camera_world.sdf
   ```

2. Verify the camera topic is publishing:
   ```bash
   gz topic -l | grep image
   ```

3. Run viam-server with this module configured

### Testing the module directly

```bash
python3 main.py --socket /tmp/viam-gazebo-camera.sock
```

## Troubleshooting

### "No image received from Gazebo"
- Verify Gazebo is running: `gz sim --version`
- Check topic exists: `gz topic -l`
- Verify topic is publishing: `gz topic -e -t <topic_name>`

### "gz-transport13 not available"
- Install the Python bindings: `apt install python3-gz-transport13 python3-gz-msgs10`
- Make sure you're using Python 3 (not Python 2)

### Image is black
- Check the world has lighting
- Verify camera pose isn't inside an object
- Check `<always_on>1</always_on>` in camera sensor config

## License

Apache 2.0
