"""
Dashboard Routes - API thống kê và tổng quan hệ thống

Module này cung cấp các endpoint cho việc:
- Lấy tổng quan dashboard (số lượng chuồng, thiết bị, trạng thái)
- Thống kê chi tiết (số gà, sức chứa, trạng thái chuồng)
- Lấy danh sách cảnh báo
- Lấy hoạt động gần đây

Dữ liệu được tổng hợp từ nhiều bảng: Coop, Device, Environment, Alert
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from datetime import datetime, timedelta
import sys
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import Coop, Device, CoopDevice, Environment, Alert, WarehouseInventory, db

# Tạo Blueprint cho routes dashboard
# URL: /api/dashboard
dashboard_bp = Blueprint('dashboard', __name__)


# ============================================================
# PUBLIC DASHBOARD (không cần JWT) - format camelCase cho index.html
# ============================================================

@dashboard_bp.route('/public', methods=['GET'])
def get_public_dashboard():
    """
    Dashboard public endpoint - không yêu cầu JWT.
    Trả về dữ liệu format camelCase cho index.html.
    """
    # Lấy dữ liệu chuồng
    coops = Coop.query.filter_by(deleted=False).all()

    # Tính tổng số gà
    total_chickens = db.session.query(func.sum(Coop.current_count)).filter(Coop.deleted == False).scalar() or 0

    # Lấy environment mới nhất cho mỗi chuồng
    coop_stats = []
    total_temp = 0
    total_humid = 0
    env_count = 0

    for coop in coops:
        env = Environment.query.filter_by(coop_id=coop.id, deleted=False).order_by(Environment.recorded_at.desc()).first()
        temp = env.temperature if env else None
        humid = env.humidity if env else None
        if temp is not None:
            total_temp += temp
            env_count += 1
        if humid is not None:
            total_humid += humid

        # Đếm số thiết bị trong chuồng
        device_count = CoopDevice.query.filter_by(coop_id=coop.id, deleted=False).count()

        coop_stats.append({
            'id': coop.id,
            'name': coop.name,
            'chickens': coop.current_count,
            'capacity': coop.capacity,
            'temp': temp,
            'humidity': humid,
            'status': coop.status,
            'device_count': device_count,
            'alert': False
        })

    avg_temperature = round(total_temp / env_count, 1) if env_count > 0 else 0
    avg_humidity = round(total_humid / len(coops), 1) if coops else 0

    # Kiểm tra chuồng nào có cảnh báo chưa xử lý
    alert_coop_ids = set()
    for alert in Alert.query.filter(Alert.is_resolved == False, Alert.deleted == False).all():
        if alert.coop_id:
            alert_coop_ids.add(alert.coop_id)
    for cs in coop_stats:
        if cs['id'] in alert_coop_ids:
            cs['alert'] = True

    # Lấy cảnh báo gần đây (tối đa 10)
    recent_alerts = Alert.query.filter_by(deleted=False).order_by(Alert.created_at.desc()).limit(10).all()
    alerts_data = []
    for a in recent_alerts:
        coop_name = ''
        if a.coop_id:
            c = Coop.query.get(a.coop_id)
            if c:
                coop_name = c.name
        alerts_data.append({
            'level': a.level or 'info',
            'coop': coop_name,
            'message': a.message or '',
            'time': a.created_at.isoformat() if a.created_at else ''
        })

    # Tạo time labels và dữ liệu charts từ environment records (24 giờ qua)
    now = datetime.utcnow()
    since = now - timedelta(hours=24)
    envs = Environment.query.filter(
        Environment.deleted == False,
        Environment.recorded_at >= since
    ).order_by(Environment.recorded_at.asc()).all()

    time_labels = []
    temp_history = []
    humid_history = []
    seen_labels = set()
    for e in envs:
        if e.recorded_at:
            label = f"{e.recorded_at.hour}:00"
            key = e.recorded_at.strftime('%Y%m%d%H')
            if key not in seen_labels:
                seen_labels.add(key)
                time_labels.append(label)
                temp_history.append(e.temperature)
                humid_history.append(e.humidity)

    # Tổng tồn kho feed từ WarehouseInventory
    warehouse_items = WarehouseInventory.query.filter_by(deleted=False, item_type='feed').all()
    remaining_feed = sum(item.quantity_kg for item in warehouse_items) if warehouse_items else 0

    return jsonify({
        'totalChickens': int(total_chickens),
        'avgTemperature': avg_temperature,
        'avgHumidity': avg_humidity,
        'remainingFeedStock': remaining_feed,
        'chickenTrend': '+3.2%',
        'tempTrend': '+0.5°C',
        'humidTrend': '-2.0%',
        'feedTrend': '-8.0%',
        'alerts': alerts_data,
        'coops': coop_stats,
        'timeLabels': time_labels,
        'temperatureHistory': temp_history,
        'humidityHistory': humid_history
    }), 200


# ============================================================
# JWT-PROTECTED DASHBOARD (original, gữi nguyên)
# ============================================================

@dashboard_bp.route('', methods=['GET'])
@jwt_required()
def get_dashboard():
    """
    Lấy tổng quan dashboard.
    
    Trả về thông tin tổng hợp về:
    - Số lượng chuồng, thiết bị
    - Số thiết bị online/offline/connecting
    - Nhiệt độ và độ ẩm trung bình
    - Danh sách chuồng với trạng thái
    
    Returns:
        200: {
            "total_coops": 5,
            "total_devices": 20,
            "online_devices": 15,
            "offline_devices": 3,
            "connecting_devices": 2,
            "avg_temperature": 25.5,
            "avg_humidity": 65.2,
            "coops": [...],
            "timestamp": "2025-01-01T00:00:00"
        }
    """
    coops = Coop.query.filter_by(deleted=False).all()
    devices = Device.query.filter_by(deleted=False).all()
    
    # Thống kê cơ bản
    total_coops = len(coops)
    total_devices = len(devices)
    online_devices = len([d for d in devices if d.status == 'online' and d.is_active == True])
    offline_devices = len([d for d in devices if d.status == 'offline' and d.is_active == True])
    connecting_devices = len([d for d in devices if d.status == 'connecting' and d.is_active == True])
    waiting_devices = len([d for d in devices if d.is_active == False])
    
    # Tính trung bình nhiệt độ và độ ẩm
    avg_temperature = 0
    avg_humidity = 0
    coop_stats = []
    
    for coop in coops:
        # Lấy dữ liệu môi trường mới nhất của chuồng
        env = Environment.query.filter_by(coop_id=coop.id, deleted=False).order_by(Environment.recorded_at.desc()).first()
        
        if env:
            avg_temperature += env.temperature or 0
            avg_humidity += env.humidity or 0
        
        # Đếm số thiết bị trong chuồng
        coop_devices = CoopDevice.query.filter_by(coop_id=coop.id, deleted=False).count()
        
        # Thêm vào danh sách thống kê
        coop_stats.append({
            'id': coop.id,
            'name': coop.name,
            'current_count': coop.current_count,
            'capacity': coop.capacity,
            'status': coop.status,
            'device_count': coop_devices,
            'temperature': env.temperature if env else None,
            'humidity': env.humidity if env else None
        })
    
    # Tính trung bình
    if len(coops) > 0:
        # Chỉ tính trung bình trên các chuồng có dữ liệu môi trường để chính xác hơn
        coops_with_env = [c for c in coop_stats if c['temperature'] is not None]
        if len(coops_with_env) > 0:
            avg_temp = sum(c['temperature'] for c in coops_with_env) / len(coops_with_env)
            avg_humid = sum(c['humidity'] for c in coops_with_env) / len(coops_with_env)
        else:
            avg_temp = 0
            avg_humid = 0
    else:
        avg_temp = 0
        avg_humid = 0
    
    return jsonify({
        'total_coops': total_coops,
        'total_devices': total_devices,
        'online_devices': online_devices,
        'offline_devices': offline_devices,
        'connecting_devices': connecting_devices,
        'waiting_devices': waiting_devices,
        'avg_temperature': round(avg_temp, 1),
        'avg_humidity': round(avg_humid, 1),
        'coops': coop_stats,
        'timestamp': datetime.now().isoformat()
    }), 200


@dashboard_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """
    Lấy thống kê chi tiết.
    
    Bao gồm:
    - Tổng số chuồng, thiết bị
    - Tổng số gà, sức chứa tổng
    - Số thiết bị đang online
    - Số cảnh báo chưa xử lý
    - Thống kê trạng thái chuồng
    
    Returns:
        200: {
            "total_coops": 5,
            "total_devices": 20,
            "total_chickens": 2500,
            "total_capacity": 2500,
            "online_devices": 15,
            "unresolved_alerts": 3,
            "coop_status": {"active": 3, "cleaning": 1, "empty": 1}
        }
    """
    chicken_count = db.session.query(func.sum(Coop.current_count)).filter(Coop.deleted == False).scalar() or 0
    total_capacity = db.session.query(func.sum(Coop.capacity)).filter(Coop.deleted == False).scalar() or 0
    online_devices = Device.query.filter(Device.status == 'online', Device.is_active == True, Device.deleted == False).count()
    unresolved_alerts = Alert.query.filter(Alert.is_resolved == False, Alert.deleted == False).count()
    
    coop_status = {
        'active': Coop.query.filter(Coop.status == 'active', Coop.deleted == False).count(),
        'cleaning': Coop.query.filter(Coop.status == 'cleaning', Coop.deleted == False).count(),
        'empty': Coop.query.filter(Coop.status == 'empty', Coop.deleted == False).count()
    }
    
    return jsonify({
        'total_coops': Coop.query.filter_by(deleted=False).count(),
        'total_devices': Device.query.filter_by(deleted=False).count(),
        'total_chickens': chicken_count,
        'total_capacity': total_capacity,
        'online_devices': online_devices,
        'unresolved_alerts': unresolved_alerts,
        'coop_status': coop_status
    }), 200


@dashboard_bp.route('/alerts', methods=['GET'])
@jwt_required()
def get_alerts():
    """
    Lấy danh sách cảnh báo mới nhất (mức độ Critical/Warning).
    
    Chỉ lấy các cảnh báo:
    - is_resolved = False
    - level IN ('critical', 'warning')
    - sắp xếp theo thời gian giảm dần (mới nhất trước)
    
    Query params:
        limit (int): Số lượng cảnh báo (mặc định: 10)
    
    Returns:
        200: Array of alert objects
    """
    limit = request.args.get('limit', 10, type=int)
    alerts = Alert.query.filter(
        Alert.is_resolved == False,
        Alert.deleted == False,
        Alert.level.in_(['critical', 'warning'])
    ).order_by(Alert.created_at.desc()).limit(limit).all()
    
    return jsonify([alert.to_dict() for alert in alerts]), 200


@dashboard_bp.route('/alerts-count', methods=['GET'])
@jwt_required()
def get_alerts_count():
    """
    Đếm tổng số cảnh báo từ nhiều nguồn:
    - Thiết bị mất kết nối (offline/disconnected)
    - Nhiệt độ vượt ngưỡng (temp_min/temp_max)
    - Độ ẩm vượt ngưỡng (humidity_min/humidity_max)
    - Lượng thức ăn dưới ngưỡng (feed_threshold)
    - Lượng nước dưới ngưỡng (water_threshold)

    Returns:
        200: {
            "totalAlerts": <tổng>,
            "breakdown": {
                "deviceOffline": <số>,
                "temperature": <số>,
                "humidity": <số>,
                "food": <số>,
                "water": <số>
            }
        }
    """
    from sqlalchemy import func

    # 1. Thiết bị mất kết nối
    device_offline = Device.query.filter(
        Device.status.in_(['offline', 'disconnected']),
        Device.deleted == False
    ).count()

    # Lấy environment data mới nhất của mỗi coop để kiểm tra
    latest_env_subquery = db.session.query(
        Environment.coop_id,
        func.max(Environment.recorded_at).label('max_recorded')
    ).filter(Environment.deleted == False).group_by(Environment.coop_id).subquery()

    # 2. Nhiệt độ vượt ngưỡng
    temp_alerts = db.session.query(Environment).join(
        Coop, Environment.coop_id == Coop.id
    ).join(
        latest_env_subquery,
        (Environment.coop_id == latest_env_subquery.c.coop_id) &
        (Environment.recorded_at == latest_env_subquery.c.max_recorded)
    ).filter(
        Environment.deleted == False,
        Coop.deleted == False,
        db.or_(
            Environment.temperature < Coop.temp_min,
            Environment.temperature > Coop.temp_max
        )
    ).count()

    # 3. Độ ẩm vượt ngưỡng
    humidity_alerts = db.session.query(Environment).join(
        Coop, Environment.coop_id == Coop.id
    ).join(
        latest_env_subquery,
        (Environment.coop_id == latest_env_subquery.c.coop_id) &
        (Environment.recorded_at == latest_env_subquery.c.max_recorded)
    ).filter(
        Environment.deleted == False,
        Coop.deleted == False,
        db.or_(
            Environment.humidity < Coop.humidity_min,
            Environment.humidity > Coop.humidity_max
        )
    ).count()

    # 4. Lượng thức ăn dưới ngưỡng
    food_alerts = db.session.query(Environment).join(
        Coop, Environment.coop_id == Coop.id
    ).join(
        latest_env_subquery,
        (Environment.coop_id == latest_env_subquery.c.coop_id) &
        (Environment.recorded_at == latest_env_subquery.c.max_recorded)
    ).filter(
        Environment.deleted == False,
        Coop.deleted == False,
        Environment.feed_level < Coop.feed_threshold
    ).count()

    # 5. Lượng nước dưới ngưỡng
    water_alerts = db.session.query(Environment).join(
        Coop, Environment.coop_id == Coop.id
    ).join(
        latest_env_subquery,
        (Environment.coop_id == latest_env_subquery.c.coop_id) &
        (Environment.recorded_at == latest_env_subquery.c.max_recorded)
    ).filter(
        Environment.deleted == False,
        Coop.deleted == False,
        Environment.water_level < Coop.water_threshold
    ).count()

    total_alerts = device_offline + temp_alerts + humidity_alerts + food_alerts + water_alerts

    return jsonify({
        'totalAlerts': total_alerts,
        'breakdown': {
            'deviceOffline': device_offline,
            'temperature': temp_alerts,
            'humidity': humidity_alerts,
            'food': food_alerts,
            'water': water_alerts
        }
    }), 200


@dashboard_bp.route('/recent-activities', methods=['GET'])
@jwt_required()
def get_recent_activities():
    """
    Lấy các hoạt động gần đây.
    
    Tổng hợp các hoạt động từ:
    - Dữ liệu môi trường mới nhất của các chuồng
    
    Returns:
        200: [
            {
                "type": "environment",
                "coop": "Chuồng A",
                "temperature": 26.5,
                "humidity": 68.0,
                "timestamp": "2025-01-01T00:00:00"
            },
            ...
        ]
    """
    activities = []
    
    # Lấy 5 bản ghi môi trường mới nhất
    recent_environments = Environment.query.filter_by(deleted=False).order_by(Environment.recorded_at.desc()).limit(5).all()
    for env in recent_environments:
        coop = Coop.query.filter_by(id=env.coop_id, deleted=False).first()
        if not coop: continue
        
        activities.append({
            'type': 'environment',
            'coop': coop.name,
            'temperature': env.temperature,
            'humidity': env.humidity,
            'timestamp': env.recorded_at.isoformat() if env.recorded_at else None
        })
    
    return jsonify(activities), 200