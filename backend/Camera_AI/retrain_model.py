import os
import multiprocessing

import torch
from ultralytics import YOLO


def main():
    # clear cached GPU memory
    torch.cuda.empty_cache()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_path = os.path.join(base_dir, 'runs', 'detect', 'runs', 'my_project', 'model_detect_disease', 'weights', 'best.pt')
    data_path = os.path.join(base_dir, 'backend', 'Camera_AI', 'Preprocess_data', 'data_disease', 'Chicken_Disease_2', 'data.yaml')

    if not os.path.exists(model_path):
        # Try local fallback if runs dir not found
        model_path = 'yolov8n.pt'
    if not os.path.exists(data_path):
        # Fallback path for data config inside workspace if available
        data_path = os.path.join(base_dir, 'backend', 'Camera_AI', 'Data', 'data.yaml')

    model = YOLO(model_path)

    model.detect_disease = model.train(
        data=data_path,
        epochs=100,
        imgsz=416,    # giảm nếu OOM
        batch=4,      # giảm nếu OOM
        device=0,
        plots=False)


if __name__ == '__main__':
    # On Windows the spawn start method requires this guard; include freeze_support for frozen executables
    multiprocessing.freeze_support()
    main()

