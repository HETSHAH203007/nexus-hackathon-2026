#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class RobotController(Node):

    def __init__(self):
        super().__init__("robot_controller")

        self.publisher = self.create_publisher(
            Twist,
            "/rosbot2r/cmd_vel",
            10
        )

        self.subscription = self.create_subscription(
            LaserScan,
            "/rosbot2r/scan",
            self.scan_callback,
            qos_profile_sensor_data
        )

        self.get_logger().info("Robot Controller Started")

    def scan_callback(self, msg):

        front = msg.ranges[750:850]

        valid = [
            r
            for r in front
            if msg.range_min < r < msg.range_max
        ]

        cmd = Twist()

        if len(valid) == 0:
            self.get_logger().info("No Valid Scan")
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

        elif min(valid) < 0.6:
            self.get_logger().info("Obstacle Detected")
            cmd.linear.x = 0.0
            cmd.angular.z = 0.6

        else:
            self.get_logger().info("Moving Forward")
            cmd.linear.x = 0.3
            cmd.angular.z = 0.0

        self.publisher.publish(cmd)


def main(args=None):
    rclpy.init(args=args)

    node = RobotController()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
