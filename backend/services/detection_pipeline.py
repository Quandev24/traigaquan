"""
Detection Pipeline Service - Single Model (model_detect_disease)

Pipeline:
  1. Single model -> Detect chickens and diseases on full frame
  2. Return annotated frame + detection data
"""

import os
import cv2
import numpy as np
from datetime import datetime
from ultralytics import YOLO
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL_PATH = os.path.join(BASE_DIR, 'runs', 'detect', 'runs', 'my_project', 'model_detect_disease', 'weights', 'best.pt')

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Real-time detection pipeline for chicken and disease detection (Single Model)"""
    
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
        
        self.model = YOLO(MODEL_PATH)
        self._app = None
        
        # Confidence threshold
        self.conf_threshold = 0.2
        
        logger.info("DetectionPipeline initialized with single model:")
        logger.info("  Model: %s", MODEL_PATH)
    
    def init_app(self, app):
        """Initialize with Flask app for database operations in background threads"""
        self._app = app
    
    def process_frame(self, frame, device_id, coop_id):
        """
        Process a single frame through the detection pipeline (Single Model)
        
        Args:
            frame: OpenCV frame (numpy array)
            device_id: Camera device ID
            coop_id: Coop ID
            
        Returns:
            tuple: (annotated_frame, detection_list)
        """
        if frame is None or frame.size == 0:
            return frame, []
        
        # Single model detection on full frame
        results = self.model.predict(frame, conf=self.conf_threshold, verbose=False)
        
        detections = []
        annotated_frame = frame.copy()
        
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            class_name = results[0].names[cls_id]
            
            is_disease = class_name.lower() not in ['healthy', 'healthys', '']
            disease_entry = {
                'disease': class_name,
                'confidence': round(conf, 3),
                'bbox': [x1, y1, x2, y2],
            }
            
            detection = {
                'bbox': [x1, y1, x2, y2],
                'confidence': round(conf, 3),
                'diseases': [disease_entry],
                'has_disease': is_disease
            }
            detections.append(detection)
            
            # Annotate frame
            self._annotate_chicken(annotated_frame, detection, x1, y1, x2, y2)
        
        return annotated_frame, detections
    
    def _annotate_chicken(self, frame, detection, x1, y1, x2, y2):
        """Draw detection results on frame"""
        has_disease = detection['has_disease']
        
        # Chicken box color: red if disease, green if healthy
        color = (0, 0, 255) if has_disease else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Disease/Health label
        disease_label = ""
        for d in detection.get('diseases', []):
            dname = d.get('disease', '').lower()
            if dname not in ['healthy', 'healthys', '']:
                disease_label = f"{d['disease']} {d['confidence']:.2f}"
                break
        
        label = disease_label if has_disease else f"Healthy {detection['confidence']:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    
    def save_detection_to_db(self, device_id, coop_id, detections, source_file=None, annotated_frame=None):
        """Save detection results to database"""
        try:
            from models import db, AIDetection, Alert, Coop

            if self._app is None:
                logger.error("No Flask app initialized for database operations")
                return None
                
            with self._app.app_context():
                chicken_count = len(detections)
                has_disease = any(d['has_disease'] for d in detections)
                diseases = []

                for d in detections:
                    for dis in d['diseases']:
                        if dis['disease'].lower() not in ['healthy', 'healthys', '']:
                            diseases.append({
                                'disease': dis['disease'],
                                'confidence': dis['confidence'],
                                'bbox': dis['bbox'],
                                'chicken_bbox': d['bbox']
                            })

                detection_record = AIDetection(
                    device_id=device_id,
                    coop_id=coop_id,
                    source_file=source_file or f'stream_{device_id}',
                    chicken_count=chicken_count,
                    has_disease=has_disease,
                    diseases=diseases,
                    details=detections,
                    detected_at=datetime.now(),
                )
                db.session.add(detection_record)
                db.session.commit()

                # Create alert if disease detected
                if has_disease and coop_id:
                    coop = db.session.get(Coop, coop_id)
                    coop_name = coop.name if coop else 'Unknown'
                    disease_names = ', '.join(d['disease'] for d in diseases)
                    alert = Alert(
                        coop_id=coop_id,
                        device_id=device_id,
                        type='disease',
                        level='warning',
                        message=f'{coop_name}: Phát hiện gà bệnh - {disease_names}',
                    )
                    db.session.add(alert)
                    db.session.commit()

                # Save annotated frame as image file
                if annotated_frame is not None:
                    try:
                        save_dir = os.path.join(BASE_DIR, 'static', 'ai_detections')
                        os.makedirs(save_dir, exist_ok=True)
                        save_path = os.path.join(save_dir, f'detection_{detection_record.id}.jpg')
                        success = cv2.imwrite(save_path, annotated_frame)
                        if not success:
                            logger.error("cv2.imwrite failed for detection_id=%s", detection_record.id)
                        else:
                            logger.info("Saved annotated image for detection_id=%s to %s", detection_record.id, save_path)
                    except Exception as e:
                        logger.exception("Error saving annotated image for detection_id=%s: %s", detection_record.id, e)

                return detection_record.id
        except Exception as e:
            logger.exception("Error saving detection to DB: %s", e)
            return None
    
    def frame_to_base64(self, frame):
        """Convert frame to base64 string for WebSocket transmission"""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        import base64
        return base64.b64encode(buffer).decode('utf-8')

    def save_annotated_frame(self, annotated_frame, device_id, detection_id=None):
        """
        Save annotated frame to static/ai_detections folder with time-based filename.
        
        Args:
            annotated_frame: OpenCV frame with annotations
            device_id: Camera device ID
            detection_id: Optional DB detection record ID
            
        Returns:
            str: Relative path to saved image (e.g., '/ai_detections/detection_1_20260612_143022.jpg')
        """
        if annotated_frame is None or annotated_frame.size == 0:
            return None
            
        try:
            save_dir = os.path.join(BASE_DIR, 'static', 'ai_detections')
            os.makedirs(save_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if detection_id:
                filename = f'detection_{device_id}_{detection_id}_{timestamp}.jpg'
            else:
                filename = f'detection_{device_id}_{timestamp}.jpg'
            
            save_path = os.path.join(save_dir, filename)
            success = cv2.imwrite(save_path, annotated_frame)
            
            if not success:
                logger.error("cv2.imwrite failed for device_id=%s", device_id)
                return None
                
            logger.info("Saved annotated image for device_id=%s to %s", device_id, save_path)
            return f'/ai_detections/{filename}'
            
        except Exception as e:
            logger.exception("Error saving annotated image for device_id=%s: %s", device_id, e)
            return None


# Global instance
detection_pipeline = DetectionPipeline()