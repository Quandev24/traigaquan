"""API Blueprint Factory - Tạo và đăng ký các Blueprint cho ứng dụng"""
from flask import Blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import và đăng ký các route blueprints với url_prefix
from api.routes.coops import coops_bp
from api.routes.devices import devices_bp
from api.routes.dashboard import dashboard_bp
from api.routes.camera import camera_bp
from api.routes.warehouse import warehouse_bp
from api.routes.ai_detection import ai_bp
from api.routes.chicken_management import chicken_management_bp

# Đăng ký các blueprints vào api_bp với url_prefix tương ứng
api_bp.register_blueprint(coops_bp, url_prefix='/coops')
api_bp.register_blueprint(devices_bp, url_prefix='/devices')
api_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(camera_bp, url_prefix='/camera')
api_bp.register_blueprint(warehouse_bp, url_prefix='/warehouse')
api_bp.register_blueprint(ai_bp, url_prefix='/ai')
api_bp.register_blueprint(chicken_management_bp, url_prefix='/chicken')