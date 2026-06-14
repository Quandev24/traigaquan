"""
Stream Manager - Manages all camera stream workers for Camera 2 devices
"""

import threading
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from services.camera_stream_worker import CameraStreamWorker, MockCameraWorker
from services.detection_pipeline import detection_pipeline

logger = logging.getLogger(__name__)

# Project root directory for video_path.txt
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VIDEO_PATH_FILE = os.path.join(PROJECT_DIR, 'video_path.txt')


class StreamManager:
    """Manages all camera stream workers"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.workers: Dict[int, CameraStreamWorker] = {}
        self.lock = threading.RLock()
        
        # Global callbacks
        self.on_detection = None
        self.on_frame = None
        self.on_status_change = None
        
        # Auto-start config
        self.auto_start_enabled = True
        self.use_mock_workers = False  # Use real workers by default
        
        logger.info("StreamManager initialized")
        self._db_initialized = False
    
    def _read_video_paths(self):
        """Read video paths from video_path.txt file"""
        paths = []
        if os.path.exists(VIDEO_PATH_FILE):
            with open(VIDEO_PATH_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                paths = [line.strip() for line in lines if line.strip() and os.path.exists(line.strip())]
        return paths

    def init_from_database(self):
        """Initialize workers from database (Camera 2 devices)"""
        if self._db_initialized:
            return
        try:
            from models import Device, CoopDevice, db
            from app import create_app
            from services.detection_pipeline import detection_pipeline
            
            app = create_app()
            detection_pipeline.init_app(app)
            
            with app.app_context():
                # Get all Camera 2 devices
                cameras = Device.query.filter(
                    Device.type == 'camera',
                    Device.deleted == False,
                    Device.name.like('%Camera 2%')
                ).order_by(Device.id.asc()).all()
                
                # Read video paths from file
                video_paths = self._read_video_paths()
                logger.info(f"Found {len(video_paths)} video/image files from video_path.txt")
                
                for i, cam in enumerate(cameras):
                    coop_device = CoopDevice.query.filter_by(
                        device_id=cam.id, deleted=False
                    ).first()
                    
                    coop_id = coop_device.coop_id if coop_device else None
                    
                    if coop_id:
                        # Assign video file (cycle through available paths)
                        if video_paths:
                            stream_url = video_paths[i % len(video_paths)]
                            logger.info(f"Assigned video file to {cam.name}: {stream_url}")
                        else:
                            # Fallback to device stream_url or mock RTSP
                            stream_url = cam.stream_url or f'rtsp://camera-{cam.id}.local:8554/stream'
                            logger.warning(f"No video files found, using stream_url for {cam.name}: {stream_url}")
                        
                        frame_skip = cam.frame_skip or 5
                        analysis_interval = 10  # 10 seconds default
                        
                        self.register_camera(cam.id, stream_url, coop_id, frame_skip, analysis_interval)
                        logger.info(f"Registered Camera 2: {cam.name} (ID: {cam.id}) -> Coop {coop_id} (interval: {analysis_interval}s, source: {stream_url})")
                
                logger.info(f"StreamManager: Initialized {len(self.workers)} Camera 2 workers")
                self._db_initialized = True
                
        except Exception as e:
            logger.error(f"StreamManager init error: {e}")
    
    def register_camera(self, device_id: int, stream_url: str, coop_id: int, frame_skip: int = 5, analysis_interval_seconds: int = 10):
        """Register a camera for management"""
        with self.lock:
            if device_id in self.workers:
                logger.warning(f"Camera {device_id} already registered, updating...")
                self.workers[device_id].stop()
            
            # Create worker - use real worker for local files, respect mock setting for streams
            is_local_file = not stream_url.isdigit() and not stream_url.startswith(('rtsp://', 'http://', 'https://')) and os.path.exists(stream_url)
            
            if is_local_file:
                # Always use real worker for local files
                worker = CameraStreamWorker(device_id, stream_url, coop_id, frame_skip, analysis_interval_seconds)
                logger.info(f"Using CameraStreamWorker for local file: {stream_url}")
            elif self.use_mock_workers:
                worker = MockCameraWorker(device_id, stream_url, coop_id, frame_skip, analysis_interval_seconds)
            else:
                worker = CameraStreamWorker(device_id, stream_url, coop_id, frame_skip, analysis_interval_seconds)
            
            # Set callbacks
            worker.on_detection = self._on_detection
            worker.on_frame = self._on_frame
            worker.on_status_change = self._on_status_change
            
            self.workers[device_id] = worker
            logger.info(f"Registered camera {device_id} (coop: {coop_id})")
    
    def start_camera(self, device_id: int) -> bool:
        """Start a specific camera worker"""
        with self.lock:
            worker = self.workers.get(device_id)
            if not worker:
                logger.error(f"Camera {device_id} not registered")
                return False
            
            if worker.running:
                logger.warning(f"Camera {device_id} already running")
                return True
            
            worker.start()
            return True
    
    def stop_camera(self, device_id: int) -> bool:
        """Stop a specific camera worker"""
        with self.lock:
            worker = self.workers.get(device_id)
            if not worker:
                logger.error(f"Camera {device_id} not registered")
                return False
            
            worker.stop()
            return True
    
    def start_all(self) -> int:
        """Start all registered cameras"""
        started = 0
        with self.lock:
            for device_id, worker in self.workers.items():
                if not worker.running:
                    worker.start()
                    started += 1
        logger.info(f"Started {started} cameras")
        return started
    
    def stop_all(self) -> int:
        """Stop all cameras"""
        stopped = 0
        with self.lock:
            for device_id, worker in self.workers.items():
                if worker.running:
                    worker.stop()
                    stopped += 1
        logger.info(f"Stopped {stopped} cameras")
        return stopped
    
    def get_camera_status(self, device_id: int) -> Optional[dict]:
        """Get status of a specific camera"""
        with self.lock:
            worker = self.workers.get(device_id)
            if not worker:
                return None
            return worker.get_stats()
    
    def get_all_status(self) -> List[dict]:
        """Get status of all cameras"""
        with self.lock:
            return [worker.get_stats() for worker in self.workers.values()]
    
    def get_running_cameras(self) -> List[int]:
        """Get list of running camera IDs"""
        with self.lock:
            return [device_id for device_id, worker in self.workers.items() if worker.running]
    
    def update_camera_config(self, device_id: int, stream_url: str = None, frame_skip: int = None, analysis_interval_seconds: int = None) -> bool:
        """Update camera configuration"""
        with self.lock:
            worker = self.workers.get(device_id)
            if not worker:
                return False
            
            was_running = worker.running
            if was_running:
                worker.stop()
            
            if stream_url:
                worker.stream_url = stream_url
            if frame_skip:
                worker.set_frame_skip(frame_skip)
            if analysis_interval_seconds is not None:
                worker.analysis_interval_seconds = max(1, int(analysis_interval_seconds))
            
            if was_running:
                worker.start()
            
            logger.info(f"Updated camera {device_id} config")
            return True
    
    def set_callbacks(self, on_detection=None, on_frame=None, on_status_change=None):
        """Set global callbacks"""
        self.on_detection = on_detection
        self.on_frame = on_frame
        self.on_status_change = on_status_change
        
        # Update existing workers
        with self.lock:
            for worker in self.workers.values():
                if on_detection:
                    worker.on_detection = on_detection
                if on_frame:
                    worker.on_frame = on_frame
                if on_status_change:
                    worker.on_status_change = on_status_change
    
    def _on_detection(self, device_id: int, detections: list, annotated_frame):
        """Internal detection callback"""
        if self.on_detection:
            try:
                self.on_detection(device_id, detections, annotated_frame)
            except Exception as e:
                logger.error(f"Detection callback error: {e}")
    
    def _on_frame(self, device_id: int, frame):
        """Internal frame callback"""
        if self.on_frame:
            try:
                self.on_frame(device_id, frame)
            except Exception as e:
                logger.error(f"Frame callback error: {e}")
    
    def _on_status_change(self, device_id: int, status: str):
        """Internal status change callback"""
        if self.on_status_change:
            try:
                self.on_status_change(device_id, status)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")
    
    def health_check(self) -> Dict:
        """Check health of all workers"""
        with self.lock:
            healthy = 0
            unhealthy = 0
            for worker in self.workers.values():
                if worker.is_healthy():
                    healthy += 1
                else:
                    unhealthy += 1
            return {
                'total': len(self.workers),
                'healthy': healthy,
                'unhealthy': unhealthy,
                'running': sum(1 for w in self.workers.values() if w.running)
            }
    
    def cleanup(self):
        """Cleanup all workers"""
        self.stop_all()
        with self.lock:
            self.workers.clear()
        logger.info("StreamManager cleaned up")


# Global instance
stream_manager = StreamManager()