#!/bin/bash
set -e

echo "╔════════════════════════════════════════╗"
echo "║     🪐 NEXUS ULTRA-LIGHT MODE                  ║"
echo "╚════════════════════════════════════════╝"

unset FASTRTPS_DEFAULT_PROFILES_FILE
source /opt/ros/humble/setup.bash

# Aggressive cleanup
echo "[1/3] Cleaning up..."
pkill -9 -f web_server 2>/dev/null || true
pkill -9 -f mission_node 2>/dev/null || true
pkill -f gazebo 2>/dev/null || true
pkill -f ros_gz_bridge 2>/dev/null || true
sleep 2

cd ~/rosbot-autonomy
docker compose -f nexus_final.yaml down --remove-orphans --timeout 5 2>/dev/null || true
sleep 3

echo "[2/3] Starting Gazebo..."
docker compose -f nexus_final.yaml up -d
sleep 25

cd ~/nexus_ws
if [ ! -d "install/web_dashboard/lib" ]; then
    colcon build --packages-select web_dashboard mission_controller 2>&1 | tail -3
fi
source install/setup.bash

echo "[3/3] Verifying..."
for i in $(seq 1 15); do
    if ros2 topic list 2>/dev/null | grep -q "/rosbot2r/camera/image"; then
        echo "       ✅ Camera ready!"
        break
    fi
    sleep 1
done

echo ""
echo "╔════════════════════════════════════════╗"
echo "║  🌐 http://localhost:8000                    ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "💡 To stop: Press Ctrl+C"

python3 ~/nexus_ws/src/web_dashboard/web_dashboard/web_server.py

echo ""
echo "Stopping..."
cd ~/rosbot-autonomy && docker compose -f nexus_final.yaml down --remove-orphans 2>/dev/null || true
echo "✅ Done."
