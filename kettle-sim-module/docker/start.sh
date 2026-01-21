#!/bin/bash
#
# Kettle Simulation Container Startup Script
#
# Starts:
# 1. Static file server for web UI (port 3000)
# 2. Viam server with simulation module (port 8080)
#

set -e

echo "Starting Kettle Cycle Test Simulation..."

# Start web UI server in background
echo "Starting web UI on port 3000..."
cd /app/web/dist
python3 -m http.server 3000 &
WEB_PID=$!

# Give web server time to start
sleep 1

# Start viam-server
echo "Starting viam-server on port 8080..."
cd /app
exec viam-server -config /etc/viam/machine-config.json

# Cleanup on exit
trap "kill $WEB_PID 2>/dev/null" EXIT
