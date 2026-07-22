#!/bin/bash
source /opt/ros/humble/setup.bash
source ~/nexus_ws/install/setup.bash
unset FASTRTPS_DEFAULT_PROFILES_FILE
python3 ~/nexus_ws/src/web_dashboard/web_dashboard/web_server.py
