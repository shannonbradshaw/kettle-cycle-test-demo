"""Kettle simulation module for Viam.

This module provides Gazebo-based simulation components for the kettle cycle test demo:
- SimulatedArm: A simulated Lite6 arm using Gazebo physics
- SimulatedForceSensor: A simulated force/torque sensor

Components use gz-transport to communicate with Gazebo simulation.
"""

from .sim_arm import SimulatedArm
from .sim_force_sensor import SimulatedForceSensor
from .gazebo_manager import GazeboManager
from .gazebo_bridge import GazeboBridge

__all__ = [
    "SimulatedArm",
    "SimulatedForceSensor",
    "GazeboManager",
    "GazeboBridge",
]
