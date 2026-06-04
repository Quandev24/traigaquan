from api.routes.coops import coops_bp
from api.routes.devices import devices_bp
from api.routes.dashboard import dashboard_bp
from api.routes.camera import camera_bp
from api.routes.pages import pages_bp

__all__ = [
    'coops_bp', 'devices_bp', 'dashboard_bp', 
    'camera_bp', 'pages_bp'
]