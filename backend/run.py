"""
Run script for Flask application
"""
import sys
import os

# Add backend directory to Python path (so 'services' module is findable)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
