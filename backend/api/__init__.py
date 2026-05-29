"""API Blueprint Factory - Tạo và đăng ký các Blueprint cho ứng dụng"""
from flask import Blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import và đăng ký các route blueprints với url_prefix
from api.routes.auth import auth_bp
from api.routes.coops import coops_bp
from api.routes.devices import devices_bp
from api.routes.dashboard import dashboard_bp
from api.routes.camera import camera_bp
from api.routes.feed_schedule import feed_schedule_bp
from api.routes.environment import environment_bp
from api.routes.alerts import alerts_bp
from api.routes.warehouse import warehouse_bp

# Đăng ký các blueprints vào api_bp với url_prefix tương ứng
api_bp.register_blueprint(auth_bp, url_prefix='/auth')
api_bp.register_blueprint(coops_bp, url_prefix='/coops')
api_bp.register_blueprint(devices_bp, url_prefix='/devices')
api_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(camera_bp, url_prefix='/camera')
api_bp.register_blueprint(feed_schedule_bp, url_prefix='/feed-schedule')
api_bp.register_blueprint(environment_bp, url_prefix='/environment')
api_bp.register_blueprint(alerts_bp, url_prefix='/alerts')
api_bp.register_blueprint(warehouse_bp, url_prefix='/warehouse')