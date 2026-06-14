"""
Run script for Flask application
"""
import sys
import os

# Add backend directory to Python path (so 'services' module is findable)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from services.disease_detector import DiseaseDetector

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

# Start AI Disease Detector for Camera 2
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(project_root, 'runs', 'detect', 'runs', 'my_project', 'model_detect_disease', 'weights', 'best.pt')
detector = DiseaseDetector(model_path, project_root, app, interval=60, conf_threshold=0.2)
detector.start()

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
