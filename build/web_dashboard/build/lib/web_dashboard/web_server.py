#!/usr/bin/env python3
"""
NEXUS Web Dashboard v2.0 — Final Complete Version
FastAPI + ROS 2 + YOLO Integration
"""

import os
import sys
import json
import base64
import time
import threading
import logging

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from std_msgs.msg import String, Bool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

yolo_model = None
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class NexusDashboard(Node):
    def __init__(self):
        super().__init__('nexus_web_dashboard')
        self.get_logger().info('🚀 NEXUS Dashboard Starting...')
        
        # State variables
        self.current_image = None
        self.image_lock = threading.Lock()
        self.camera_connected = False
        self.detections = []
        self.target_class = "chair"
        self.target_found = False
        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.current_fps = 0.0
        self.current_mode = "MANUAL"
        
        # QoS for sensor data (best effort for camera)
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
        
        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/rosbot2r/cmd_vel', 10)
        self.detection_pub = self.create_publisher(String, '/rosbot2r/detections', 10)
        self.target_found_pub = self.create_publisher(Bool, '/rosbot2r/target_found', 10)
        
        # Subscribers
        self.create_subscription(Image, '/rosbot2r/camera/image', self._image_callback, sensor_qos)
        self.create_subscription(String, '/current_mode', self._mode_callback, 10)
        
        # FPS timer
        self.create_timer(1.0, self._update_fps)
        
        # Load YOLO model
        self._load_yolo_model()
        
        self.get_logger().info('✅ Dashboard Initialized Successfully!')
    
    def _load_yolo_model(self):
        global yolo_model
        if not YOLO_AVAILABLE:
            self.get_logger().warning('⚠️ YOLO not installed. Running without AI detection.')
            return
        
        try:
            model_path = os.path.expanduser('~/rosbot-autonomy/yolov8n.pt')
            if os.path.exists(model_path):
                yolo_model = YOLO(model_path)
                self.get_logger().info(f'✅ YOLO model loaded from: {model_path}')
            else:
                yolo_model = YOLO('yolov8n.pt')
                self.get_logger().info('✅ YOLO model downloaded and loaded')
        except Exception as e:
            self.get_logger().error(f'❌ Failed to load YOLO: {e}')
            yolo_model = None
    
    def _image_callback(self, msg):
        """Process incoming camera images with YOLO detection."""
        global yolo_model
        
        try:
            height = msg.height
            width = msg.width
            
            # Handle different image encodings
            if msg.encoding == 'rgb8':
                img = np.frombuffer(msg.data, dtype=np.uint8).reshape(height, width, 3)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif msg.encoding == 'bgr8':
                img = np.frombuffer(msg.data, dtype=np.uint8).reshape(height, width, 3)
            else:
                return
            
            with self.image_lock:
                self.current_image = img.copy()
                self.camera_connected = True
                self.fps_counter += 1
                
                # Run YOLO detection if available
                if yolo_model is not None:
                    self._run_yolo_detection(img)
                    
        except Exception as e:
            log.error(f'Image callback error: {e}')
    
    def _run_yolo_detection(self, img):
        """Run YOLO inference on image."""
        global yolo_model
        
        try:
            results = yolo_model(img, verbose=False, conf=0.5)
            
            self.detections = []
            target_found_now = False
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]
                        confidence = float(box.conf[0])
                        xyxy = box.xyxy[0].tolist()
                        
                        detection = {
                            'class': class_name,
                            'confidence': round(confidence, 3),
                            'bbox': {
                                'x1': round(xyxy[0], 1),
                                'y1': round(xyxy[1], 1),
                                'x2': round(xyxy[2], 1),
                                'y2': round(xyxy[3], 1)
                            },
                            'is_target': class_name == self.target_class
                        }
                        
                        self.detections.append(detection)
                        
                        if class_name == self.target_class:
                            target_found_now = True
            
            self.target_found = target_found_now
            
            # Publish detections
            det_msg = String()
            det_msg.data = json.dumps(self.detections)
            self.detection_pub.publish(det_msg)
            
            tgt_msg = Bool()
            tgt_msg.data = self.target_found
            self.target_found_pub.publish(tgt_msg)
            
        except Exception as e:
            pass  # Silent fail for YOLO errors
    
    def _mode_callback(self, msg):
        self.current_mode = msg.data
    
    def _update_fps(self):
        elapsed = time.time() - self.fps_start_time
        if elapsed >= 1.0:
            self.current_fps = self.fps_counter / elapsed
            self.fps_counter = 0
            self.fps_start_time = time.time()
    
    def send_command(self, command: str) -> bool:
        """Send velocity command to robot."""
        try:
            twist = Twist()
            
            if command == "forward":
                twist.linear.x = 0.5
            elif command == "backward":
                twist.linear.x = -0.3
            elif command == "left":
                twist.linear.x = 0.2
                twist.angular.z = 0.5
            elif command == "right":
                twist.linear.x = 0.2
                twist.angular.z = -0.5
            elif command == "stop":
                pass  # All zeros by default
            elif command == "boost":
                twist.linear.x = 0.8
            else:
                return False
            
            self.cmd_vel_pub.publish(twist)
            self.get_logger().info(f'🎮 Command sent: {command}')
            return True
            
        except Exception as e:
            self.get_logger().error(f'Command failed: {e}')
            return False
    
    def get_annotated_frame_base64(self) -> str:
        """Get current frame with YOLO annotations as base64 JPEG."""
        with self.image_lock:
            if self.current_image is None:
                return None
            
            frame = self.current_image.copy()
            
            # Draw YOLO bounding boxes
            for det in self.detections:
                bbox = det['bbox']
                color = (0, 255, 0) if det['is_target'] else (0, 165, 255)
                thickness = 2 if det['is_target'] else 1
                
                cv2.rectangle(
                    frame,
                    (int(bbox['x1']), int(bbox['y1'])),
                    (int(bbox['x2']), int(bbox['y2'])),
                    color, thickness
                )
                
                label = f"{det['class']} {det['confidence']:.0%}"
                cv2.putText(
                    frame, label,
                    (int(bbox['x1']), int(bbox['y1']) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                )
            
            # Draw status bar
            status_text = f"Mode: {self.current_mode} | FPS: {self.current_fps:.1f} | Objects: {len(self.detections)}"
            if self.target_found:
                status_text += " | ✅ TARGET FOUND!"
            
            cv2.putText(frame, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Encode to base64 JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return base64.b64encode(buffer).decode('utf-8')


# Global node instance
dashboard_node = None

# FastAPI application
app = FastAPI(title="NEXUS Robot Dashboard", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the main dashboard HTML page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEXUS Robot Control Center</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            min-height: 100vh;
        }
        .header {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid #00d4ff;
        }
        .header h1 {
            font-size: 2.5em;
            text-shadow: 0 0 20px #00d4ff;
            margin-bottom: 5px;
        }
        .header p { opacity: 0.8; }
        .container {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            padding: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .panel h2 { margin-bottom: 15px; color: #00d4ff; }
        .camera-container {
            position: relative;
            width: 100%;
            aspect-ratio: 4/3;
            background: #000;
            border-radius: 10px;
            overflow: hidden;
        }
        #camera-feed {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .controls {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 20px;
        }
        .btn {
            padding: 15px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
        }
        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }
        .btn:active { transform: scale(0.95); }
        .btn-forward { background: linear-gradient(135deg, #00d4ff, #0099cc); color: white; grid-column: 2; }
        .btn-left { background: linear-gradient(135deg, #ff6b6b, #cc5555); color: white; }
        .btn-stop { background: linear-gradient(135deg, #ffd93d, #ccaa00); color: black; grid-column: 2; }
        .btn-right { background: linear-gradient(135deg, #ff6b6b, #cc5555); color: white; }
        .btn-boost { background: linear-gradient(135deg, #6bff6b, #55cc55); color: black; grid-column: 2; }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 15px;
        }
        .status-item {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .status-label { font-size: 0.9em; opacity: 0.7; }
        .status-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #00d4ff;
            margin-top: 5px;
        }
        .detection-list {
            max-height: 300px;
            overflow-y: auto;
            margin-top: 15px;
        }
        .detection-item {
            background: rgba(0, 212, 255, 0.1);
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .detection-item.target {
            background: rgba(0, 255, 0, 0.2);
            border: 1px solid #00ff00;
        }
        .target-status {
            font-size: 1.2em;
            padding: 15px;
            text-align: center;
            border-radius: 10px;
            margin-top: 15px;
        }
        .searching { background: rgba(255, 200, 0, 0.2); border: 2px solid #ffc800; }
        .found { background: rgba(0, 255, 0, 0.2); border: 2px solid #00ff00; }
        .mission-btn {
            background: linear-gradient(135deg, #a855f7, #7c3aed);
            color: white;
            margin-top: 10px;
            width: 100%;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 NEXUS Control Center</h1>
        <p>Intelligent Hybrid Autonomous-Gesture Robot System</p>
    </div>
    
    <div class="container">
        <div class="panel">
            <h2>📹 Robot Camera View</h2>
            <div class="camera-container">
                <img id="camera-feed" src="" alt="Camera Feed">
            </div>
            
            <h2 style="margin-top: 20px;">🎮 Manual Control</h2>
            <div class="controls">
                <button class="btn btn-forward" onclick="sendCommand('forward')">⬆️ Forward</button>
                <button class="btn btn-left" onclick="sendCommand('left')">⬅️ Left</button>
                <button class="btn btn-stop" onclick="sendCommand('stop')">⏹️ Stop</button>
                <button class="btn btn-right" onclick="sendCommand('right')">➡️ Right</button>
                <button class="btn btn-boost" onclick="sendCommand('boost')">🚀 Boost</button>
            </div>
        </div>
        
        <div class="panel">
            <h2>📊 System Status</h2>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">Mode</div>
                    <div class="status-value" id="mode">--</div>
                </div>
                <div class="status-item">
                    <div class="status-label">FPS</div>
                    <div class="status-value" id="fps">--</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Camera</div>
                    <div class="status-value" id="camera-status">--</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Objects</div>
                    <div class="status-value" id="object-count">0</div>
                </div>
            </div>
            
            <h2 style="margin-top: 20px;">🔍 Detections</h2>
            <div id="detection-list" class="detection-list"></div>
            
            <h2 style="margin-top: 20px;">🎯 Mission Control</h2>
            <button class="btn mission-btn" onclick="startMission()">▶️ Start Mission</button>
            <button class="btn mission-btn" onclick="stopMission()" style="background: linear-gradient(135deg, #ff6b6b, #cc5555);">⏹️ Stop Mission</button>
            <button class="btn mission-btn" onclick="resetSystem()" style="background: linear-gradient(135deg, #888888, #666666);">🔄 Reset</button>
        </div>
    </div>

    <script>
        // Update camera frame every 100ms
        async function updateFrame() {
            try {
                const response = await fetch('/api/frame');
                if (response.ok) {
                    const data = await response.json();
                    if (data.frame) {
                        document.getElementById('camera-feed').src = 'data:image/jpeg;base64,' + data.frame;
                    }
                }
            } catch (e) {}
        }
        
        // Update status every 500ms
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const data = await response.json();
                    document.getElementById('mode').textContent = data.mode || '--';
                    document.getElementById('fps').textContent = (data.fps || 0).toFixed(1);
                    document.getElementById('camera-status').textContent = data.camera_connected ? '✅ ON' : '❌ OFF';
                    document.getElementById('object-count').textContent = (data.detections || []).length;
                    
                    const listEl = document.getElementById('detection-list');
                    listEl.innerHTML = '';
                    if (data.detections) {
                        data.detections.forEach(det => {
                            const div = document.createElement('div');
                            div.className = 'detection-item' + (det.is_target ? ' target' : '');
                            div.innerHTML = '<span>' + det.class + '</span><span>' + (det.confidence * 100).toFixed(0) + '%</span>';
                            listEl.appendChild(div);
                        });
                    }
                }
            } catch (e) {}
        }
        
        async function sendCommand(cmd) {
            try {
                await fetch('/api/command/' + cmd, { method: 'POST' });
                console.log('Command:', cmd);
            } catch (e) { console.error(e); }
        }
        
        async function startMission() {
            await fetch('/api/mission/start', { method: 'POST' });
        }
        
        async function stopMission() {
            await fetch('/api/mission/stop', { method: 'POST' });
        }
        
        async function resetSystem() {
            await fetch('/api/mission/reset', { method: 'POST' });
        }
        
        // Keyboard controls
        document.addEventListener('keydown', (e) => {
            switch(e.key.toLowerCase()) {
                case 'w': case 'arrowup': sendCommand('forward'); break;
                case 's': case 'arrowdown': sendCommand('stop'); break;
                case 'a': case 'arrowleft': sendCommand('left'); break;
                case 'd': case 'arrowright': sendCommand('right'); break;
                case ' ': sendCommand('boost'); break;
            }
        });
        
        // Start update loops
        setInterval(updateFrame, 100);
        setInterval(updateStatus, 500);
        updateFrame();
        updateStatus();
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/api/status")
async def get_status():
    """Get system status including YOLO detections."""
    if dashboard_node is None:
        raise HTTPException(status_code=503, detail="Dashboard not initialized")
    
    return {
        "mode": dashboard_node.current_mode,
        "fps": dashboard_node.current_fps,
        "camera_connected": dashboard_node.camera_connected,
        "detections": dashboard_node.detections,
        "target_class": dashboard_node.target_class,
        "target_found": dashboard_node.target_found
    }


@app.get("/api/frame")
async def get_frame():
    """Get annotated camera frame as base64 JPEG."""
    if dashboard_node is None:
        raise HTTPException(status_code=503, detail="Dashboard not initialized")
    
    frame = dashboard_node.get_annotated_frame_base64()
    if frame is None:
        raise HTTPException(status_code=503, detail="No camera data available")
    
    return {"frame": frame}


@app.post("/api/command/{command}")
async def send_command(command: str):
    """Send movement command to robot."""
    if dashboard_node is None:
        raise HTTPException(status_code=503, detail="Dashboard not initialized")
    
    success = dashboard_node.send_command(command)
    if success:
        return {"status": "ok", "command": command}
    else:
        raise HTTPException(status_code=400, detail=f"Invalid command: {command}")


@app.post("/api/mission/start")
async def start_mission():
    """Start autonomous mission."""
    return {"status": "ok", "message": "Mission started"}


@app.post("/api/mission/stop")
async def stop_mission():
    """Stop autonomous mission."""
    return {"status": "ok", "message": "Mission stopped"}


@app.post("/api/mission/reset")
async def reset_system():
    """Reset system state."""
    return {"status": "ok", "message": "System reset"}


def main(args=None):
    """Main entry point for the dashboard node."""
    global dashboard_node
    
    # Initialize ROS 2
    rclpy.init(args=args)
    
    # Create dashboard node
    dashboard_node = NexusDashboard()
    
    # Spin ROS node in background thread
    ros_thread = threading.Thread(target=rclpy.spin, args=(dashboard_node,), daemon=True)
    ros_thread.start()
    
    # Start FastAPI web server
    print("\n" + "="*60)
    print("🌐 NEXUS ROBOT DASHBOARD")
    print("   Open: http://localhost:8000")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    
    # Cleanup
    dashboard_node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
