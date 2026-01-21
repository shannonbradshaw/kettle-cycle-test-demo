"""Kettle simulation module entry point.

This is the main entry point for the Viam module. It registers
the simulated arm and force sensor components with the Viam registry.
"""

import asyncio
import logging
import signal
import sys

from viam.components.arm import Arm
from viam.components.sensor import Sensor
from viam.module.module import Module
from viam.resource.registry import Registry, ResourceCreatorRegistration

from .sim_arm import SimulatedArm, LITE6_MODEL
from .sim_force_sensor import SimulatedForceSensor, FORCE_SENSOR_MODEL
from .gazebo_manager import shutdown_global_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def register_components() -> None:
    """Register all simulation components with Viam."""
    logger.info("Registering simulation components...")

    # Register SimulatedArm
    Registry.register_resource_creator(
        Arm.SUBTYPE,
        LITE6_MODEL,
        ResourceCreatorRegistration(
            SimulatedArm.new,
            SimulatedArm.validate_config,
        ),
    )
    logger.info(f"Registered arm model: {LITE6_MODEL}")

    # Register SimulatedForceSensor
    Registry.register_resource_creator(
        Sensor.SUBTYPE,
        FORCE_SENSOR_MODEL,
        ResourceCreatorRegistration(
            SimulatedForceSensor.new,
            SimulatedForceSensor.validate_config,
        ),
    )
    logger.info(f"Registered sensor model: {FORCE_SENSOR_MODEL}")


async def main() -> None:
    """Main entry point for the module."""
    logger.info("Starting kettle-sim module...")

    # Register components
    register_components()

    # Create and start the module
    module = Module.from_args()

    # Add models to the module
    module.add_model_from_registry(Arm.SUBTYPE, LITE6_MODEL)
    module.add_model_from_registry(Sensor.SUBTYPE, FORCE_SENSOR_MODEL)

    logger.info("Module started, waiting for connections...")

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, cleaning up...")
        shutdown_global_manager()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await module.start()
    finally:
        logger.info("Module shutting down...")
        shutdown_global_manager()


if __name__ == "__main__":
    asyncio.run(main())
