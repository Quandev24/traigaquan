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

        from models import db, Coop
        coops = Coop.query.filter_by(deleted=False).all()
        for coop in coops:
            self._save_disease_image(coop.id, camera2_path)

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

    def _save_disease_image(self, coop_id, source_path):
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
        shutil.copy2(source_path, dest_path)
