"""
AI Detection Pipeline - Phát hiện gà bệnh qua camera (Single Model)

Pipeline:
  1. Single model (model_detect_disease) → Detect both chickens and diseases on full image
  2. Return results with annotations
"""

import os
import cv2
import numpy as np
from datetime import datetime
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

MODEL_PATH = r'D:\Share_Projects\AutomatedChickenFarmManagement\runs\detect\runs\my_project\model_detect_disease\weights\best.pt'


class AIDetector:
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

    def load_image(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}

        if ext in video_exts:
            cap = cv2.VideoCapture(file_path)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            return frame
        else:
            img = cv2.imread(file_path)
            return img

    def detect(self, file_path, coop_id=None, device_id=None):
        if not os.path.exists(file_path):
            return {'error': f'File not found: {file_path}'}

        img = self.load_image(file_path)
        if img is None:
            return {'error': 'Cannot read file'}

        results = self.model.predict(img, conf=0.2, verbose=False)

        chickens = []
        diseases = []
        has_disease = False

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

            chicken = {
                'bbox': [x1, y1, x2, y2],
                'confidence': round(conf, 3),
                'diseases': [disease_entry],
            }
            chickens.append(chicken)

            if is_disease:
                diseases.append({
                    **disease_entry,
                    'chicken_bbox': [x1, y1, x2, y2],
                })
                has_disease = True

        return {
            'source_file': file_path,
            'coop_id': coop_id,
            'device_id': device_id,
            'chicken_count': len(chickens),
            'has_disease': has_disease,
            'chickens': chickens,
            'diseases': diseases,
            'image_shape': img.shape[:2],
        }

    def annotate_and_save(self, file_path, result, detection_id=None, image=None):
        if 'error' in result:
            return None

        if image is not None:
            img = image
        else:
            img = self.load_image(file_path)
        if img is None:
            return None

        for chicken in result.get('chickens', []):
            x1, y1, x2, y2 = chicken['bbox']

            has_disease = False
            disease_label = ""
            for d in chicken.get('diseases', []):
                dname = d.get('disease', '').lower()
                if dname not in ['healthy', 'healthys', '']:
                    has_disease = True
                    disease_label = f"{d['disease']} {d['confidence']:.2f}"
                    break

            color = (0, 0, 255) if has_disease else (0, 255, 0)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            label = disease_label if has_disease else f"Healthy {chicken['confidence']:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
            cv2.putText(img, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        save_dir = os.path.join(BASE_DIR, 'static', 'ai_detections')
        os.makedirs(save_dir, exist_ok=True)

        if detection_id:
            filename = f'detection_{detection_id}.jpg'
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f'detection_{timestamp}.jpg'

        save_path = os.path.join(save_dir, filename)
        success = cv2.imwrite(save_path, img)
        if not success:
            import logging
            logging.error(f"Failed to save annotated image to {save_path}")
            return None
        return f'/ai_detections/{filename}'

    def detect_video(self, file_path, coop_id=None, device_id=None, interval=30):
        if not os.path.exists(file_path):
            return {'error': f'File not found: {file_path}'}

        cap = cv2.VideoCapture(file_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_idx = 0
        all_results = []
        last_frame = None

        aggregated_chickens = []
        aggregated_diseases = []
        has_any_disease = False
        best_frame_idx = -1
        best_disease_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % interval == 0:
                temp_path = f"_temp_frame_{frame_idx}.jpg"
                write_success = cv2.imwrite(temp_path, frame)
                if not write_success:
                    import logging
                    logging.warning(f"Failed to write temp frame {temp_path}")
                    frame_idx += 1
                    continue

                result = self.detect(temp_path, coop_id=coop_id, device_id=device_id)
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

                if 'error' not in result:
                    result['frame_idx'] = frame_idx
                    result['timestamp_sec'] = frame_idx / fps if fps > 0 else 0
                    all_results.append(result)
                    last_frame = frame

                    # Aggregate chickens and diseases
                    for chicken in result.get('chickens', []):
                        aggregated_chickens.append(chicken)
                        for d in chicken.get('diseases', []):
                            dname = d.get('disease', '').lower()
                            if dname not in ['healthy', 'healthys', '']:
                                has_any_disease = True
                                disease_entry = {
                                    **d,
                                    'chicken_bbox': chicken['bbox'],
                                    'frame_idx': frame_idx,
                                }
                                aggregated_diseases.append(disease_entry)

                    # Track best frame (most diseases)
                    disease_count = len([d for d in result.get('diseases', []) if d.get('disease', '').lower() not in ['healthy', 'healthys', '']])
                    if disease_count > best_disease_count:
                        best_disease_count = disease_count
                        best_frame_idx = frame_idx

            frame_idx += 1

        cap.release()

        if all_results:
            # Build aggregated result
            final_result = {
                'source_file': file_path,
                'coop_id': coop_id,
                'device_id': device_id,
                'chicken_count': len(aggregated_chickens),
                'has_disease': has_any_disease,
                'chickens': aggregated_chickens,
                'diseases': aggregated_diseases,
                'image_shape': all_results[0].get('image_shape', (0, 0)),
                'frame_idx': best_frame_idx if best_frame_idx >= 0 else all_results[-1].get('frame_idx', 0),
                'total_frames': total_frames,
                'processed_frames': len(all_results),
                '_last_frame': last_frame,
            }
            return final_result
        return {'error': 'No frames processed'}
