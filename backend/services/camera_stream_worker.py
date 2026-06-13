"""
Camera Stream Worker - Background worker for processing a single camera stream
"""

import cv2
import time
import threading
import logging
import os
from datetime import datetime
from services.detection_pipeline import detection_pipeline

logger = logging.getLogger(__name__)


class CameraStreamWorker:
    """Background worker for processing a single camera stream"""
    
    def __init__(self, device_id: int, stream_url: str, coop_id: int, frame_skip: int = 5, analysis_interval_seconds: int = 10):
        self.device_id = device_id
        self.stream_url = stream_url
        self.coop_id = coop_id
        self.frame_skip = frame_skip
        self.analysis_interval_seconds = analysis_interval_seconds
        self.frame_count = 0
        self.processed_count = 0
        
        self.running = False
        self.thread = None
        self.cap = None
        
        # File handling
        self.is_local_file = False
        self.is_image = False
        self.static_frame = None  # For static images
        
        # Stats
        self.start_time = None
        self.last_frame_time = None
        self.last_detection_time = None
        self.last_analysis_time = None
        self.error_count = 0
        self.last_error = None
        
        # Callbacks
        self.on_detection = None  # Callback for detection results
        self.on_frame = None      # Callback for raw/annotated frames
        self.on_status_change = None  # Callback for status changes
    
    def start(self):
        """Start the stream worker"""
        if self.running:
            logger.warning(f"Worker {self.device_id} already running")
            return
        
        self.running = True
        self.start_time = datetime.now()
        self.last_analysis_time = datetime.now()
        self.error_count = 0
        self.last_error = None
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name=f"CameraWorker-{self.device_id}")
        self.thread.start()
        
        self._notify_status('starting')
        logger.info(f"Started camera worker {self.device_id} for {self.stream_url} (analysis interval: {self.analysis_interval_seconds}s)")
    
    def stop(self):
        """Stop the stream worker"""
        if not self.running:
            return
        
        self.running = False
        self._notify_status('stopping')
        
        if self.thread:
            self.thread.join(timeout=10)
            self.thread = None
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self._notify_status('stopped')
        logger.info(f"Stopped camera worker {self.device_id}")
    
    def _run_loop(self):
        """Main processing loop - processes frame every analysis_interval_seconds"""
        while self.running:
            try:
                # Initialize or reconnect capture
                if not self.is_image and (self.cap is None or not self.cap.isOpened()):
                    self._connect_stream()
                    if self.cap is None and not self.is_image:
                        time.sleep(5)
                        continue
                
                # Read frame based on source type
                frame = None
                ret = True
                
                if self.is_image:
                    # Static image - use the pre-loaded frame
                    if self.static_frame is not None:
                        frame = self.static_frame.copy()
                        ret = True
                    else:
                        ret = False
                else:
                    # Video stream or video file
                    ret, frame = self.cap.read()
                    
                    if not ret or frame is None or frame.size == 0:
                        if self.is_local_file and self.cap:
                            # Video file ended - loop back to start
                            logger.info(f"Worker {self.device_id}: Video ended, looping...")
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, frame = self.cap.read()
                            if not ret or frame is None:
                                logger.warning(f"Worker {self.device_id}: Failed to loop video, reconnecting...")
                                self._reconnect()
                                continue
                        else:
                            # Stream ended or error
                            logger.warning(f"Worker {self.device_id}: Failed to read frame, reconnecting...")
                            self._reconnect()
                            continue
                
                if not ret or frame is None or frame.size == 0:
                    time.sleep(1)
                    continue
                
                self.frame_count += 1
                self.last_frame_time = datetime.now()
                
                # Time-based processing: run analysis every analysis_interval_seconds
                now = datetime.now()
                if self.last_analysis_time is None:
                    self.last_analysis_time = now
                
                elapsed = (now - self.last_analysis_time).total_seconds()
                if elapsed >= self.analysis_interval_seconds:
                    self._process_frame(frame)
                    self.last_analysis_time = now
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Worker {self.device_id} error: {e}")
                self.error_count += 1
                self.last_error = str(e)
                if not self.is_image:
                    self._reconnect()
                time.sleep(2)
    
    def _connect_stream(self):
        """Connect to the stream URL or local file"""
        try:
            logger.info(f"Worker {self.device_id}: Connecting to {self.stream_url}")
            
            # Detect stream type
            self.is_local_file = False
            self.is_image = False
            self.static_frame = None
            
            if self.stream_url.isdigit():
                # Webcam index
                self.cap = cv2.VideoCapture(int(self.stream_url), cv2.CAP_DSHOW)
            else:
                # Check if it's a local file path
                is_http = self.stream_url.startswith(('http://', 'https://'))
                is_rtsp = self.stream_url.startswith('rtsp://')
                
                if not is_http and not is_rtsp and os.path.exists(self.stream_url):
                    # Local file path
                    self.is_local_file = True
                    ext = os.path.splitext(self.stream_url)[1].lower()
                    image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
                    if ext in image_exts:
                        self.is_image = True
                        # Load static image once
                        self.static_frame = cv2.imread(self.stream_url)
                        if self.static_frame is None:
                            logger.error(f"Worker {self.device_id}: Failed to load image {self.stream_url}")
                            return False
                        logger.info(f"Worker {self.device_id}: Loaded static image ({self.static_frame.shape[1]}x{self.static_frame.shape[0]})")
                        self._notify_status('connected')
                        return True
                    else:
                        # Video file
                        self.cap = cv2.VideoCapture(self.stream_url)
                elif is_rtsp or is_http:
                    # RTSP/HTTP URL
                    self.cap = cv2.VideoCapture(self.stream_url)
                else:
                    # Fallback: try as video capture
                    self.cap = cv2.VideoCapture(self.stream_url)
            
            if self.is_image:
                return True
            
            # Set buffer size to reduce latency
            if self.cap:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                if not self.cap.isOpened():
                    logger.error(f"Worker {self.device_id}: Failed to open stream/file")
                    self.cap = None
                    return False
                
                # Test read
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    logger.error(f"Worker {self.device_id}: Stream/file opened but cannot read frames")
                    self.cap.release()
                    self.cap = None
                    return False
                
                logger.info(f"Worker {self.device_id}: Connected successfully ({frame.shape[1]}x{frame.shape[0]})")
                self._notify_status('connected')
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Worker {self.device_id}: Connection error: {e}")
            self.cap = None
            return False
    
    def _reconnect(self):
        """Reconnect to stream"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self._notify_status('reconnecting')
        time.sleep(3)
    
    def _process_frame(self, frame):
        """Process frame through detection pipeline"""
        try:
            # Run detection
            annotated_frame, detections = detection_pipeline.process_frame(
                frame, self.device_id, self.coop_id
            )
            
            self.processed_count += 1
            self.last_detection_time = datetime.now()
            
            # Always save annotated frame to folder (time-based filename)
            image_path = detection_pipeline.save_annotated_frame(
                annotated_frame, self.device_id
            )
            
            # Save to database if diseases detected
            has_disease = any(d['has_disease'] for d in detections)
            detection_id = None
            if has_disease:
                detection_id = detection_pipeline.save_detection_to_db(
                    self.device_id, self.coop_id, detections,
                    source_file=f'stream_{self.device_id}',
                    annotated_frame=annotated_frame
                )
            
            # Callbacks - include image_path
            if self.on_detection:
                self.on_detection(self.device_id, detections, annotated_frame, image_path)
            
            if self.on_frame:
                self.on_frame(self.device_id, annotated_frame)
                
        except Exception as e:
            logger.error(f"Worker {self.device_id}: Processing error: {e}")
            self.error_count += 1
            self.last_error = str(e)
    
    def _notify_status(self, status):
        """Notify status change"""
        if self.on_status_change:
            self.on_status_change(self.device_id, status)
    
    def get_stats(self):
        """Get worker statistics"""
        uptime = None
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        fps = 0
        if uptime and uptime > 0:
            fps = self.processed_count / uptime
        
        return {
            'device_id': self.device_id,
            'running': self.running,
            'stream_url': self.stream_url,
            'coop_id': self.coop_id,
            'frame_skip': self.frame_skip,
            'analysis_interval_seconds': self.analysis_interval_seconds,
            'frame_count': self.frame_count,
            'processed_count': self.processed_count,
            'uptime_seconds': uptime,
            'fps': round(fps, 2),
            'last_frame_time': self.last_frame_time.isoformat() if self.last_frame_time else None,
            'last_detection_time': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'last_analysis_time': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            'error_count': self.error_count,
            'last_error': self.last_error,
        }
    
    def set_frame_skip(self, frame_skip: int):
        """Update frame skip value"""
        self.frame_skip = max(1, frame_skip)
        logger.info(f"Worker {self.device_id}: Frame skip set to {self.frame_skip}")
    
    def is_healthy(self):
        """Check if worker is healthy"""
        if not self.running:
            return False
        if self.cap is None or not self.cap.isOpened():
            return False
        if self.last_frame_time:
            elapsed = (datetime.now() - self.last_frame_time).total_seconds()
            if elapsed > 30:  # No frames for 30 seconds
                return False
        return True


class MockCameraWorker(CameraStreamWorker):
    """Mock worker for testing without actual cameras"""
    
    def __init__(self, device_id: int, stream_url: str, coop_id: int, frame_skip: int = 5, analysis_interval_seconds: int = 10):
        super().__init__(device_id, stream_url, coop_id, frame_skip, analysis_interval_seconds)
        self.mock_frame = None
        self._create_mock_frame()
    
    def _create_mock_frame(self):
        """Create a mock frame for testing"""
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Add some test pattern
        cv2.putText(frame, f'Camera {self.device_id} - Mock Stream', (50, 360),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        cv2.putText(frame, f'Coop ID: {self.coop_id}', (50, 450),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
        cv2.putText(frame, time.strftime('%H:%M:%S'), (50, 520),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 255, 100), 2)
        self.mock_frame = frame
    
    def _connect_stream(self):
        """Mock connection always succeeds"""
        logger.info(f"Mock worker {self.device_id}: Connected (mock)")
        self._notify_status('connected')
        return True
    
    def _run_loop(self):
        """Mock processing loop - time-based like real worker"""
        while self.running:
            try:
                self._create_mock_frame()  # Update timestamp
                frame = self.mock_frame.copy()
                
                self.frame_count += 1
                self.last_frame_time = datetime.now()
                
                # Time-based processing
                now = datetime.now()
                if self.last_analysis_time is None:
                    self.last_analysis_time = now
                
                elapsed = (now - self.last_analysis_time).total_seconds()
                if elapsed >= self.analysis_interval_seconds:
                    self._process_frame(frame)
                    self.last_analysis_time = now
                
                time.sleep(0.1)  # ~10 FPS mock
                
            except Exception as e:
                logger.error(f"Mock worker {self.device_id} error: {e}")
                time.sleep(1)


# Import numpy for mock worker
import numpy as np