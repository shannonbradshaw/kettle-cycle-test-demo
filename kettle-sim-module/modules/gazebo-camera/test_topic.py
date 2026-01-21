#!/usr/bin/env python3
"""Test that the Gazebo camera topic is publishing images."""

import time
import sys

try:
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image as GzImage
except ImportError:
    print("ERROR: gz-transport13 or gz-msgs10 not installed")
    print("Install with: apt install python3-gz-transport13 python3-gz-msgs10")
    sys.exit(1)

TOPIC = "/camera"
received_image = False
image_info = {}

def callback(msg: GzImage):
    global received_image, image_info
    received_image = True
    image_info = {
        "width": msg.width,
        "height": msg.height,
        "pixel_format_type": msg.pixel_format_type,
        "data_size": len(msg.data)
    }

print(f"Subscribing to topic: {TOPIC}")
print("Waiting for image (10 seconds)...")

node = Node()
success = node.subscribe(GzImage, TOPIC, callback)

if not success:
    print(f"ERROR: Failed to subscribe to topic: {TOPIC}")
    print("\nAvailable topics:")
    import subprocess
    subprocess.run(["gz", "topic", "-l"])
    sys.exit(1)

# Wait up to 10 seconds for an image
for i in range(20):
    time.sleep(0.5)
    if received_image:
        break
    print(f"  Waiting... ({i+1}/20)")

if received_image:
    print("\nSUCCESS! Received image from Gazebo:")
    print(f"  Width:  {image_info['width']}")
    print(f"  Height: {image_info['height']}")
    print(f"  Format: {image_info['pixel_format_type']}")
    print(f"  Size:   {image_info['data_size']} bytes")
    sys.exit(0)
else:
    print("\nERROR: No image received after 10 seconds")
    print("The camera sensor may not be rendering.")
    print("\nCheck that:")
    print("  1. The simulation is unpaused")
    print("  2. Rendering is working (DISPLAY is set)")
    print("  3. The camera sensor has <always_on>1</always_on>")
    sys.exit(1)
