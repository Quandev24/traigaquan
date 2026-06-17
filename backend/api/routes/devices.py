"""
Devices Routes - API quản lý thiết bị IoT

Module này cung cấp các endpoint cho việc:
- CRUD thiết bị (Create, Read, Update, Delete)
- Kết nối thiết bị mới (quét QR / nhập mã)
- Bật/tắt thiết bị
- Gán thiết bị vào chuồng
- Cập nhật tên thiết bị sau khi kết nối thành công

Các loại thiết bị được hỗ trợ:
- sensor: Cảm biến (nhiệt độ, độ ẩm)
- fan: Quạt
- light: Đèn
- feeder: Hệ thống cho ăn
- camera: Camera

Trạng thái thiết bị:
- online: Đang kết nối và hoạt động
- offline: Không kết nối
- connecting: Đang trong quá trình kết nối
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, UTC
import sys
import os

# Thêm đường dẫn parent vào sys.path để có thể import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Device, CoopDevice, UnconnectedDevice

# Tạo Blueprint cho routes liên quan đến thiết bị
# URL: /api/devices
devices_bp = Blueprint('devices', __name__)

# Stub cho broadcast functions (websocket chưa setup)
def broadcast_device_update(*a, **kw): pass
def broadcast_dashboard_update(*a, **kw): pass
def broadcast_coop_update(*a, **kw): pass
def broadcast_coop_deleted(*a, **kw): pass

# ============================================================
# PUBLIC ENDPOINTS (No Auth - for demo mode)
# ============================================================

@devices_bp.route('/public/unconnected', methods=['GET'])
def get_unconnected_devices():
    """
    Lấy danh sách thiết bị chưa kết nối (Không cần auth - cho demo).
    
    Returns:
        200: Array of unconnected device objects
    """
    devices = UnconnectedDevice.query.all()
    return jsonify([device.to_dict() for device in devices]), 200


@devices_bp.route('/public/unconnected/available', methods=['GET'])
def get_available_unconnected_devices():
    """
    Lấy danh sách thiết bị có thể thêm vào chuồng (từ bảng unconnected_devices).
    
    Chỉ trả về thiết bị:
    - Có device_id (đã được tạo trong bảng Device)
    - Không bị xóa (deleted = 0)
    - Có status KHÔNG trong ('online', 'connecting', 'offline')
    - Chưa được gắn vào chuồng nào (không có trong coop_devices)
    
    Returns:
        200: Array of device objects {id, name, type, mac_address}
    """
    # Query: Join unconnected_devices với devices, lọc theo điều kiện
    results = db.session.query(Device).join(
        UnconnectedDevice, UnconnectedDevice.device_id == Device.id
    ).filter(
        Device.deleted == False,
        Device.status.notin_(['online', 'connecting', 'offline'])
    ).all()
    
    # Lọc bỏ các device đã có trong coop_devices
    attached_device_ids = [cd.device_id for cd in 
                           db.session.query(CoopDevice.device_id).filter_by(deleted=False).all()]
    
    available = [d for d in results if d.id not in attached_device_ids]
    
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'type': d.type,
        'mac_address': d.mac_address,
        'status': d.status
    } for d in available]), 200


@devices_bp.route('/public/unconnected', methods=['POST'])
def add_unconnected_device():
    """
    Thêm thiết bị mới vào danh sách chưa kết nối (Không cần auth - cho demo).
    
    Args:
        Request Body (JSON):
            - name (str): Tên thiết bị
            - type (str): Loại thiết bị
            - mac_address (str): Địa chỉ MAC
            - status (str): Trạng thái
            - is_active (bool): Bật/tắt
            - battery (int): % pin
            
    Returns:
        201: UnconnectedDevice object đã tạo
    """
    data = request.get_json()
    
    device = UnconnectedDevice(
        name=data.get('name'),
        type=data.get('type', 'sensor'),
        mac_address=data.get('mac_address', ''),
        status=data.get('status', 'offline'),
        is_active=data.get('is_active', False),
        battery=data.get('battery', 100)
    )
    
    db.session.add(device)
    db.session.commit()
    
    return jsonify(device.to_dict()), 201


@devices_bp.route('/public/unconnected/<int:device_id>', methods=['DELETE'])
def delete_unconnected_device(device_id):
    """
    Xóa thiết bị khỏi danh sách chưa kết nối (Không cần auth - cho demo).
    
    Args:
        device_id (int): ID của thiết bị
        
    Returns:
        200: Thông báo thành công
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(UnconnectedDevice, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    db.session.delete(device)
    db.session.commit()
    
    return jsonify({'message': 'Device deleted from unconnected list'}), 200


@devices_bp.route('/public/<int:device_id>', methods=['PUT'])
def update_public_device(device_id):
    """
    Cập nhật thông tin thiết bị (Không cần auth - cho demo).
    
    Args:
        device_id (int): ID của thiết bị
        Request Body: Các trường cần cập nhật
        
    Returns:
        200: Device object đã cập nhật
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    data = request.get_json()
    
    device.name = data.get('name', device.name)
    device.type = data.get('type', device.type)
    device.mac_address = data.get('mac_address', device.mac_address)
    device.status = data.get('status', device.status)
    device.is_active = data.get('is_active', device.is_active)
    device.battery = data.get('battery', device.battery)
    
    db.session.commit()
    
    return jsonify(device.to_dict()), 200


@devices_bp.route('/public/<int:device_id>/toggle', methods=['POST'])
def toggle_public_device(device_id):
    """
    Bật/tắt thiết bị (Không cần auth - cho demo).
    
    Args:
        device_id (int): ID của thiết bị
        
    Returns:
        200: {
            "message": "Device toggled",
            "is_active": true/false,
            "device": {...}
        }
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    device.is_active = not device.is_active
    db.session.commit()
    
    # Task 34: Broadcast update
    broadcast_device_update(device_id)
    broadcast_dashboard_update()
    
    return jsonify({
        'message': 'Device toggled',
        'is_active': device.is_active,
        'device': device.to_dict()
    }), 200


@devices_bp.route('/public/<int:device_id>', methods=['DELETE'])
def delete_public_device(device_id):
    """
    Xóa thiết bị (Không cần auth - cho demo).

    Args:
        device_id (int): ID của thiết bị

    Returns:
        200: Thông báo thành công
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404

    coop_devices = CoopDevice.query.filter_by(device_id=device_id).all()
    coop_ids = [cd.coop_id for cd in coop_devices]

    CoopDevice.query.filter_by(device_id=device_id).delete()
    db.session.delete(device)
    db.session.commit()

    return jsonify({'message': 'Device deleted'}), 200


@devices_bp.route('/public/add-to-coop', methods=['POST'])
def add_device_to_coop():
    """
    Thêm thiết bị (từ unconnected list) vào chuồng (Không cần auth - cho demo).
    
    Args:
        Request Body (JSON):
            - unconnected_device_id (int): ID thiết bị trong unconnected list
            - coop_id (int): ID chuồng
            
    Returns:
        201: Device object đã thêm vào coop
        400: Thiếu thông tin
        404: Không tìm thấy thiết bị/chuồng
    """
    data = request.get_json()
    unconnected_device_id = data.get('unconnected_device_id')
    coop_id = data.get('coop_id')
    
    if not unconnected_device_id or not coop_id:
        return jsonify({'error': 'unconnected_device_id and coop_id required'}), 400
    
    # Tìm thiết bị trong unconnected list
    unconnected = db.session.get(UnconnectedDevice, unconnected_device_id)
    if not unconnected:
        return jsonify({'error': 'Unconnected device not found'}), 404
    
    # Kiểm tra chuồng tồn tại
    from models import Coop
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    # Tạo thiết bị mới trong bảng Device
    device = Device(
        name=unconnected.name,
        type=unconnected.type,
        mac_address=unconnected.mac_address,
        status=unconnected.status,
        is_active=unconnected.is_active,
        battery=unconnected.battery
    )
    db.session.add(device)
    db.session.commit()
    
    # Tạo liên kết với chuồng
    coop_device = CoopDevice(coop_id=coop_id, device_id=device.id, is_active=True)
    db.session.add(coop_device)
    
    # Xóa khỏi unconnected list
    db.session.delete(unconnected)
    db.session.commit()
    
    # Task 34: Broadcast update
    broadcast_coop_update(coop_id)
    broadcast_device_update(device.id)
    broadcast_dashboard_update()
    
    return jsonify({
        'message': 'Device added to coop',
        'device': device.to_dict()
    }), 201


@devices_bp.route('/public/attach-to-coop', methods=['POST'])
def attach_device_to_coop():
    """
    Thêm thiết bị có sẵn (từ unconnected_devices) vào chuồng (3-step transaction).
    
    Bước 1: INSERT INTO coop_devices (coop_id, device_id)
    Bước 2: DELETE FROM unconnected_devices WHERE device_id = :device_id
    Bước 3: UPDATE devices SET status = 'connecting', is_active = 1 WHERE id = :device_id
    
    Args:
        Request Body (JSON):
            - device_id (int): ID thiết bị trong bảng Device (từ unconnected)
            - coop_id (int): ID chuồng
            
    Returns:
        200: Device object đã thêm vào coop
        400: Thiếu thông tin
        404: Không tìm thấy thiết bị/chuồng
    """
    data = request.get_json()
    device_id = data.get('device_id')
    coop_id = data.get('coop_id')
    
    if not device_id or not coop_id:
        return jsonify({'error': 'device_id and coop_id required'}), 400
    
    # Kiểm tra chuồng tồn tại
    from models import Coop
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    # Kiểm tra thiết bị tồn tại
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    # Kiểm tra thiết bị đã trong coop chưa
    existing_link = CoopDevice.query.filter_by(
        coop_id=coop_id, device_id=device_id, deleted=False
    ).first()
    if existing_link:
        return jsonify({'error': 'Device already in this coop'}), 400
    
    try:
        # Bước 1: Thêm vào coop_devices
        coop_device = CoopDevice(coop_id=coop_id, device_id=device_id)
        db.session.add(coop_device)
        
        # Bước 2: Xóa khỏi unconnected_devices (nếu có)
        UnconnectedDevice.query.filter_by(device_id=device_id).delete()
        
        # Bước 3: Cập nhật trạng thái Device
        device.status = 'connecting'
        device.is_active = True
        
        db.session.commit()
        
        # Broadcast updates
        broadcast_coop_update(coop_id)
        broadcast_device_update(device_id)
        broadcast_dashboard_update()
        
        return jsonify({
            'message': 'Device attached to coop',
            'device': device.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@devices_bp.route('/public/remove-from-coop/<int:device_id>', methods=['DELETE'])
def remove_device_from_coop(device_id):
    """
    Gỡ thiết bị khỏi chuồng và thêm vào unconnected list (Không cần auth - cho demo).
    
    Args:
        device_id (int): ID của thiết bị
        
    Returns:
        200: Thông báo thành công
        404: Không tìm thấy thiết bị
    """
    from models import Coop
    
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    # Lấy danh sách chuồng của thiết bị trước khi gỡ
    coop_devices = CoopDevice.query.filter_by(device_id=device_id).all()
    coop_ids = [cd.coop_id for cd in coop_devices]
    
    # Gỡ liên kết với chuồng
    CoopDevice.query.filter_by(device_id=device_id).delete()
    
    # Thêm vào unconnected list
    unconnected = UnconnectedDevice(
        name=device.name,
        type=device.type,
        mac_address=device.mac_address,
        status=device.status,
        is_active=device.is_active,
        battery=device.battery
    )
    db.session.add(unconnected)
    
    # Xóa thiết bị
    db.session.delete(device)
    db.session.commit()
    
    # Task 34: Broadcast update
    for coop_id in coop_ids:
        broadcast_coop_update(coop_id)
    broadcast_dashboard_update()
    
    return jsonify({'message': 'Device removed from coop and added to unconnected list'}), 200


@devices_bp.route('', methods=['GET'])
@jwt_required()
def get_devices():
    """
    Lấy danh sách tất cả thiết bị.
    
    Returns:
        200: Array of device objects
        401: Unauthorized
    """
    devices = Device.query.filter_by(deleted=False).all()
    return jsonify([device.to_dict() for device in devices]), 200


@devices_bp.route('/public/all', methods=['GET'])
def get_all_devices_public():
    """
    Lấy danh sách tất cả thiết bị (Không cần auth).
    
    Returns:
        200: Array of device objects
    """
    devices = Device.query.filter_by(deleted=False).all()
    return jsonify([device.to_dict() for device in devices]), 200


@devices_bp.route('', methods=['POST'])
@jwt_required()
def create_device():
    """
    Tạo thiết bị mới (thủ công).
    
    Thường dùng để thêm thiết bị thủ công vào hệ thống,
    không phải qua flow kết nối thiết bị tự động.
    
    Args:
        Request Body (JSON):
            - name (str): Tên thiết bị
            - type (str): Loại thiết bị (sensor/fan/light/feeder/camera)
            - mac_address (str): Địa chỉ MAC
            - status (str): Trạng thái (online/offline/connecting)
            - is_active (bool): Bật/tắt
            - battery (int): % pin
            
    Returns:
        201: Device object đã tạo
    """
    data = request.get_json()
    
    device = Device(
        name=data.get('name'),
        type=data.get('type', 'sensor'),
        mac_address=data.get('mac_address', ''),
        status=data.get('status', 'offline'),
        is_active=data.get('is_active', True),
        battery=data.get('battery', 100)
    )
    
    from models import db
    db.session.add(device)
    db.session.commit()
    
    return jsonify(device.to_dict()), 201


@devices_bp.route('/connect', methods=['POST'])
@jwt_required()
def connect_device():
    """
    Kết nối thiết bị mới.
    
    Đây là endpoint chính cho flow thêm thiết bị từ frontend:
    1. User quét QR hoặc nhập mã thiết bị
    2. Gọi API này với device_id (từ QR/mã)
    3. Nếu thiết bị chưa tồn tại -> tạo mới với status 'connecting'
    4. Nếu thiết bị đã tồn tại -> chuyển status thành 'connecting'
    
    Args:
        Request Body (JSON):
            - device_id (str): ID thiết bị hoặc MAC address
            
    Returns:
        200: {
            "message": "Device connecting",
            "device": {...},
            "status": "connecting"
        }
        400: Thiếu device_id hoặc thiết bị đã online
    """
    data = request.get_json()
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    
    # Tìm thiết bị theo ID hoặc MAC address
    device = Device.query.filter(
        (Device.id == device_id) | 
        (Device.mac_address == device_id)
    ).first()
    
    # Nếu chưa có -> tạo mới
    if not device:
        device = Device(
            name=f"Device {device_id}",
            mac_address=device_id,
            type='sensor',
            status='connecting',  # Trạng thái đang kết nối
            is_active=True,
            battery=100
        )
        from models import db
        db.session.add(device)
        db.session.commit()
        return jsonify({
            'message': 'Device connecting', 
            'device': device.to_dict(),
            'status': 'connecting'
        }), 200
    
    # Kiểm tra thiết bị đã kết nối chưa
    if device.status == 'online':
        return jsonify({'error': 'Device already connected', 'device': device.to_dict()}), 400
    
    # Cập nhật trạng thái sang connecting
    device.status = 'connecting'
    from models import db
    db.session.commit()
    
    return jsonify({
        'message': 'Device connecting', 
        'device': device.to_dict(),
        'status': 'connecting'
    }), 200


@devices_bp.route('/<int:device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    """
    Lấy thông tin một thiết bị cụ thể.
    
    Args:
        device_id (int): ID của thiết bị
        
    Returns:
        200: Device object
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device or device.deleted:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify(device.to_dict()), 200


@devices_bp.route('/public/<int:device_id>', methods=['GET'])
def get_device_public(device_id):
    """
    Lấy thông tin một thiết bị cụ thể (Không cần auth).
    """
    device = db.session.get(Device, device_id)
    if not device or device.deleted:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify(device.to_dict()), 200


@devices_bp.route('/<int:device_id>', methods=['PUT'])
@jwt_required()
def update_device(device_id):
    """
    Cập nhật thông tin thiết bị.
    
    Args:
        device_id (int): ID của thiết bị
        Request Body: Các trường cần cập nhật
        
    Returns:
        200: Device object đã cập nhật
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    data = request.get_json()
    
    device.name = data.get('name', device.name)
    device.type = data.get('type', device.type)
    device.mac_address = data.get('mac_address', device.mac_address)
    device.status = data.get('status', device.status)
    device.is_active = data.get('is_active', device.is_active)
    device.battery = data.get('battery', device.battery)
    
    db.session.commit()
    
    return jsonify(device.to_dict()), 200


@devices_bp.route('/<int:device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    """
    Xóa thiết bị.
    
    Xóa thiết bị sẽ đồng thời xóa các liên kết trong CoopDevice.
    
    Args:
        device_id (int): ID của thiết bị
        
    Returns:
        200: Thông báo thành công
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    # Lấy danh sách chuồng trước khi xóa
    coop_devices = CoopDevice.query.filter_by(device_id=device_id).all()
    coop_ids = [cd.coop_id for cd in coop_devices]
    
    # Xóa các liên kết với chuồng trước
    CoopDevice.query.filter_by(device_id=device_id).delete()
    # Xóa thiết bị
    db.session.delete(device)
    db.session.commit()
    
    # Task 34: Broadcast update
    for coop_id in coop_ids:
        broadcast_coop_update(coop_id)
    broadcast_device_update(device_id)
    broadcast_dashboard_update()
    
    return jsonify({'message': 'Device deleted'}), 200


@devices_bp.route('/<int:device_id>/toggle', methods=['POST'])
@jwt_required()
def toggle_device(device_id):
    """
    Bật/tắt thiết bị.
    
    Chuyển đổi trạng thái is_active của thiết bị.
    
    Args:
        device_id (int): ID của thiết bị
        
    Returns:
        200: {
            "message": "Device toggled",
            "is_active": true/false,
            "device": {...}
        }
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    # Toggle is_active
    device.is_active = not device.is_active
    
    db.session.commit()
    
    # Task 34: Broadcast update
    broadcast_device_update(device_id)
    broadcast_dashboard_update()
    
    return jsonify({
        'message': 'Device toggled',
        'is_active': device.is_active,
        'device': device.to_dict()
    }), 200


@devices_bp.route('/<int:device_id>/assign', methods=['POST'])
@jwt_required()
def assign_device_to_coop(device_id):
    """
    Gán thiết bị vào chuồng.
    
    Tạo liên kết trong bảng CoopDevice để kết nối
    thiết bị với chuồng.
    
    Args:
        device_id (int): ID của thiết bị
        Request Body (JSON):
            - coop_id (int): ID của chuồng
            
    Returns:
        200: Thông báo thành công
        400: Thiếu coop_id hoặc đã gán rồi
        404: Không tìm thấy thiết bị/chuồng
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    data = request.get_json()
    coop_id = data.get('coop_id')
    
    if not coop_id:
        return jsonify({'error': 'coop_id required'}), 400
    
    from models import Coop
    
    # Kiểm tra chuồng tồn tại
    coop = db.session.get(Coop, coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    # Kiểm tra đã gán chưa
    existing = CoopDevice.query.filter_by(coop_id=coop_id, device_id=device_id).first()
    if existing:
        return jsonify({'error': 'Device already assigned to this coop'}), 400
    
    # Tạo liên kết mới
    coop_device = CoopDevice(coop_id=coop_id, device_id=device_id, is_active=True)
    db.session.add(coop_device)
    db.session.commit()
    
    # Task 34: Broadcast update
    broadcast_coop_update(coop_id)
    broadcast_device_update(device_id)
    broadcast_dashboard_update()
    
    return jsonify({'message': 'Device assigned to coop', 'coop_device': {
        'coop_id': coop_id,
        'device_id': device_id,
        'is_active': True
    }}), 200


@devices_bp.route('/<int:device_id>/name', methods=['PATCH'])
@jwt_required()
def update_device_name(device_id):
    """
    Cập nhật tên thiết bị sau khi kết nối thành công.
    
    Đây là endpoint cuối cùng trong flow kết nối thiết bị:
    1. connect_device -> status: 'connecting'
    2. (thiết bị thực tế kết nối thành công)
    3. update_device_name -> status: 'online', cập nhật tên
    
    Args:
        device_id (int): ID của thiết bị
        Request Body (JSON):
            - name (str): Tên mới cho thiết bị
            
    Returns:
        200: Device object đã cập nhật
        400: Thiếu name
        404: Không tìm thấy thiết bị
    """
    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'error': 'name required'}), 400
    
    # Cập nhật tên và đánh dấu đã kết nối
    device.name = name
    device.status = 'online'
    
    db.session.commit()
    
    # Task 34: Broadcast update
    broadcast_device_update(device_id)
    broadcast_dashboard_update()
    
    return jsonify({
        'message': 'Device name updated',
        'device': device.to_dict()
    }), 200


@devices_bp.route('/status-stats', methods=['GET'])
def get_device_status_stats():
    """
    Lấy thống kê thiết bị theo trạng thái (4 trạng thái).
    
    Returns:
        200: {
            "active": <số thiết bị đang hoạt động (is_active = 1 AND status = 'online')>,
            "error": <số thiết bị lỗi (is_active = 1 AND status = 'offline')>,
            "connecting": <số thiết bị đang kết nối (is_active = 1 AND status = 'connecting')>,
            "waiting": <số thiết bị đang chờ kết nối (is_active = 0)>
        }
    """
    stats = {
        'active': Device.query.filter(Device.is_active == True, Device.status == 'online', Device.deleted == False).count(),
        'error': Device.query.filter(Device.is_active == True, Device.status == 'offline', Device.deleted == False).count(),
        'connecting': Device.query.filter(Device.is_active == True, Device.status == 'connecting', Device.deleted == False).count(),
        'waiting': Device.query.filter(Device.is_active == False, Device.deleted == False).count()
    }

    return jsonify(stats), 200


@devices_bp.route('/public/recent', methods=['GET'])
def get_recent_devices():
    """
    Lấy danh sách thiết bị gần đây (Không cần auth - cho demo).
    JOIN các bảng devices, coop_devices, coops để lấy tên chuồng.

    Returns:
        200: Array of recent device objects with coop_name
    """
    from models import Coop

    # Query JOIN để lấy thiết bị kèm thông tin chuồng
    devices = Device.query.filter_by(deleted=False).order_by(Device.updated_at.desc()).limit(10).all()

    devices_list = []
    for device in devices:
        # Lấy tên chuồng đầu tiên nếu có
        coop_name = None
        if device.coops and len(device.coops) > 0:
            coop_name = device.coops[0].name

        devices_list.append({
            'id': device.id,
            'device_name': device.name,
            'status': device.status,
            'type': device.type,
            'coop_name': coop_name
        })

    return jsonify(devices_list), 200