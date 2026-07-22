#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           🤖 NEXUS HACKATHON LAUNCHER v2.1            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

unset FASTRTPS_DEFAULT_PROFILES_FILE
source /opt/ros/humble/setup.bash

echo "[1/5] Cleaning up..."
pkill -f web_server 2>/dev/null || true
pkill -f mission_node 2>/dev/null || true
cd ~/rosbot-autonomy && docker compose -f nexus_final.yaml down --remove-orphans 2>/dev/null || true
sleep 2
echo "       ✅ Done"

echo "[2/5] Starting Gazebo..."
cd ~/rosbot-autonomy
docker compose -f nexus_final.yaml up -d
echo "       Waiting..."
for i in $(seq 1 30); do
    sleep 1
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' nexus_robot_demo 2>/dev/null || echo "starting")
    if [ "$STATUS" = "healthy" ]; then echo "       ✅ Gazebo ready!"; break; fi
done

echo "[3/5] Building workspace..."
cd ~/nexus_ws
colcon build --packages-select web_dashboard mission_controller 2>&1 | grep -E "(Starting|Finished|Summary)" || true
source install/setup.bash
echo "       ✅ Built"

echo "[4/5] Verifying camera..."
for i in $(seq 1 15); do
    if ros2 topic list 2>/dev/null | grep -q "/rosbot2r/camera/image"; then echo "       ✅ Camera topic found!"; break; fi
    sleep 1
done

echo "[5/5] Launching nodes..."
echo ""

# Start Mission Controller (direct Python)
python3 ~/nexus_ws/src/mission_controller/mission_controller/mission_node.py &
MISSION_PID=$!
sleep 2
echo "       ✅ Mission Controller (PID: $MISSION_PID)"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  🌐  OPEN: http://localhost:8000                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop..."
echo ""

# Start Web Dashboard (direct Python)
python3 ~/nexus_ws/src/web_dashboard/web_dashboard/web_server.py

echo ""
echo "Stopping..."
kill $MISSION_PID 2>/dev/null || true
cd ~/rosbot-autonomy && docker compose -f nexus_final.yaml down --remove-orphans 2>/dev/null || true
echo "✅ Stopped."
