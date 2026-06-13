"""
Flask Application Entry Point

Sử dụng mô hình Application Factory (create_app).
Hỗ trợ cấu hình đa môi trường (Development/Production/Testing).
Hỗ trợ cấu hình đa môi trường (Development/Production/Testing).
"""

# ============================================================
# 1. IMPORTS - Thư viện cần thiết
# ============================================================

import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from dotenv import load_dotenv

# Import cấu hình và database từ project
from config import config
from models import db

# Import pages blueprint cho frontend routing
from api.routes.pages import pages_bp

# Load biến môi trường từ .env file (nếu có)
load_dotenv()

# SocketIO will be initialized inside create_app
socketio = None


# ============================================================
# 2. APPLICATION FACTORY FUNCTION
# ============================================================

def create_app(config_name='development'):
    """
    Tạo và cấu hình Flask application.
    
    Args:
        config_name: Tên cấu hình ('development', 'production', 'testing')
                         Mặc định là 'development'
    
    Returns:
        Flask application instance
    """
    
    import os as _os
    import logging
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # --- Khởi tạo Flask app ---
    # template_folder='templates': Chỉ chỉ định thư mục chứa HTML templates
    # static_folder: Chỉ chỉ định thư mục chứa file tĩnh (CSS, JS, images)
    # Đường dẫn: từ backend/ đi ra ngoài đến static/
    base_dir = _os.path.dirname(_os.path.abspath(__file__))
    project_root = _os.path.dirname(base_dir)
    static_dir = _os.path.join(project_root, 'static')
    
    app = Flask(__name__, 
                template_folder=static_dir,
                static_folder=static_dir,
                static_url_path='')
    
    # --- Cấu hình từ config.py ---
    # config[config_name] sẽ lấy class Config tương ứng
    app.config.from_object(config[config_name])
    
    # ============================================================
    # 3. KHỞI TẠO CÁC EXTENSIONS
    # ============================================================
    
    # --- SQLAlchemy Database ---
    # Khởi tạo SQLAlchemy với app
    db.init_app(app)
    
    # --- CORS (Cross-Origin Resource Sharing) ---
    # Cho phép frontend (static folder) gọi API
    # resources={r"/api/*": {"origins": "*"}} chỉ áp dụng cho /api/*
    CORS(app, resources={r"/api/*": {"origins": "*", "allow_headers": ["Authorization", "Content-Type"]}})
    
    # --- JWT Manager ---
    # Quản lý xác thực người dùng bằng JWT token
    jwt = JWTManager(app)
    
    # --- SocketIO ---
    # Real-time communication for camera detection
    global socketio
    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # Initialize websocket_server with the socketio instance
    import websocket_server
    websocket_server.init_socketio(socketio)
    
    # ============================================================
    # 4. REGISTER BLUEPRINTS - Đăng ký API routes
    # ============================================================
    
    # Import api blueprint từ api/__init__.py
    # api_bp đã được định nghĩa với url_prefix='/api'
    from api import api_bp
    app.register_blueprint(api_bp)
    
    # --- Pages Blueprint (Frontend Routes) ---
    # Đăng ký pages_bp KHÔNG có prefix để render HTML trực tiếp
    # Các routes: /, /coops, /devices, /cameras, /login, etc.
    app.register_blueprint(pages_bp)
    
    # ============================================================
    # 5. TẠO DATABASE TỰ ĐỘNG
    # ============================================================
    
    # Tạo các bảng database trong application context
    # db.create_all() sẽ tạo tất cả tables định nghĩa trong models.py
    # Chỉ tạo khi file database chưa tồn tại để tránh ghi đè dữ liệu
    
    with app.app_context():
        db_file = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')

        if not _os.path.exists(db_file):
            print(f"Creating new database: {db_file}")
            db.create_all()
            print("Database tables created successfully!")
        else:
            db.create_all()
            print(f"Database already exists: {db_file}")

        # Auto-migrate: add missing columns to unconnected_devices
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        if 'unconnected_devices' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('unconnected_devices')}
            migrations = []
            if 'device_id' not in existing_cols:
                migrations.append('ALTER TABLE unconnected_devices ADD COLUMN device_id INTEGER')
            if 'previous_coop_id' not in existing_cols:
                migrations.append('ALTER TABLE unconnected_devices ADD COLUMN previous_coop_id INTEGER')
            if 'unconnected_at' not in existing_cols:
                migrations.append('ALTER TABLE unconnected_devices ADD COLUMN unconnected_at DATETIME')
            for migration_sql in migrations:
                try:
                    db.session.execute(text(migration_sql))
                    db.session.commit()
                    print(f"Migration applied: {migration_sql}")
                except Exception as e:
                    db.session.rollback()
                    print(f"Migration skipped (column may exist): {e}")
        
        # Auto-migrate: add camera stream columns to devices
        if 'devices' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('devices')}
            device_migrations = []
            if 'stream_url' not in existing_cols:
                device_migrations.append('ALTER TABLE devices ADD COLUMN stream_url TEXT')
            if 'stream_type' not in existing_cols:
                device_migrations.append("ALTER TABLE devices ADD COLUMN stream_type TEXT DEFAULT 'rtsp'")
            if 'stream_enabled' not in existing_cols:
                device_migrations.append('ALTER TABLE devices ADD COLUMN stream_enabled BOOLEAN DEFAULT 0')
            if 'frame_skip' not in existing_cols:
                device_migrations.append('ALTER TABLE devices ADD COLUMN frame_skip INTEGER DEFAULT 5')
            if 'analysis_interval_seconds' not in existing_cols:
                device_migrations.append('ALTER TABLE devices ADD COLUMN analysis_interval_seconds INTEGER DEFAULT 10')
            for migration_sql in device_migrations:
                try:
                    db.session.execute(text(migration_sql))
                    db.session.commit()
                    print(f"Migration applied: {migration_sql}")
                except Exception as e:
                    db.session.rollback()
                    print(f"Migration skipped (column may exist): {e}")
    
    # ============================================================
    # 6. API HEALTH CHECK ROUTE
    # ============================================================
    
    @app.route('/health')
    def health():
        """
        Health check endpoint
        
        Returns:
            JSON: Trạng thái health của server
        """
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        })
    
    # ============================================================
    # 7. ERROR HANDLERS - Xử lý lỗi
    # ============================================================
    
    @app.errorhandler(404)
    def not_found(error):
        """Xử lý lỗi 404 - Not Found"""
        return jsonify({
            'error': 'Not Found',
            'message': 'Endpoint không tồn tại'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Xử lý lỗi 500 - Internal Server Error"""
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Đã xảy ra lỗi server'
        }), 500
    
    return app


def init_stream_manager(app):
    """Initialize stream manager with app context (call after app creation)"""
    with app.app_context():
        from services.stream_manager import stream_manager
        stream_manager.init_from_database()
        
        # Set up WebSocket callbacks
        from websocket_server import (
            emit_detection_result, emit_camera_status, emit_stats_update,
            has_subscribers
        )
        
        def on_detection(device_id, detections, annotated_frame, image_path=None):
            if has_subscribers(device_id):
                emit_detection_result(device_id, detections, annotated_frame, image_path=image_path)
        
        def on_frame(device_id, frame):
            pass  # Frame callback for MJPEG streaming
        
        def on_status_change(device_id, status):
            emit_camera_status(device_id, status)
        
        stream_manager.set_callbacks(
            on_detection=on_detection,
            on_frame=on_frame,
            on_status_change=on_status_change
        )
        
        # Auto-start cameras if enabled
        if os.environ.get('AUTO_START_CAMERAS', 'true').lower() == 'true':
            stream_manager.start_all()


# ============================================================
# 8. MAIN - Chạy ứng dụng
# ============================================================

if __name__ == '__main__':
    config_name = os.environ.get('FLASK_ENV', 'development')
    print(f"Starting Flask app with config: {config_name}")
    app = create_app(config_name)
    init_stream_manager(app)
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader for SocketIO
    )