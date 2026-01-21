# Kettle Simulation Module - Docker Image
#
# This Dockerfile creates a container with:
# - MuJoCo physics simulation
# - Viam server with kettle-sim module
# - Web-based 3D visualizer
#
# Build:
#   docker build -t kettle-sim .
#
# Run:
#   docker run -p 8080:8080 -p 3000:3000 kettle-sim

FROM python:3.11-slim

# Install system dependencies for MuJoCo and viam-server
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install viam-server
RUN curl -fsSL https://storage.googleapis.com/packages.viam.com/apps/viam-server/viam-server-stable-x86_64 \
    -o /usr/local/bin/viam-server \
    && chmod +x /usr/local/bin/viam-server

# Set up working directory
WORKDIR /app

# Copy Python module
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY models/ ./models/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# Copy and build web UI
COPY web/ ./web/
WORKDIR /app/web
RUN npm install && npm run build
WORKDIR /app

# Copy configuration and startup script
COPY docker/machine-config.json /etc/viam/machine-config.json
COPY docker/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports
# 8080: viam-server gRPC/WebRTC
# 3000: Web UI
EXPOSE 8080 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

# Start services
CMD ["/app/start.sh"]
