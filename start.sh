#!/bin/bash
set -e

echo "============================================"
echo "  NEXUS SYSTEM LAUNCH v2.0"
echo "============================================"

# Critical environment
unset FASTRTPS_DEFAULT_PROFILES_FILE

# Source ROS
source /opt/ros/humble/setup.bash

# Kill old processes
echo "[1/4] Cleaning up..."
pkill -f web_server 2>/dev/null || true
pkill -f mission_node 2>/dev/null || true
cd ~/rosbot-autonomy && docker compose -f nexus_demo.yaml down --remove-orphans 2>/dev/null || true

# Start Gazebo
echo "[2/4] Starting Gazebo..."
cd ~/rosbot-autonomy
docker compose -f nexus_demo.yaml up -d

# Wait for camera
echo "[3/4] Waiting for simulation..."
for i in $(seq 1 30); do
    sleep 1
    if ros2 topic list 2>/dev/null | grep -q "/rosbot2r/camera/image"; then
        echo "  ✅ Camera topic detected!"
        break
    fi
done

# Build & source workspace
echo "[4/4] Building workspace..."
cd ~/nexus_ws
colcon build --packages-select web_dashboard mission_controller 2>/dev/null
source install/setup.bash

# Start nodes
echo ""
echo "Starting Mission Controller..."
ros2 run mission_controller mission_node &
sleep 2

echo "Starting Web Dashboard..."
ros2 run web_dashboard web_server &

echo ""
echo "============================================"
echo "  🚀 NEXUS READY!"
echo "============================================"
echo "Dashboard: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop..."
echo ""

# Wait forever
wait
