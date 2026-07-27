"""
Disease Detector Service - Chạy AI detection định kỳ cho Camera 2
Mỗi 60s phân tích ảnh từ camera 2, nếu phát hiện bệnh thì lưu ảnh.
"""

import os
import re
import shutil
import threading
import time
import zipfile
from datetime import datetime

import cv2

# ==================== CẤU HÌNH ANNOTATION ====================
CLASS_COLORS = {
    "chicken":          (46, 204, 113),   # xanh lá — Bình thường
    "healthy":          (46, 204, 113),
    "healthys":         (46, 204, 113),
    "cau_trung":        (231, 76, 60),    # đỏ
    "newcastle":        (230, 126, 34),   # cam
    "tu_huyet_trung":   (155, 89, 182),   # tím
    "marek":            (52, 152, 219),   # xanh dương
}

CLASS_DISPLAY_NAMES = {
    "chicken":   "Bình thường",
    "healthy":   "Bình thường",
    "healthys":  "Bình thường",
}

CONF_THRESHOLD = 0.2
# ==============================================================


class DiseaseDetector:

    def __init__(self, model_path, project_root, app, interval=60, conf_threshold=0.2):
        self.model_path = model_path
        self.project_root = project_root
        self.app = app
        self.interval = interval
        self.conf_threshold = conf_threshold
        self.model = None
        self._stop_event = threading.Event()
        self._thread = None
        self._disease_dir = os.path.join(project_root, 'disease_detect')

    def load_model(self):
        from ultralytics import YOLO
        self.model = YOLO(self.model_path)

    def start(self):
        self.load_model()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    self._analyze_all_coops()
            except Exception as e:
                pass
            self._stop_event.wait(self.interval)

    def _get_camera2_path(self):
        path_file = os.path.join(self.project_root, 'video_path.txt')
        if not os.path.exists(path_file):
            return None
        with open(path_file, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
        if len(lines) < 2:
            return None
        line = lines[1]
        if ' = ' in line:
            line = line.split(' = ', 1)[1]
        return line

    def _analyze_all_coops(self):
        camera2_path = self._get_camera2_path()
        if not camera2_path or not os.path.exists(camera2_path):
            return

        results = self.model.predict(camera2_path, conf=self.conf_threshold, verbose=False)
        if not results or len(results) == 0:
            return

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return

        img = cv2.imread(camera2_path)
        if img is None:
            return

        from models import db, Coop
        coops = Coop.query.filter_by(deleted=False).all()
        for coop in coops:
            annotated = self._annotate_image(img.copy(), boxes, results[0].names, coop)
            self._save_disease_image(coop.id, annotated)

    def _annotate_image(self, img, boxes, class_names, coop):
        h, w = img.shape[:2]
        disease_found = False
        detection_count = 0

        # Check if the model is a generic COCO model (contains 'person' class)
        is_generic = "person" in class_names.values()

        for box in boxes:
            conf = float(box.conf[0].cpu().numpy())
            if conf < CONF_THRESHOLD:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            class_name = class_names.get(cls_id, "unknown")

            # Map generic yolov8n.pt class names for the demo
            if is_generic:
                if class_name.lower() in ("bird", "chicken", "cat", "dog"):
                    # Mock disease state for demo
                    mock_val = (coop.id + x1) % 5
                    if mock_val == 0:
                        class_name = "newcastle"
                    elif mock_val == 1:
                        class_name = "cau_trung"
                    elif mock_val == 2:
                        class_name = "marek"
                    else:
                        class_name = "healthy"
                else:
                    # Skip other generic objects
                    continue

            detection_count += 1

            if class_name.lower() not in ("healthy", "healthys", ""):
                disease_found = True

            color = CLASS_COLORS.get(class_name, (128, 128, 128))
            display = CLASS_DISPLAY_NAMES.get(class_name, class_name.title())

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            label = f"{display} {int(conf * 100)}%"
            font_scale = max(0.4, min(0.7, w / 1200))
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)
            cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
            cv2.putText(img, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX,
                        font_scale, (255, 255, 255), 2)

        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if disease_found:
            status_text = "Phat hien benh"
            status_color = (231, 76, 60)
        else:
            status_text = "Binh thuong"
            status_color = (46, 204, 113)

        info_lines = [
            f"Chuong: {coop.name or f'ID {coop.id}'}",
            f"Thoi gian: {now_str}",
            f"So ga phat hien: {detection_count}",
            status_text,
        ]

        y_offset = 30
        for i, line in enumerate(info_lines):
            is_status = (i == len(info_lines) - 1)
            color = status_color if is_status else (255, 255, 255)
            cv2.putText(img, line, (15, y_offset), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 2)
            y_offset += 28

        return img

    def _get_next_counter(self, folder):
        max_num = 0
        pattern = re.compile(r'camera_2_\d+_(\d+)_\d+\.jpg$')
        if os.path.exists(folder):
            for f in os.listdir(folder):
                m = pattern.match(f)
                if m:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
        return max_num + 1

    def _save_disease_image(self, coop_id, annotated_img):
        coop_dir = os.path.join(self._disease_dir, f'coop_{coop_id}')
        os.makedirs(coop_dir, exist_ok=True)

        jpgs = sorted([
            f for f in os.listdir(coop_dir)
            if f.endswith('.jpg') and f.startswith('camera_2_')
        ])

        if len(jpgs) >= 8:
            now = datetime.now()
            zip_name = f"backup_{now:%Y%m%d}_{now:%H%M%S}.zip"
            zip_path = os.path.join(coop_dir, zip_name)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for jpg in jpgs:
                    zf.write(os.path.join(coop_dir, jpg), jpg)
                    os.remove(os.path.join(coop_dir, jpg))

        counter = self._get_next_counter(coop_dir)
        now = datetime.now()
        filename = f"camera_2_{coop_id}_{counter}_{now:%H%M%S}.jpg"
        dest_path = os.path.join(coop_dir, filename)
        cv2.imwrite(dest_path, annotated_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
