"""
Coops Routes - API quản lý chuồng trại

Module này cung cấp các endpoint cho việc:
- CRUD chuồng trại (Create, Read, Update, Delete)
- Quản lý thiết bị trong chuồng
- Lấy dữ liệu môi trường (nhiệt độ, độ ẩm,...)
- Lịch sử dữ liệu theo thời gian

Mỗi chuồng có thể chứa nhiều thiết bị và có các thông số môi trường riêng.
Các thông số cảnh báo (ngưỡng nhiệt độ, độ ẩm,...) được cấu hình cho từng chuồng.
"""

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, UTC
import sys
import os
import re
import mimetypes

# Thêm đường dẫn parent vào sys.path để có thể import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Coop, CoopDevice, Device, Environment

# Tạo Blueprint cho routes liên quan đến chuồng
# URL: /api/coops
coops_bp = Blueprint('coops', __name__)


@coops_bp.route('/public', methods=['GET'])
def get_public_coops():
    """
    Lấy danh sách tất cả các chuồng (Không cần auth - cho demo).
    
    Returns:
        200: Array of coop objects (bao gồm environment data mới nhất)
    """
    coops = Coop.query.filter_by(deleted=False).all()
    return jsonify([coop.to_dict(include_environment=True) for coop in coops]), 200


@coops_bp.route('/public/<int:coop_id>', methods=['GET'])
def get_public_coop(coop_id):
    """
    Lấy thông tin một chuồng cụ thể (Không cần auth - cho demo).
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: Coop object
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    return jsonify(coop.to_dict()), 200


@coops_bp.route('/public/<int:coop_id>', methods=['PUT'])
def update_public_coop(coop_id):
    """
    Cập nhật thông tin chuồng (Không cần auth - cho demo).
    
    Args:
        coop_id (int): ID của chuồng cần cập nhật
        Request Body: Các trường cần cập nhật
        
    Returns:
        200: Coop object đã cập nhật
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    data = request.get_json()
    
    coop.name = data.get('name', coop.name)
    coop.location = data.get('location', coop.location)
    coop.capacity = data.get('capacity', coop.capacity)
    coop.current_count = data.get('current_count', coop.current_count)
    coop.area = data.get('area', coop.area)
    coop.temp_min = data.get('temp_min', coop.temp_min)
    coop.temp_max = data.get('temp_max', coop.temp_max)
    coop.humidity_min = data.get('humidity_min', coop.humidity_min)
    coop.humidity_max = data.get('humidity_max', coop.humidity_max)
    coop.feed_threshold = data.get('feed_threshold', coop.feed_threshold)
    coop.water_threshold = data.get('water_threshold', coop.water_threshold)
    coop.auto_fan = data.get('auto_fan', coop.auto_fan)
    coop.auto_light = data.get('auto_light', coop.auto_light)
    coop.auto_feed = data.get('auto_feed', coop.auto_feed)
    coop.auto_water = data.get('auto_water', coop.auto_water)
    
    db.session.commit()
    
    return jsonify(coop.to_dict()), 200


@coops_bp.route('/public/<int:coop_id>/devices', methods=['GET'])
def get_public_coop_devices(coop_id):
    """
    Lấy danh sách thiết bị trong một chuồng (Không cần auth - cho demo).
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: Array of device objects
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    coop_devices = CoopDevice.query.filter_by(coop_id=coop_id, deleted=False).all()
    devices = []
    for cd in coop_devices:
        device = db.session.get(Device, cd.device_id)
        if device and not device.deleted:
            devices.append(device.to_dict())
    
    return jsonify(devices), 200


@coops_bp.route('/public/<int:coop_id>/devices/<int:device_id>', methods=['DELETE'])
def remove_device_from_coop(coop_id, device_id):
    """
    Gỡ thiết bị khỏi chuồng và thêm vào danh sách unconnected (Giữ nguyên Device).
    
    Args:
        coop_id (int): ID của chuồng
        device_id (int): ID của thiết bị
        
    Returns:
        200: Thông báo thành công
        404: Không tìm thấy chuồng hoặc thiết bị
    """
    from models import UnconnectedDevice
    
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    # Kiểm tra xem thiết bị có trong chuồng không (chưa bị xóa mềm)
    coop_device = CoopDevice.query.filter_by(coop_id=coop_id, device_id=device_id, deleted=False).first()
    if not coop_device:
        return jsonify({'error': 'Device not in this coop'}), 404
    
    # Cập nhật trạng thái thiết bị (không xóa)
    device.status = 'offline'
    device.is_active = False
    
    # Thêm vào unconnected list VỚI device_id trỏ tới Device
    unconnected = UnconnectedDevice(
        name=device.name,
        type=device.type,
        mac_address=device.mac_address,
        status='offline',
        is_active=False,
        battery=device.battery,
        device_id=device.id  # Liên kết với Device
    )
    db.session.add(unconnected)
    
    # Gỡ liên kết với chuồng
    db.session.delete(coop_device)
    
    # Commit
    db.session.commit()
    
    # Broadcast update
    broadcast_coop_update(coop_id)
    broadcast_dashboard_update()
    
    return jsonify({'message': 'Device removed from coop'}), 200


@coops_bp.route('/public/<int:coop_id>/environment', methods=['GET'])
def get_public_coop_environment(coop_id):
    """
    Lấy dữ liệu môi trường mới nhất của chuồng (Không cần auth - cho demo).
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: Environment object mới nhất
        404: Không tìm thấy chuồng hoặc chưa có dữ liệu
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    environment = Environment.query.filter_by(coop_id=coop_id).order_by(Environment.recorded_at.desc()).first()
    
    if not environment:
        return jsonify({
            'temperature': 0,
            'humidity': 0,
            'feed_level': 0,
            'water_level': 0,
            'recorded_at': None
        }), 200
    
    return jsonify(environment.to_dict()), 200


@coops_bp.route('/public/<int:coop_id>/history', methods=['GET'])
def get_public_coop_history(coop_id):
    """
    Lấy lịch sử dữ liệu môi trường của chuồng (Không cần auth - cho demo).
    
    Args:
        coop_id (int): ID của chuồng
        limit (int, query param): Số lượng bản ghi (mặc định: 24)
        
    Returns:
        200: Array of environment objects
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    limit = request.args.get('limit', 24, type=int)
    environments = Environment.query.filter_by(coop_id=coop_id).order_by(Environment.recorded_at.desc()).limit(limit).all()
    
    return jsonify([env.to_dict() for env in environments]), 200


# ============================================================
# CAMERA: Serve video/images from video_path.txt (public, no auth)
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

MIME_MAP = {
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.mkv': 'video/x-matroska',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
}


@coops_bp.route('/public/video-paths', methods=['GET'])
def get_video_paths():
    path_file = os.path.join(PROJECT_ROOT, 'video_path.txt')
    if not os.path.exists(path_file):
        return jsonify({'paths': [], 'types': []}), 200

    with open(path_file, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]

    paths = []
    for line in lines:
        if ' = ' in line:
            line = line.split(' = ', 1)[1]
        paths.append(line)

    types = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            types.append('video')
        elif ext in IMAGE_EXTENSIONS:
            types.append('image')
        else:
            types.append('unknown')

    return jsonify({'paths': paths, 'types': types}), 200


@coops_bp.route('/public/serve-media', methods=['GET'])
def serve_media():
    file_path = request.args.get('path', '')
    if not file_path or not os.path.exists(file_path):
        return '', 404

    ext = os.path.splitext(file_path)[1].lower()
    mime_type = MIME_MAP.get(ext)
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range')

    if range_header:
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = file_size - 1
            if match.group(2):
                end = int(match.group(2))
            if start >= file_size:
                return '', 416
            length = end - start + 1
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)
            resp = Response(data, 206, mimetype=mime_type)
            resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Content-Length'] = str(length)
            resp.headers['Cache-Control'] = 'no-cache'
            return resp

    with open(file_path, 'rb') as f:
        data = f.read()
    resp = Response(data, 200, mimetype=mime_type)
    resp.headers['Accept-Ranges'] = 'bytes'
    resp.headers['Content-Length'] = str(file_size)
    return resp


# ============================================================
# DISEASE DETECTION: list & serve detected images
# ============================================================

DISEASE_DIR = os.path.join(PROJECT_ROOT, 'disease_detect')


@coops_bp.route('/public/disease-images', methods=['GET'])
def get_disease_images():
    coop_id = request.args.get('coop_id', type=int)
    if not coop_id:
        return jsonify({'error': 'coop_id is required'}), 400

    coop_dir = os.path.join(DISEASE_DIR, f'coop_{coop_id}')
    if not os.path.exists(coop_dir):
        return jsonify({'images': []}), 200

    files = sorted([
        f for f in os.listdir(coop_dir)
        if f.endswith('.jpg') and f.startswith('camera_2_')
    ], reverse=True)

    return jsonify({'images': files}), 200


@coops_bp.route('/public/serve-disease-media', methods=['GET'])
def serve_disease_media():
    coop_id = request.args.get('coop_id', type=int)
    filename = request.args.get('file', '')

    if not coop_id or not filename:
        return '', 404

    # Security: prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return '', 400

    file_path = os.path.join(DISEASE_DIR, f'coop_{coop_id}', filename)
    # Ensure we're still inside DISEASE_DIR
    file_path = os.path.normpath(file_path)
    if not file_path.startswith(os.path.normpath(DISEASE_DIR)):
        return '', 400

    if not os.path.exists(file_path):
        return '', 404

    ext = os.path.splitext(file_path)[1].lower()
    mime_type = MIME_MAP.get(ext)
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

    with open(file_path, 'rb') as f:
        data = f.read()

    resp = Response(data, 200, mimetype=mime_type)
    resp.headers['Content-Length'] = str(os.path.getsize(file_path))
    resp.headers['Cache-Control'] = 'private, max-age=60'
    return resp


@coops_bp.route('', methods=['GET'])
@jwt_required()
def get_coops():
    """
    Lấy danh sách tất cả các chuồng.

        
    Returns:
        200: Array of coop objects (bao gồm environment data mới nhất và priority)
        401: Unauthorized
    """
    query = Coop.query.filter_by(deleted=False)
    
    coops = query.all()
    return jsonify([coop.to_dict(include_environment=True) for coop in coops]), 200


@coops_bp.route('', methods=['POST'])
@jwt_required()
def create_coop():
    """
    Tạo chuồng mới.
    
    Args:
        Request Body (JSON):
            - name (str): Tên chuồng (bắt buộc)
            - location (str): Địa điểm (tùy chọn)
            - capacity (int): Sức chứa tối đa (mặc định: 500)
            - current_count (int): Số gà hiện tại (mặc định: 0)
            - area (float): Diện tích m² (mặc định: 50)
            - temp_min/max (float): Ngưỡng nhiệt độ
            - humidity_min/max (float): Ngưỡng độ ẩm
            - feed_threshold (int): Ngưỡng thức ăn (%)
            - water_threshold (int): Ngưỡng nước (%)
            - feed_time_1/2/3 (str): Giờ cho ăn
            - auto_fan/light/feed/water (bool): Bật/tắt tự động
        
    Returns:
        201: Coop object đã tạo
        400: Thiếu name
    """
    data = request.get_json()
    
    # Convert time strings to time objects
    def parse_time(time_str, default):
        if not time_str:
            return default
        try:
            from datetime import datetime
            return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return default
    
    from datetime import time as time_obj
    coop = Coop(
        name=data.get('name'),
        location=data.get('location', ''),
        capacity=data.get('capacity', 500),
        current_count=data.get('current_count', 0),
        area=data.get('area', 50),
        # Ngưỡng cảnh báo nhiệt độ
        temp_min=data.get('temp_min', 18),
        temp_max=data.get('temp_max', 28),
        # Ngưỡng cảnh báo độ ẩm
        humidity_min=data.get('humidity_min', 50),
        humidity_max=data.get('humidity_max', 80),
        # Ngưỡng thức ăn/nước
        feed_threshold=data.get('feed_threshold', 30),
        water_threshold=data.get('water_threshold', 30),
        # Lịch cho ăn tự động
        feed_time_1=parse_time(data.get('feed_time_1'), time_obj(6, 0)),
        feed_time_2=parse_time(data.get('feed_time_2'), time_obj(12, 0)),
        feed_time_3=parse_time(data.get('feed_time_3'), time_obj(18, 0)),
        # Cấu hình tự động hóa
        auto_fan=data.get('auto_fan', True),
        auto_light=data.get('auto_light', True),
        auto_feed=data.get('auto_feed', True),
        auto_water=data.get('auto_water', True),
        status='normal'  # Trạng thái mặc định
    )
    
    db.session.add(coop)
    db.session.flush()  # Get coop.id before commit
    
    # Tạo bản ghi môi trường mặc định (NULL) cho chuồng mới
    env = Environment(
        coop_id=coop.id,
        temperature=None,
        humidity=None,
        feed_level=None,
        water_level=None
    )
    db.session.add(env)
    db.session.commit()
    
    return jsonify(coop.to_dict()), 201


@coops_bp.route('/<int:coop_id>', methods=['GET'])
@jwt_required()
def get_coop(coop_id):
    """
    Lấy thông tin một chuồng cụ thể.
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: Coop object
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    return jsonify(coop.to_dict()), 200


@coops_bp.route('/<int:coop_id>', methods=['PUT'])
@jwt_required()
def update_coop(coop_id):
    """
    Cập nhật thông tin chuồng.
    
    Args:
        coop_id (int): ID của chuồng cần cập nhật
        Request Body: Các trường cần cập nhật
        
    Returns:
        200: Coop object đã cập nhật
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    data = request.get_json()
    
    # Cập nhật các trường được gửi lên, giữ nguyên giá trị cũ nếu không có
    coop.name = data.get('name', coop.name)
    coop.location = data.get('location', coop.location)
    coop.capacity = data.get('capacity', coop.capacity)
    coop.current_count = data.get('current_count', coop.current_count)
    coop.area = data.get('area', coop.area)
    coop.temp_min = data.get('temp_min', coop.temp_min)
    coop.temp_max = data.get('temp_max', coop.temp_max)
    coop.humidity_min = data.get('humidity_min', coop.humidity_min)
    coop.humidity_max = data.get('humidity_max', coop.humidity_max)
    coop.feed_threshold = data.get('feed_threshold', coop.feed_threshold)
    coop.water_threshold = data.get('water_threshold', coop.water_threshold)
    coop.auto_fan = data.get('auto_fan', coop.auto_fan)
    coop.auto_light = data.get('auto_light', coop.auto_light)
    coop.auto_feed = data.get('auto_feed', coop.auto_feed)
    coop.auto_water = data.get('auto_water', coop.auto_water)
    
    db.session.commit()
    
    return jsonify(coop.to_dict()), 200


@coops_bp.route('/<int:coop_id>', methods=['DELETE'])
@jwt_required()
def delete_coop(coop_id):
    """
    Xóa một chuồng (soft delete).

    Quy trình:
    1. Soft delete chuồng (deleted = True)
    2. Lấy danh sách thiết bị đang gắn với chuồng
    3. Chuyển thiết bị sang bảng unconnected_devices
    4. Soft delete liên kết trong coop_devices
    5. Cập nhật trạng thái thiết bị: status='pending', is_active=False

    Toàn bộ thực hiện trong một transaction, rollback nếu lỗi.

    Args:
        coop_id (int): ID của chuồng cần xóa

    Returns:
        200: {'message': 'Coop deleted successfully', 'devices_moved': N}
        404: Không tìm thấy chuồng
        500: Xóa thất bại
    """
    from models import UnconnectedDevice

    try:
        coop = db.session.get(Coop, coop_id)
        if not coop or coop.deleted:
            return jsonify({'error': 'Coop not found'}), 404

        coop_device_links = CoopDevice.query.filter_by(
            coop_id=coop_id, deleted=False
        ).all()
        device_ids = [cd.device_id for cd in coop_device_links]

        coop.deleted = True

        for cd in coop_device_links:
            device = db.session.get(Device, cd.device_id)
            if device:
                unconnected = UnconnectedDevice(
                    name=device.name,
                    type=device.type,
                    mac_address=device.mac_address,
                    status='pending',
                    is_active=False,
                    battery=device.battery,
                    device_id=device.id,
                    previous_coop_id=coop_id
                )
                db.session.add(unconnected)

                device.status = 'pending'
                device.is_active = False

            cd.deleted = True

        db.session.commit()

        # Task 34: Broadcast update
        broadcast_coop_deleted(coop_id)
        broadcast_dashboard_update()

        return jsonify({
            'message': 'Coop deleted successfully',
            'devices_moved': len(device_ids)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Delete failed, please try again'}), 500


@coops_bp.route('/<int:coop_id>/devices', methods=['GET'])
@jwt_required()
def get_coop_devices(coop_id):
    """
    Lấy danh sách thiết bị trong một chuồng.
    
    Sử dụng bảng trung gian CoopDevice để lấy các thiết bị
    được gán vào chuồng.
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: Array of device objects
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    # Lấy tất cả các link thiết bị-chuồng (chưa bị xóa mềm)
    coop_devices = CoopDevice.query.filter_by(coop_id=coop_id, deleted=False).all()
    devices = []
    for cd in coop_devices:
        device = db.session.get(Device, cd.device_id)
        if device and not device.deleted:
            devices.append(device.to_dict())
    
    return jsonify(devices), 200


@coops_bp.route('/<int:coop_id>/environment', methods=['GET'])
@jwt_required()
def get_coop_environment(coop_id):
    """
    Lấy dữ liệu môi trường mới nhất của chu���ng.
    
    Trả về các thông số:
    - temperature: Nhiệt độ (°C)
    - humidity: Độ ẩm (%)
    - feed_level: Mức thức ăn (%)
    - water_level: Mức nước (%)
    - recorded_at: Thời gian ghi nhận
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: Environment object mới nhất
        404: Không tìm thấy chuồng hoặc chưa có dữ liệu
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    # Lấy bản ghi mới nhất, sắp xếp theo thời gian giảm dần
    environment = Environment.query.filter_by(coop_id=coop_id).order_by(Environment.recorded_at.desc()).first()
    
    if not environment:
        return jsonify({'error': 'No environment data'}), 404
    
    return jsonify(environment.to_dict()), 200


@coops_bp.route('/<int:coop_id>/history', methods=['GET'])
@jwt_required()
def get_coop_history(coop_id):
    """
    Lấy lịch sử dữ liệu môi trường của chuồng.
    
    Args:
        coop_id (int): ID của chuồng
        limit (int, query param): Số lượng bản ghi (mặc định: 24)
        
    Returns:
        200: Array of environment objects
        404: Không tìm thấy chuồng
    """
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    limit = request.args.get('limit', 24, type=int)
    environments = Environment.query.filter_by(coop_id=coop_id).order_by(Environment.recorded_at.desc()).limit(limit).all()
    
    return jsonify([env.to_dict() for env in environments]), 200