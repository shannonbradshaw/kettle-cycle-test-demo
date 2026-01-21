"""Kettle simulation module for Viam.

This module provides MuJoCo-based simulation components for the kettle cycle test demo:
- SimulatedArm: A simulated Lite6 arm using MuJoCo physics
- SimulatedForceSensor: A simulated force/torque sensor

Components use a shared MuJoCo simulation instance for physics.
"""

from .sim_arm import SimulatedArm
from .sim_force_sensor import SimulatedForceSensor
from .mujoco_sim import MuJoCoSimulation, MockSimulation

__all__ = [
    "SimulatedArm",
    "SimulatedForceSensor",
    "MuJoCoSimulation",
    "MockSimulation",
]
