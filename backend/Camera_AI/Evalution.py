import os
import cv2
from ultralytics import YOLO
import matplotlib.pyplot as plt

def test_with_img():
    # Test model với ảnh \
    test_dir = "Data/Test_data/Images"
    img_paths = os.listdir(test_dir)
    n_show = 6
    selected_imgs = img_paths[:n_show]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))  # 2 hàng, 3 cột
    axes = axes.flatten()

    for ax, img_path in zip(axes, selected_imgs):
        full_path = os.path.join(test_dir, img_path)
        results = model.predict(source=full_path, conf=0.6, save=False)
        result = results[0]

        plotted_img = result.plot()  # numpy array có vẽ box
        ax.imshow(plotted_img)
        ax.axis("off")
        ax.set_title(img_path)

    plt.tight_layout()
    plt.show()

def test_with_video():
    test_dir = r"Backend\Camera_AI\Data\Test_data\Videos"
    video_path = os.listdir(test_dir)[0]
    full_video_path = os.path.join(test_dir,video_path)

    cap = cv2.VideoCapture(full_video_path)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model.predict(source=frame, conf=0.6, save=False)
        result = results[0]

        # vẽ bounding box lên frame
        plotted_frame = result.plot()


        # hiển thị frame
        cv2.imshow("YOLO Video Test", plotted_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    
if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(BASE_DIR, 'runs', 'detect', 'runs', 'my_project', 'yolo_model', 'weights', 'best.pt')
    model = YOLO(model_path)
    test_with_video()


            

