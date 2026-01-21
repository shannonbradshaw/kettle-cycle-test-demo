#!/usr/bin/env python3
"""
Viam module that bridges a Gazebo camera to Viam's camera API.

This module subscribes to a Gazebo camera topic (gz.msgs.Image) and
exposes it through the standard Viam camera interface.
"""

import asyncio
import io
import sys
from threading import Lock, Thread
from typing import Any, Dict, List, Mapping, Optional, Tuple

from PIL import Image as PILImage

from viam.components.camera import Camera
from viam.logging import getLogger
from viam.media.video import CameraMimeType, ViamImage
from viam.module.module import Module
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName, ResponseMetadata
from viam.resource.base import ResourceBase
from viam.resource.registry import Registry, ResourceCreatorRegistration
from viam.resource.types import Model, ModelFamily
from viam.utils import ValueTypes

# Gazebo transport imports
try:
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image as GzImage
    GZ_AVAILABLE = True
except ImportError:
    GZ_AVAILABLE = False
    print("WARNING: gz-transport13 not available. Install with: apt install python3-gz-transport13 python3-gz-msgs10")

LOGGER = getLogger(__name__)


class GazeboCamera(Camera):
    """
    A Viam camera component that reads images from a Gazebo simulation.

    Attributes:
        topic: The Gazebo topic to subscribe to (e.g., "/world/my_world/model/robot/link/camera_link/sensor/camera/image")
    """

    MODEL = Model(ModelFamily("viam-labs", "camera"), "gazebo")

    def __init__(self, name: str):
        super().__init__(name)
        self._node: Optional[Any] = None
        self._latest_image: Optional[bytes] = None
        self._image_lock = Lock()
        self._topic: str = ""
        self._width: int = 640
        self._height: int = 480
        self._subscribed: bool = False
        self._transport_thread: Optional[Thread] = None

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> "GazeboCamera":
        """Create a new GazeboCamera instance."""
        camera = cls(config.name)
        camera.reconfigure(config, dependencies)
        return camera

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> List[str]:
        """Validate the component configuration."""
        errors = []
        attrs = config.attributes.fields

        if "topic" not in attrs or not attrs["topic"].string_value:
            errors.append("'topic' attribute is required")

        if not GZ_AVAILABLE:
            errors.append("gz-transport13 Python bindings not available")

        return errors

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> None:
        """Reconfigure the camera with new settings."""
        attrs = config.attributes.fields

        new_topic = attrs["topic"].string_value if "topic" in attrs else ""

        if "width" in attrs:
            self._width = int(attrs["width"].number_value)
        if "height" in attrs:
            self._height = int(attrs["height"].number_value)

        # If topic changed, resubscribe
        if new_topic != self._topic:
            self._topic = new_topic
            self._setup_subscription()

        LOGGER.info(f"Configured GazeboCamera '{self.name}' on topic: {self._topic}")

    def _setup_subscription(self) -> None:
        """Subscribe to the Gazebo camera topic."""
        if not GZ_AVAILABLE:
            LOGGER.error("Cannot subscribe: gz-transport13 not available")
            return

        if not self._topic:
            LOGGER.error("Cannot subscribe: no topic configured")
            return

        # Create new node if needed
        if self._node is None:
            self._node = Node()

        def callback(msg: GzImage) -> None:
            """Called when a new image is received from Gazebo."""
            with self._image_lock:
                self._latest_image = msg.data
                self._width = msg.width
                self._height = msg.height

        # Subscribe to the camera topic
        success = self._node.subscribe(GzImage, self._topic, callback)

        if success:
            self._subscribed = True
            LOGGER.info(f"Subscribed to Gazebo camera topic: {self._topic}")
        else:
            self._subscribed = False
            LOGGER.error(f"Failed to subscribe to Gazebo topic: {self._topic}")

    async def get_image(
        self,
        mime_type: str = "",
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> ViamImage:
        """Get the latest image from the Gazebo camera."""
        with self._image_lock:
            if self._latest_image is None:
                raise Exception(
                    f"No image received from Gazebo yet on topic: {self._topic}. "
                    "Make sure Gazebo is running and the topic exists."
                )

            # Convert raw RGB bytes to PIL Image
            try:
                img = PILImage.frombytes(
                    "RGB", (self._width, self._height), self._latest_image
                )
            except Exception as e:
                raise Exception(f"Failed to decode image: {e}")

            # Convert to JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            jpeg_bytes = buffer.getvalue()

            return ViamImage(jpeg_bytes, CameraMimeType.JPEG)

    async def get_images(
        self,
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Tuple[List[ViamImage], ResponseMetadata]:
        """Get images from the camera."""
        img = await self.get_image(timeout=timeout)
        return [img], ResponseMetadata()

    async def get_point_cloud(
        self,
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Tuple[bytes, str]:
        """Point cloud not supported for basic RGB camera."""
        raise NotImplementedError(
            "Point cloud not supported. Use a depth camera module instead."
        )

    async def get_properties(
        self,
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Camera.Properties:
        """Return camera properties."""
        return Camera.Properties(
            supports_pcd=False,
            intrinsic_parameters=None,
            distortion_parameters=None,
        )

    async def close(self) -> None:
        """Clean up resources."""
        LOGGER.info(f"Closing GazeboCamera '{self.name}'")
        # Node cleanup happens automatically


async def main():
    """Main entry point for the module."""
    # Register the camera model
    Registry.register_resource_creator(
        Camera.SUBTYPE,
        GazeboCamera.MODEL,
        ResourceCreatorRegistration(GazeboCamera.new, GazeboCamera.validate_config),
    )

    # Create and start the module
    module = Module.from_args()
    module.add_model_from_registry(Camera.SUBTYPE, GazeboCamera.MODEL)
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
