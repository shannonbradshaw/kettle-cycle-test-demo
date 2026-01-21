# Gazebo Harmonic simulation for Kettle Cycle Test
# Bridges Gazebo to Viam via custom modules

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Gazebo Harmonic repository
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    && curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

# Install Gazebo Harmonic and dependencies
RUN apt-get update && apt-get install -y \
    gz-harmonic \
    python3-pip \
    python3-gz-transport13 \
    python3-gz-msgs10 \
    xvfb \
    mesa-utils \
    libgl1-mesa-dri \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Install Viam SDK
RUN pip3 install viam-sdk>=0.20.0

# Install viam-server
RUN curl -o /usr/local/bin/viam-server \
    https://storage.googleapis.com/packages.viam.com/apps/viam-server/viam-server-stable-x86_64.AppImage \
    && chmod +x /usr/local/bin/viam-server

# Create app directory
WORKDIR /app

# Copy models
COPY models/ /app/models/

# Copy worlds
COPY worlds/ /app/worlds/

# Copy Viam bridge modules
COPY modules/ /app/modules/

# Copy config and entrypoint
COPY viam-config.json /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Set Gazebo resource path to find custom models
ENV GZ_SIM_RESOURCE_PATH=/app/models

# Expose Viam server port
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
