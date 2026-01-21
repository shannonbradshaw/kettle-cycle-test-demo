"""Gazebo subprocess manager.

This module handles spawning and managing the Gazebo simulation process.
It supports headless mode by default, with optional GUI attachment.
"""

import asyncio
import logging
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GazeboMode(Enum):
    """Gazebo execution mode."""
    HEADLESS = "headless"  # Server only, no GUI
    GUI = "gui"            # Server with GUI
    EXTERNAL = "external"  # Don't start Gazebo, assume it's already running


@dataclass
class GazeboConfig:
    """Configuration for Gazebo manager."""
    world_file: str
    mode: GazeboMode = GazeboMode.HEADLESS
    verbose: bool = False
    startup_timeout: float = 30.0  # seconds to wait for Gazebo to start
    physics_update_rate: float = 1000.0  # Hz
    real_time_factor: float = 1.0


class GazeboManager:
    """Manages Gazebo simulation subprocess lifecycle.

    Spawns Gazebo in headless mode by default for lower resource usage.
    Supports external mode for debugging with GUI attached separately.
    """

    def __init__(self, config: GazeboConfig):
        """Initialize the Gazebo manager.

        Args:
            config: Gazebo configuration
        """
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._started = False

    @classmethod
    def get_default_world_path(cls) -> Path:
        """Get path to the default kettle world SDF file."""
        module_dir = Path(__file__).parent.parent.parent
        return module_dir / "worlds" / "kettle_world.sdf"

    def start(self) -> None:
        """Start the Gazebo simulation.

        Raises:
            RuntimeError: If Gazebo fails to start or is already running
        """
        with self._lock:
            if self._started:
                raise RuntimeError("Gazebo is already running")

            if self.config.mode == GazeboMode.EXTERNAL:
                logger.info("External mode: assuming Gazebo is already running")
                self._started = True
                return

            # Validate world file exists
            world_path = Path(self.config.world_file)
            if not world_path.exists():
                raise RuntimeError(f"World file not found: {world_path}")

            # Build command
            cmd = self._build_command()
            logger.info(f"Starting Gazebo: {' '.join(cmd)}")

            # Set environment for headless mode
            env = os.environ.copy()
            if self.config.mode == GazeboMode.HEADLESS:
                # Disable rendering for headless operation
                env["LIBGL_ALWAYS_SOFTWARE"] = "1"

            # Start process
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE if not self.config.verbose else None,
                    stderr=subprocess.PIPE if not self.config.verbose else None,
                    env=env,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "Gazebo not found. Ensure Gazebo Harmonic is installed."
                )

            # Wait for Gazebo to initialize
            if not self._wait_for_startup():
                self.stop()
                raise RuntimeError("Gazebo failed to start within timeout")

            self._started = True
            logger.info("Gazebo started successfully")

    def _build_command(self) -> list:
        """Build the Gazebo command line."""
        cmd = ["gz", "sim"]

        # Server-only mode for headless
        if self.config.mode == GazeboMode.HEADLESS:
            cmd.append("-s")  # Server only, no GUI

        # Verbose output
        if self.config.verbose:
            cmd.append("-v4")

        # Physics settings via environment (SDF overrides these anyway)
        # but we can set real-time factor
        cmd.extend(["--physics-engine", "gz-physics-dartsim-plugin"])

        # World file
        cmd.append(str(self.config.world_file))

        return cmd

    def _wait_for_startup(self) -> bool:
        """Wait for Gazebo to finish initializing.

        Returns:
            True if Gazebo started successfully, False on timeout
        """
        start_time = time.time()
        check_interval = 0.5  # seconds

        while time.time() - start_time < self.config.startup_timeout:
            # Check if process is still running
            if self._process.poll() is not None:
                # Process exited
                stdout, stderr = self._process.communicate()
                logger.error(f"Gazebo exited early. stderr: {stderr}")
                return False

            # Try to query Gazebo via gz topic
            try:
                result = subprocess.run(
                    ["gz", "topic", "-l"],
                    capture_output=True,
                    timeout=5.0,
                )
                if result.returncode == 0:
                    topics = result.stdout.decode().strip().split('\n')
                    # Look for world topic as indicator of successful startup
                    world_topic = f"/world/{self._get_world_name()}/stats"
                    if any(world_topic in t for t in topics):
                        return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            time.sleep(check_interval)

        logger.error(f"Gazebo startup timeout after {self.config.startup_timeout}s")
        return False

    def _get_world_name(self) -> str:
        """Extract world name from world file path."""
        return Path(self.config.world_file).stem

    def stop(self) -> None:
        """Stop the Gazebo simulation."""
        with self._lock:
            if not self._started:
                return

            if self.config.mode == GazeboMode.EXTERNAL:
                logger.info("External mode: not stopping Gazebo")
                self._started = False
                return

            if self._process is not None:
                logger.info("Stopping Gazebo...")

                # Try graceful shutdown first
                self._process.terminate()
                try:
                    self._process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    logger.warning("Gazebo did not terminate gracefully, killing")
                    self._process.kill()
                    self._process.wait()

                self._process = None

            self._started = False
            logger.info("Gazebo stopped")

    def is_running(self) -> bool:
        """Check if Gazebo is running."""
        with self._lock:
            if not self._started:
                return False

            if self.config.mode == GazeboMode.EXTERNAL:
                # For external mode, check if Gazebo topics are available
                try:
                    result = subprocess.run(
                        ["gz", "topic", "-l"],
                        capture_output=True,
                        timeout=2.0,
                    )
                    return result.returncode == 0
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    return False

            if self._process is None:
                return False

            return self._process.poll() is None

    def pause(self) -> None:
        """Pause the simulation."""
        self._send_world_control(pause=True)

    def unpause(self) -> None:
        """Unpause the simulation."""
        self._send_world_control(pause=False)

    def _send_world_control(self, pause: bool) -> None:
        """Send world control command."""
        try:
            cmd = ["gz", "service", "-s", f"/world/{self._get_world_name()}/control"]
            cmd.extend(["--reqtype", "gz.msgs.WorldControl"])
            cmd.extend(["--reptype", "gz.msgs.Boolean"])
            cmd.extend(["--timeout", "1000"])
            cmd.extend(["--req", f"pause: {str(pause).lower()}"])

            subprocess.run(cmd, capture_output=True, timeout=5.0)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Failed to send world control: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


# Singleton manager for shared Gazebo instance
_global_manager: Optional[GazeboManager] = None
_global_manager_lock = threading.Lock()


def get_global_manager() -> Optional[GazeboManager]:
    """Get the global Gazebo manager instance."""
    with _global_manager_lock:
        return _global_manager


def set_global_manager(manager: GazeboManager) -> None:
    """Set the global Gazebo manager instance."""
    global _global_manager
    with _global_manager_lock:
        _global_manager = manager


def shutdown_global_manager() -> None:
    """Shutdown and clear the global Gazebo manager."""
    global _global_manager
    with _global_manager_lock:
        if _global_manager is not None:
            _global_manager.stop()
            _global_manager = None
