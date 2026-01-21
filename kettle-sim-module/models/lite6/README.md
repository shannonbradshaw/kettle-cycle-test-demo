# Lite6 Model Meshes

This directory is intended for Lite6 robot arm meshes.

## Obtaining Meshes

The Lite6 visual and collision meshes can be obtained from the xarm_ros repository:

```bash
git clone https://github.com/xArm-Developer/xarm_ros.git
cp -r xarm_ros/xarm_description/meshes/lite6/* meshes/
```

## Directory Structure

After copying, the structure should be:

```
meshes/
├── visual/
│   ├── base.stl
│   ├── link1.stl
│   ├── link2.stl
│   ├── link3.stl
│   ├── link4.stl
│   ├── link5.stl
│   └── link6.stl
└── collision/
    ├── base.stl
    ├── link1.stl
    ├── link2.stl
    ├── link3.stl
    ├── link4.stl
    ├── link5.stl
    └── link6.stl
```

## Note

The world SDF file (`worlds/kettle_world.sdf`) currently uses simplified
geometric shapes (cylinders) instead of the actual meshes. To use the real
meshes, update the SDF visual and collision elements to reference the mesh
files:

```xml
<visual name="visual">
  <geometry>
    <mesh>
      <uri>model://lite6/meshes/visual/link1.stl</uri>
    </mesh>
  </geometry>
</visual>
```
