#!/usr/bin/env python3
"""NEXUS Mission Controller v3.0 — Smart Explorer with Object Detection"""

import time
import math
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


class SmartExplorer(Node):
    def __init__(self):
        super().__init__('nexus_smart_explorer')
        
        self.get_logger().info('🤖 NEXUS Smart Explorer v3.0 Starting...')
        
        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/rosbot2r/cmd_vel', 10)
        self.findings_pub = self.create_publisher(String, '/rosbot2r/findings', 10)
        
        # Subscribers
        sensor_qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=5)
        self.create_subscription(LaserScan, '/rosbot2r/scan', self._laser_cb, sensor_qos)
        self.create_subscription(String, '/rosbot2r/detections', self._detection_cb, 10)
        
        # State machine states
        self.state = "STARTING"  # STARTING -> DRIVING -> SCANNING -> TURNING -> REPORTING
        self.state_start_time = time.time()
        
        # Exploration parameters
        self.drive_duration = 3.0      # Drive forward for 3 seconds
        self.scan_duration = 4.0       # Rotate and scan for 4 seconds
        self.turn_duration = 2.0       # Turn for 2 seconds
        
        # Obstacle avoidance
        self.obstacle_detected = False
        self.min_front_distance = 999.0
        
        # Detection tracking
        self.all_detections = []        # All objects seen this session
        self.current_detections = []     # Current frame detections
        self.unique_objects = set()      # Unique object types found
        self.total_objects_found = 0
        
        # Statistics
        self.distance_traveled = 0.0
        self.exploration_time = 0.0
        self.scan_count = 0
        
        # Control loop (10 Hz)
        self.create_timer(0.1, self._control_loop)
        
        # Status reporter (every 5 seconds)
        self.create_timer(5.0, self._report_status)
        
        self.get_logger().info('✅ Smart Explorer Ready!')
        self.get_logger().info('   States: DRIVE → SCAN → TURN → REPEAT')
    
    def _laser_cb(self, msg: LaserScan):
        """Process LiDAR data for obstacle detection."""
        if len(msg.ranges) == 0:
            return
        
        # Get front distance (center of scan)
        mid = len(msg.ranges) // 2
        front_ranges = [r for r in msg.ranges[mid-30:mid+30] if 0.1 < r < 5.0]
        
        if len(front_ranges) > 0:
            self.min_front_distance = min(front_ranges)
            
            if self.min_front_distance < 0.5:
                if not self.obstacle_detected:
                    self.obstacle_detected = True
                    self.get_logger().warn(f'⚠️ OBSTACLE at {self.min_front_distance:.2f}m!')
            else:
                self.obstacle_detected = False
    
    def _detection_cb(self, msg: String):
        """Process YOLO detections from dashboard."""
        try:
            dets = json.loads(msg.data)
            self.current_detections = dets
            
            for det in dets:
                obj_class = det['class']
                confidence = det['confidence']
                
                # Track unique objects
                self.unique_objects.add(obj_class)
                self.total_objects_found += 1
                
                # Store finding
                finding = {
                    'object': obj_class,
                    'confidence': confidence,
                    'time': time.strftime('%H:%M:%S'),
                    'position': 'detected'
                }
                self.all_detections.append(finding)
                
                self.get_logger().info(f'🎯 FOUND: {obj_class} ({confidence:.0%})')
                
        except Exception as e:
            pass
    
    def _control_loop(self):
        """Main state machine control loop."""
        twist = Twist()
        now = time.time()
        elapsed = now - self.state_start_time
        
        # Emergency obstacle avoidance (overrides everything)
        if self.obstacle_detected:
            self.state = "AVOIDING"
            twist.angular.z = 0.6  # Turn faster to avoid
            self.cmd_pub.publish(twist)
            return
        
        # State machine
        if self.state == "STARTING":
            self.state = "DRIVING"
            self.state_start_time = now
            self.get_logger().info('🚗 State: DRIVING')
        
        elif self.state == "DRIVING":
            twist.linear.x = 0.25  # Drive forward slowly
            self.distance_traveled += 0.025  # Approximate
            
            if elapsed >= self.drive_duration:
                self.state = "SCANNING"
                self.state_start_time = now
                self.scan_count += 1
                self.get_logger().info(f'👁️ State: SCANNING (#{self.scan_count})')
        
        elif self.state == "SCANNING":
            # Rotate in place to scan surroundings
            twist.angular.z = 0.4
            
            if elapsed >= self.scan_duration:
                self.state = "TURNING"
                self.state_start_time = now
                self.get_logger().info('↩️ State: TURNING')
        
        elif self.state == "TURNING":
            # Continue turning briefly
            twist.angular.z = 0.3
            
            if elapsed >= self.turn_duration:
                self.state = "DRIVING"
                self.state_start_time = now
                self.get_logger().info('🚗 State: DRIVING')
        
        self.exploration_time = elapsed
        self.cmd_pub.publish(twist)
    
    def _report_status(self):
        """Periodic status report."""
        status = {
            'state': self.state,
            'unique_objects': list(self.unique_objects),
            'total_detections': self.total_objects_found,
            'scans_completed': self.scan_count,
            'distance_m': round(self.distance_traveled, 2),
            'front_clearance_m': round(self.min_front_distance, 2)
        }
        
        self.findings_pub.publish(String(data=json.dumps(status)))
        
        self.get_logger().info(
            f'📊 Status: {self.state} | '
            f'Objects: {list(self.unique_objects)} | '
            f'Scans: {self.scan_count} | '
            f'Distance: {self.distance_traveled:.1f}m'
        )


def main(args=None):
    rclpy.init(args=args)
    
    node = SmartExplorer()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('\n\n🛑 Exploration stopped by user')
        node.get_logger().info(f'📊 FINAL REPORT:')
        node.get_logger().info(f'   Total scans: {node.scan_count}')
        node.get_logger().info(f'   Unique objects found: {list(node.unique_objects)}')
        node.get_logger_.info(f'   Total detections: {node.total_objects_found}')
        node.get_logger().info(f'   Distance traveled: {node.distance_traveled:.1f}m')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
