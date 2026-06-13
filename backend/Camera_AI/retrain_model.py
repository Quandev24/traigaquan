import os
import multiprocessing

import torch
from ultralytics import YOLO


def main():
    # clear cached GPU memory
    torch.cuda.empty_cache()

    model_path = r'D:\Share_Projects\AutomatedChickenFarmManagement\runs\detect\runs\my_project\model_detect_disease\weights\best.pt'
    data_path = r'D:\Share_Projects\AutomatedChickenFarmManagement\backend\Camera_AI\Preprocess_data\data_disease\Chicken_Disease_2\data.yaml'

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Missing model file: {model_path}")
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Missing data config: {data_path}")

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

