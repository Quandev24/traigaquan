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
from datetime import datetime, timedelta, UTC, date
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import Coop, Device, CoopDevice, Environment, Alert, WarehouseInventory, FeedConsumption, db

# Tạo Blueprint cho routes dashboard
# URL: /api/dashboard
dashboard_bp = Blueprint('dashboard', __name__)


# =========================================================================
# PUBLIC ENDPOINTS (không cần JWT - cho frontend dashboard)
# =========================================================================

@dashboard_bp.route('/public', methods=['GET'])
def get_public_dashboard():
    """
    Lấy toàn bộ dữ liệu dashboard (không cần auth).

    Trả về thông tin tổng hợp cho frontend:
    - Thống kê chuồng, đàn, nhiệt độ, độ ẩm
    - Dữ liệu biểu đồ 24h
    - Danh sách chuồng kèm môi trường
    - Cảnh báo gần đây

    Returns:
        200: Dashboard data object
    """
    now = datetime.now(UTC)

    # --- Thống kê cơ bản ---
    coops = Coop.query.filter_by(deleted=False).all()
    total_coops = len(coops)
    total_chickens = sum(c.current_count for c in coops)

    # --- Nhiệt độ & độ ẩm TB từ bản ghi môi trường mới nhất mỗi chuồng ---
    latest_envs = []
    for coop in coops:
        env = Environment.query.filter_by(coop_id=coop.id, deleted=False).order_by(Environment.recorded_at.desc()).first()
        if env:
            latest_envs.append(env)

    avg_temp = round(sum(e.temperature for e in latest_envs) / len(latest_envs), 1) if latest_envs else 0
    avg_humid = round(sum(e.humidity for e in latest_envs) / len(latest_envs), 1) if latest_envs else 0

    # --- Kho thức ăn ---
    feed_total = db.session.query(func.sum(WarehouseInventory.quantity_kg)).filter(
        WarehouseInventory.item_type == 'feed',
        WarehouseInventory.deleted == False
    ).scalar() or 0

    # --- Dữ liệu biểu đồ 24h (theo giờ) ---
    time_labels = []
    temp_history = []
    humid_history = []
    for i in range(23, -1, -1):
        hour_start = now - timedelta(hours=i + 1)
        hour_end = now - timedelta(hours=i)
        label = hour_end.strftime('%H:00')
        time_labels.append(label)

        # Lấy bản ghi môi trường gần nhất trong khung giờ này cho mỗi chuồng
        hour_temps = []
        hour_humids = []
        for coop in coops:
            env = Environment.query.filter(
                Environment.coop_id == coop.id,
                Environment.deleted == False,
                Environment.recorded_at >= hour_start,
                Environment.recorded_at < hour_end
            ).order_by(Environment.recorded_at.desc()).first()
            if env:
                hour_temps.append(env.temperature)
                hour_humids.append(env.humidity)

        temp_history.append(round(sum(hour_temps) / len(hour_temps), 1) if hour_temps else avg_temp)
        humid_history.append(round(sum(hour_humids) / len(hour_humids), 1) if hour_humids else avg_humid)

    # --- Trends (so với 24h trước) ---
    yesterday_start = now - timedelta(hours=48)
    yesterday_end = now - timedelta(hours=24)

    yesterday_temps = []
    yesterday_humids = []
    for coop in coops:
        env = Environment.query.filter(
            Environment.coop_id == coop.id,
            Environment.deleted == False,
            Environment.recorded_at >= yesterday_start,
            Environment.recorded_at < yesterday_end
        ).order_by(Environment.recorded_at.desc()).first()
        if env:
            yesterday_temps.append(env.temperature)
            yesterday_humids.append(env.humidity)

    yesterday_avg_temp = round(sum(yesterday_temps) / len(yesterday_temps), 1) if yesterday_temps else avg_temp
    yesterday_avg_humid = round(sum(yesterday_humids) / len(yesterday_humids), 1) if yesterday_humids else avg_humid

    temp_diff = round(avg_temp - yesterday_avg_temp, 1)
    humid_diff = round(avg_humid - yesterday_avg_humid, 1)
    temp_trend = f'+{temp_diff}°C' if temp_diff >= 0 else f'{temp_diff}°C'
    humid_trend = f'+{humid_diff}%' if humid_diff >= 0 else f'{humid_diff}%'

    # Chicken trend (ước lượng từ FeedConsumption: so sánh 7 ngày gần vs 7 ngày trước)
    today = date.today()
    last_7_start = today - timedelta(days=7)
    prev_7_start = today - timedelta(days=14)
    
    last_7_consumption = db.session.query(func.sum(FeedConsumption.quantity_kg)).filter(
        FeedConsumption.recorded_date >= last_7_start
    ).scalar() or 0
    
    prev_7_consumption = db.session.query(func.sum(FeedConsumption.quantity_kg)).filter(
        FeedConsumption.recorded_date >= prev_7_start,
        FeedConsumption.recorded_date < last_7_start
    ).scalar() or 0
    
    if prev_7_consumption > 0:
        chicken_change = ((last_7_consumption - prev_7_consumption) / prev_7_consumption) * 100
        chicken_trend = f'+{chicken_change:.1f}%' if chicken_change >= 0 else f'{chicken_change:.1f}%'
    else:
        chicken_trend = '+0.0%'

    # --- Dữ liệu cảnh báo ---
    alerts_list = Alert.query.filter_by(deleted=False, is_resolved=False).order_by(Alert.created_at.desc()).limit(10).all()
    alert_coop_ids = set(a.coop_id for a in alerts_list)
    alerts_data = []
    for a in alerts_list:
        coop_name = Coop.query.filter_by(id=a.coop_id).first().name if a.coop_id else 'Hệ thống'
        alerts_data.append({
            'id': a.id,
            'coop': coop_name,
            'type': a.type,
            'level': a.level,
            'message': a.message,
            'time': a.created_at.isoformat() if a.created_at else None
        })

    # --- Danh sách chuồng kèm môi trường ---
    coops_data = []
    for coop in coops:
        env = Environment.query.filter_by(coop_id=coop.id, deleted=False).order_by(Environment.recorded_at.desc()).first()
        device_total = Device.query.join(CoopDevice).filter(
            CoopDevice.coop_id == coop.id, Device.deleted == False
        ).count()
        device_online = Device.query.join(CoopDevice).filter(
            CoopDevice.coop_id == coop.id, Device.deleted == False,
            Device.status == 'online'
        ).count()
        coops_data.append({
            'id': coop.id,
            'name': coop.name,
            'location': coop.location,
            'chickens': coop.current_count,
            'capacity': coop.capacity,
            'temp': round(env.temperature, 1) if env else 0,
            'humidity': round(env.humidity, 1) if env else 0,
            'feedLevel': round(env.feed_level, 1) if env else 0,
            'waterLevel': round(env.water_level, 1) if env else 0,
            'status': coop.status,
            'alert': coop.id in alert_coop_ids,
            'deviceCount': device_total,
            'onlineDeviceCount': device_online
        })

    # Feed trend (từ FeedConsumption: so sánh lượng tiêu thụ 14 ngày gần vs 14 ngày trước)
    last_14_start = today - timedelta(days=14)
    prev_14_start = today - timedelta(days=28)
    
    last_14_consumption = db.session.query(func.sum(FeedConsumption.quantity_kg)).filter(
        FeedConsumption.recorded_date >= last_14_start
    ).scalar() or 0
    
    prev_14_consumption = db.session.query(func.sum(FeedConsumption.quantity_kg)).filter(
        FeedConsumption.recorded_date >= prev_14_start,
        FeedConsumption.recorded_date < last_14_start
    ).scalar() or 0
    
    if prev_14_consumption > 0:
        feed_change = ((last_14_consumption - prev_14_consumption) / prev_14_consumption) * 100
        feed_trend = f'+{feed_change:.1f}%' if feed_change >= 0 else f'{feed_change:.1f}%'
    else:
        feed_trend = '+0.0%'

    return jsonify({
        'totalChickens': total_chickens,
        'avgTemperature': avg_temp,
        'avgHumidity': avg_humid,
        'remainingFeedStock': round(feed_total, 1),
        'totalCoops': total_coops,
        'chickenTrend': chicken_trend,
        'tempTrend': temp_trend,
        'humidTrend': humid_trend,
        'feedTrend': feed_trend,
        'temperatureHistory': temp_history,
        'humidityHistory': humid_history,
        'timeLabels': time_labels,
        'coops': coops_data,
        'alerts': alerts_data,
        'timestamp': now.isoformat()
    }), 200


# =========================================================================
# AUTHENTICATED ENDPOINTS
# =========================================================================

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
        'timestamp': datetime.now(UTC).isoformat()
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