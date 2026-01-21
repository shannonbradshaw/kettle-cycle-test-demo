#!/bin/bash
set -e

# Start virtual framebuffer for headless rendering
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Wait for Xvfb to be ready
sleep 2

# Start Gazebo simulation in background
echo "Starting Gazebo simulation..."
gz sim -r /app/worlds/kettle_test.sdf &
GZ_PID=$!

# Wait for Gazebo to initialize
echo "Waiting for Gazebo to initialize..."
sleep 5

# Start Viam server with config
echo "Starting viam-server..."
exec /usr/local/bin/viam-server -config /app/viam-config.json
