#!/usr/bin/env python3
"""NEXUS Mission Controller v3.1 — Command-Responsive"""

import time
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String, Bool, Empty
from std_srvs.srv import Trigger, SetBool, SetBool_Request, SetBool_Response


class MissionController(Node):
    def __init__(self):
        super().__init__('nexus_mission_controller')
        
        self.get_logger().info('🎯️ NEXUS Mission Controller v3.1')
        self.get_logger().info('   Listening for commands...')
        
        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/rosbot2r/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/rosbot2r/mission_status', 10)
        self.target_found_pub = self.create_publisher(Bool, '/rosbot2r/target_found', 10)
        self.findings_pub = self.create_publisher(String, '/rosbot2r/findings', 10)
        
        # Subscribers
        sensor_qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=5)
        self.create_subscription(LaserScan, '/rosbot2r/scan', self._laser_cb, sensor_qos)
        self.create_subscription(String, '/rosbot2r/mission_command', self._command_cb, 10)
        self.create_subscription(String, '/rosbot2r/detections', self._detection_cb, 10)
        
        # State machine
        self.state = "IDLE"
        self.target_object = None
        self.exploring = False
        self.avoiding = False
        self.avoid_start = 0
        self.scan_start = 0
        self.drive_start = 0
        self.turn_start = 0
        
        # Exploration parameters
        self.drive_time = 3.0      # seconds of driving
        self.scan_time = 4.0       # seconds of rotating
        self.turn_time = 2.0       # seconds of turning
        self.forward_speed = 0.25
        self.turn_speed = 0.4
        self.avoid_speed = 0.5
        
        # Detection tracking
        self.current_detections = []
        self.all_detections = []
        self.unique_objects_found = set()
        self.target_confirmed = False
        
        # Statistics
        self.scans_completed = 0
        self.distance_traveled = 0.0
        self.mission_start_time = None
        self.total_detections = 0
        
        # Control loop timer (20 Hz)
        self.create_timer(0.05, self._control_loop)
        # Status reporter timer (5 seconds)
        self.create_timer(5.0, self._report_status)
        
        self.get_logger().info('✅ Mission Controller READY!')
        self.get_logger().info('   Waiting for /rosbot2r/mission_command messages...')
    
    def _command_cb(self, msg: String):
        """Handle incoming mission commands from dashboard"""
        cmd = msg.data.strip().upper()
        self.get_logger().info(f'📡 Received command: {cmd}')
        
        if cmd == "START":
            self._start_mission()
        elif cmd == "STOP":
            self._stop_mission()
        elif cmd == "RESET":
            self._reset_mission()
        elif cmd == "PAUSE":
            self._pause_mission()
        elif cmd == "RESUME":
            self._resume_mission()
        elif cmd == "TARGET:SET":
            try:
                target = json.loads(msg.data).get("target", "chair")
                self.target_object = target
                self.get_logger.info(f'🎯 Target set to: {self.target_object}')
            except Exception as e:
                self.get_logger.error(f'Failed to parse target: {e}')
    
    def _start_mission(self):
        """Start autonomous exploration mission"""
        if self.state == "EXPLORING" or self.exploring:
            self.get_logger().warn('⚠️ Already exploring! Stop first!')
            return
        
        self.state = "EXPLORING"
        self.exploring = True
        self.mission_start_time = time.time()
        self.distance_traveled = 0.0
        self.scans_completed = 0
        self.unique_objects_found = set()
        self.all_detections = []
        self.target_confirmed = False
        
        self.get_logger().info('🚀🚀🚀 MISSION STARTED!')
        self._publish_status()
    
    def _stop_mission(self):
        """Stop autonomous mode, return to IDLE"""
        self.state = "IDLE"
        self.exploring = False
        self._publish_status()
        self.get_logger().info('⏹️ Mission STOPPED - Back to IDLE')
    
    def _reset_mission(self):
        """Reset everything for fresh mission"""
        self._stop_mission()
        self.target_object = None
        self.current_detections = []
        self.all_detections = []
        self.unique_objects_found = set()
        self.target_confirmed = False
        self.scans_completed = 0
        self.distance_traveled = 0.0
        self.get_logger.info('🔄 MISSION RESET')
    
    def _pause_mission(self):
        """Pause exploration temporarily"""
        if self.state != "EXPLORING":
            return
        self.prev_state = self.state
        self.state = "PAUSED"
        self.get_logger.info('⏸ Mission PAUSED')
    
    def _resume_mission(self):
        """Resume from pause"""
        if self.state != "PAUSED":
            return
        self.state = self.prev_state
        self.get_logger.info▶️ Mission RESUMED')
    
    def _laser_cb(self, msg: LaserScan):
        """Process LiDAR data for obstacle avoidance"""
        if len(msg.ranges) == 0:
            return
        
        front_ranges = [r for r in msg.ranges[mid_point-30:mid_point+30] if 0.1 < r < 5.0]
        
        if front_ranges:
            min_dist = min(front_ranges)
            
            if min_dist < 0.5 and not self.avoiding:
                self.avoiding = True
                self.avoid_start = time.time()
                self.get_logger().warn(f'⚠️ OBSTACLE at {min_dist:.2f}m!')
            else:
                self.avoiding = False
    
    def _detection_cb(self, msg: String):
        """Process YOLO detections"""
        try:
            dets = json.loads(msg.data)
            self.current_detections = dets
            
            for det in dets:
                obj_class = det['class']
                conf = det['confidence']
                
                self.unique_objects_found.add(obj_class)
                self.all_detections.append(det)
                self.total_detections += 1
                
                # Check if target found
                if self.target_object and obj_class == self.target_object:
                    if conf > 0.50:  # Confidence threshold
                        self.target_confirmed = True
                        self.target_found_pub.publish(Bool(data=True))
                        self.get_logger().f'🎯 TARGET FOUND: {obj_class} ({conf:.0%})!')
                        self._publish_status()
                
        except Exception as e:
            pass
    
    def _control_loop(self):
        """Main control loop - runs at 20Hz"""
        twist = Twist()
        now = time.time()
        
        # Emergency obstacle avoidance override
        if self.avoiding:
            if now - self.avoid_start > 3.0:
                self.avoiding = False
            else:
                twist.angular.z = self.avoid_speed
                self.cmd_pub.publish(twist)
                return
        
        # State machine
        if self.state == "IDLE":
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            
        elif self.state == "EXPLORING":
            elapsed = now - self.drive_start
            
            if elapsed < self.drive_time:
                twist.linear.x = self.forward_speed
                self.distance_traveled += self.forward_speed * 0.05  # ~25ms steps
            else:
                self.state = "SCANNING"
                self.scan_start = now
                self.scans_completed += 1
                twist.linear.x = 0.0
                
        elif self.state == "SCANNING":
            twist.angular.z = self.turn_speed
            if now - self.scan_start > self.scan_time:
                self.state = "TURNING"
                self.turn_start = now
                twist.angular.z = self.turn_speed * 0.7  # Slower turn
            else:
                twist.angular.z = self.turn_speed
            
        elif self.state == "TURNING":
            if now - self.turn_start > self.turn_time:
                self.state = "DRIVING"
                self.drive_start = now
                twist.angular.z = 0.0
            else:
                twist.angular.z = self.turn_speed * 0.5
        
        self.cmd_pub.publish(twist)
    
    def _publish_status(self):
        """Publish current status"""
        status = {
            'state': self.state,
            'exploring': self.exploring,
            'target': self.target_object,
            'target_found': self.target_confirmed,
            'scans': self.scans_completed,
            'distance_m': round(self.distance_traveled, 2),
            'objects_found': list(self.unique_objects_found),
            'total_detections': self.total_detections,
            'uptime_seconds': round(time.time() - self.mission_start_time) if self.mission_start_time else 0
        }
        
        self.status_pub.publish(String(data=json.dumps(status)))
        self.findings_pub.publish(String(data=json.dumps({
            'objects': self.current_detections[-10:] if self.current_detections else [],
            'all_unique': list(self.found_objects),
            'count': len(self.all_detections)
        }))
