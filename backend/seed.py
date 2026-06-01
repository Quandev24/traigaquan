"""
Script seed.py - Nạp dữ liệu mẫu vào cơ sở dữ liệu

Script này tạo dữ liệu mẫu cho hệ thống Quản lý Trang trại Gà.
Chạy độc lập với: python seed.py

Dữ liệu được tạo:
- 1 tài khoản admin
- 5 chuồng gà (A, B, C, D, E)
- 15 thiết bị IoT (3 thiết bị/ chuồng)
- 100 bản ghi dữ liệu môi trường (20/ chuồng)
- 15 lịch cho ăn (3/ chuồng)
"""

import sys
import os
import random
from datetime import datetime, timedelta, UTC

# Thêm thư mục hiện tại vào path để import được config và models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import ứng dụng Flask và cấu hình
from flask import Flask
from config import config

# Import database models và db instance
from models import db, User, Coop, Device, CoopDevice, Environment, FeedSchedule, Alert, VideoRecording, WarehouseInventory, FeedConsumption


# =============================================================================
# KHỞI TẠO ỨNG DỤNG FLASK
# =============================================================================

def create_app():
    """Tạo và cấu hình Flask app cho script seed."""
    app = Flask(__name__)
    
    # Load cấu hình development (sử dụng SQLite cục bộ)
    app. config.from_object(config['development'])
    
    # Khởi tạo SQLAlchemy với app           
    db.init_app(app)
    
    return app


# =============================================================================
# SEED DỮ LIỆU NGƯỜI DÙNG
# =============================================================================

def seed_users():
    """
    Tạo tài khoản admin mặc định.
    
    Tài khoản admin được tạo:
    - Username: admin
    - Password: admin123 (đã được mã hóa bằng werkzeug)
    - Role: admin
    - Email: admin@chickenfarm.com
    """
    print("  Đang tạo tài khoản admin...")
    
    # Kiểm tra nếu admin đã tồn tại thì bỏ qua
    if User.query.filter_by(username='admin').first():
        print("    [Bỏ qua] Tài khoản admin đã tồn tại")
        return User.query.filter_by(username='admin').first()
    
    # Tạo user admin mới
    admin = User(
        username='admin',
        email='admin@chickenfarm.com',
        full_name='Quản trị viên',
        role='admin'
    )
    
    # Mã hóa mật khẩu bằng werkzeug.security.generate_password_hash
    # Đây là phương pháp bảo mật an toàn, sử dụng thuật toán pbkdf2:sha256
    admin.set_password('admin123')
    
    # Lưu vào database
    db.session.add(admin)
    db.session.commit()
    
    print(f"    [OK] Đã tạo tài khoản: {admin.username}")
    return admin


# =============================================================================
# SEED DỮ LIỆU CHUỒNG GÀ
# =============================================================================

def seed_coops():
    """
    Tạo 5 chuồng gà với thông tin mẫu.
    
    Thông tin mỗi chuồng:
    | Tên | Số gà | Sức chứa | Diện tích | Vị trí |
    |-----|------|---------|---------|--------|
    | Chuồng A | 480 | 500 | 50m² | Tầng 1 - Khu A |
    | Chuồng B | 450 | 500 | 50m² | Tầng 1 - Khu B |
    | Chuồng C | 420 | 500 | 50m² | Tầng 2 - Khu A |
    | Chuồng D | 500 | 500 | 50m² | Tầng 2 - Khu B |
    | Chuồng E | 380 | 500 | 50m² | Tầng 3 - Khu A |
    
    Ngưỡng cảnh báo mặc định:
    - Nhiệt độ: 20-30°C
    - Độ ẩm: 50-80%
    - Thức ăn: 20%
    - Nước: 20%
    """
    print("  Đang tạo 5 chuồng gà...")
    
    # Danh sách thông tin chuồng (tên, số gà hiện tại, vị trí)
    coop_data = [
        {'name': 'Chuồng A', 'current_count': 480, 'location': 'Tầng 1 - Khu A', 'has_camera': 1},
        {'name': 'Chuồng B', 'current_count': 450, 'location': 'Tầng 1 - Khu B', 'has_camera': 0},
        {'name': 'Chuồng C', 'current_count': 420, 'location': 'Tầng 2 - Khu A', 'has_camera': 1},
        {'name': 'Chuồng D', 'current_count': 500, 'location': 'Tầng 2 - Khu B', 'has_camera': 1},
        {'name': 'Chuồng E', 'current_count': 380, 'location': 'Tầng 3 - Khu A', 'has_camera': 0},
    ]
    
    coops = []
    
    for data in coop_data:
        # Kiểm tra nếu chuồng đã tồn tại thì bỏ qua
        existing = Coop.query.filter_by(name=data['name']).first()
        if existing:
            print(f"    [Bỏ qua] {data['name']} đã tồn tại")
            coops.append(existing)
            continue
        
        # Tạo chuồng mới với các thông số mặc định
        coop = Coop(
            name=data['name'],
            location=data['location'],
            capacity=500,           # Sức chứa tối đa: 500 gà
            current_count=data['current_count'],  # Số gà hiện tại
            area=50.0,               # Diện tích: 50m²
            has_camera=data.get('has_camera', 0),  # Camera: 0 hoặc 1
            
            # Ngưỡng nhiệt độ: 20-30°C
            temp_min=20.0,
            temp_max=30.0,
            
            # Ngưỡng độ ẩm: 50-80%
            humidity_min=50.0,
            humidity_max=80.0,
            
            # Ngưỡng thức ăn và nước: 20%
            feed_threshold=20.0,
            water_threshold=20.0,
            
            # Lịch cho ăn mặc định: 06:00, 12:00, 18:00
            # Sử dụng datetime.strptime để chuyển string thành Time object
            feed_time_1=datetime.strptime('06:00', '%H:%M').time(),
            feed_time_2=datetime.strptime('12:00', '%H:%M').time(),
            feed_time_3=datetime.strptime('18:00', '%H:%M').time(),
            
            # Chế độ tự động: bật tất cả
            auto_fan=True,
            auto_light=True,
            auto_feed=True,
            auto_water=True,
            
            # Trạng thái: đang hoạt động
            status='active'
        )
        
        db.session.add(coop)
        coops.append(coop)
        print(f"    [OK] {coop.name} - {coop.current_count} gà")
    
    db.session.commit()
    return coops


# =============================================================================
# SEED DỮ LIỆU THIẾT BỊ IOT
# =============================================================================

def seed_devices(coops):
    """
    Tạo thiết bị IoT cho mỗi chuồng.
    
    Mỗi chuồng được gán:
    - 01 Cảm biến nhiệt độ (type: temperature)
    - 01 Cảm biến độ ẩm (type: humidity)
    - 01 Thiết bị điều khiển (type: fan hoặc light)
    - 01 Camera (type: camera) - chỉ cho chuồng có has_camera=1
    """
    print("  Đang tạo thiết bị IoT...")
    
    statuses = ['online', 'offline', 'connecting']
    control_types = ['fan', 'light']
    
    # Dictionary lưu danh sách thiết bị theo coop_id
    coop_devices_map = {}
    device_index = 1
    all_cameras = []

    for coop in coops:
        coop_devices_map[coop.id] = []
        
        # 1. Cảm biến nhiệt độ
        temp_device = Device(
            name=f'Cảm biến nhiệt {coop.name[-1]}',
            type='temperature',
            mac_address=f'AA:BB:CC:DD:EE:{str(device_index).zfill(2)}',
            status=random.choice(statuses),
            is_active=True,
            battery=random.randint(60, 100)
        )
        db.session.add(temp_device)
        coop_devices_map[coop.id].append(temp_device)
        device_index += 1
        
        # 2. Cảm biến độ ẩm
        humid_device = Device(
            name=f'Cảm biến ẩm {coop.name[-1]}',
            type='humidity',
            mac_address=f'AA:BB:CC:DD:EE:{str(device_index).zfill(2)}',
            status=random.choice(statuses),
            is_active=True,
            battery=random.randint(60, 100)
        )
        db.session.add(humid_device)
        coop_devices_map[coop.id].append(humid_device)
        device_index += 1
        
        # 3. Thiết bị điều khiển
        control_type = random.choice(control_types)
        control_name = 'Quạt thông gió' if control_type == 'fan' else 'Đèn LED'
        control_device = Device(
            name=f'{control_name} {coop.name[-1]}',
            type=control_type,
            mac_address=f'AA:BB:CC:DD:EE:{str(device_index).zfill(2)}',
            status=random.choice(statuses),
            is_active=True,
            battery=random.randint(60, 100)
        )
        db.session.add(control_device)
        coop_devices_map[coop.id].append(control_device)
        device_index += 1

        # 4. Camera (chỉ cho chuồng có has_camera=1)
        if coop.has_camera:
            # Camera 1
            camera_1 = Device(
                name=f'Camera 1 - {coop.name}',
                type='camera',
                mac_address=f'CC:AA:BB:DD:EE:{str(device_index).zfill(2)}',
                status='online',
                is_active=True,
                battery=100
            )
            db.session.add(camera_1)
            coop_devices_map[coop.id].append(camera_1)
            all_cameras.append(camera_1)
            device_index += 1

            # Camera 2
            camera_2 = Device(
                name=f'Camera 2 - {coop.name}',
                type='camera',
                mac_address=f'CC:AA:BB:DD:EE:{str(device_index).zfill(2)}',
                status='online',
                is_active=True,
                battery=100
            )
            db.session.add(camera_2)
            coop_devices_map[coop.id].append(camera_2)
            all_cameras.append(camera_2)
            device_index += 1
        
        count = len(coop_devices_map[coop.id])
        print(f"    [OK] {coop.name}: {count} thiết bị đã tạo")
    
    # Điều chỉnh status camera: 1 offline, 1 connecting, còn lại online
    if all_cameras:
        random.shuffle(all_cameras)
        all_cameras[0].status = 'offline'
        if len(all_cameras) > 1:
            all_cameras[1].status = 'connecting'
        for cam in all_cameras[2:]:
            cam.status = 'online'
    
    db.session.commit()
    return coop_devices_map


# =============================================================================
# GÁN THIẾT BỊ VÀO CHUỒNG (Bảng trung gian CoopDevice)
# =============================================================================

def seed_coop_devices(coops, coop_devices_map):
    """
    Gán thiết bị vào các chuồng thông qua bảng trung gian CoopDevice.
    """
    print("  Đang gán thiết bị vào chuồng...")
    
    for coop in coops:
        devices = coop_devices_map.get(coop.id, [])
        for device in devices:
            # Kiểm tra nếu đã tồn tại thì bỏ qua
            existing = CoopDevice.query.filter_by(
                coop_id=coop.id,
                device_id=device.id
            ).first()
            
            if not existing:
                coop_device = CoopDevice(
                    coop_id=coop.id,
                    device_id=device.id
                )
                db.session.add(coop_device)
    
    db.session.commit()
    print("    [OK] Đã gán thiết bị vào chuồng")


# =============================================================================
# SEED DỮ LIỆU MÔI TRƯỜNG
# =============================================================================

def seed_environments(coops):
    """
    Tạo dữ liệu môi trường cho 48 giờ qua.
    
    Mỗi chuồng tạo 48 bản ghi (1 bản ghi/giờ).
    Dữ liệu bao gồm:
    - Nhiệt độ: 26-35°C (dao động ngày-đêm, thấp nhất 2-4h sáng, cao nhất 14-16h)
    - Độ ẩm: 55-85% (cao hơn vào đêm/sáng, thấp hơn vào trưa chiều)
    - Mức thức ăn: 15-95% (giảm dần từ sáng đến tối, tăng sau giờ ăn)
    - Mức nước: 30-95%
    
    Mỗi chuồng có profile riêng để tạo sự khác biệt:
    - Chuồng A: nền nhiệt trung bình, ẩm độ trung bình
    - Chuồng B: nền nhiệt mát hơn 1°C, ẩm hơn 3%
    - Chuồng C: nền nhiệt trung bình, khô hơn 5%
    - Chuồng D: nền nhiệt nóng hơn 2°C (gần ngưỡng max)
    - Chuồng E: mát nhất, ẩm nhất (góc khuất)
    """
    print("  Đang tạo dữ liệu môi trường (48 bản ghi/ chuồng, pattern ngày-đêm)...")
    
    now = datetime.utcnow()
    
    # Profile nhiệt/ẩm cho từng chuồng (dựa trên tên)
    coop_profiles = {
        'Chuồng A': {'temp_base': 31.0, 'temp_offset': 0, 'humid_base': 70, 'humid_offset': 0},
        'Chuồng B': {'temp_base': 31.0, 'temp_offset': -1.0, 'humid_base': 70, 'humid_offset': 3},
        'Chuồng C': {'temp_base': 31.0, 'temp_offset': 0.5, 'humid_base': 70, 'humid_offset': -5},
        'Chuồng D': {'temp_base': 31.0, 'temp_offset': 2.0, 'humid_base': 70, 'humid_offset': 2},
        'Chuồng E': {'temp_base': 31.0, 'temp_offset': -1.5, 'humid_base': 70, 'humid_offset': 5},
    }
    
    feed_schedule_hours = [6, 12, 18]  # Giờ cho ăn: 6h, 12h, 18h
    
    for coop in coops:
        profile = coop_profiles.get(coop.name, coop_profiles['Chuồng A'])
        
        # Tạo 48 bản ghi (47h trước đến hiện tại)
        for i in range(48):
            hours_ago = 47 - i
            recorded_at = now - timedelta(hours=hours_ago)
            hour_of_day = recorded_at.hour
            
            # --- Nhiệt độ: pattern ngày-đêm (sine wave) ---
            # Cao nhất lúc 14h (hour=14), thấp nhất lúc 3h (hour=3)
            hour_angle = (hour_of_day - 14) * (2 * 3.14159 / 24)
            daily_variation = 4.0 * (1 - abs(hour_of_day - 14) / 14) if 0 <= hour_of_day <= 14 else 4.0 * (1 - abs(hour_of_day - 24 - 14) / 14)
            daily_variation = max(0, min(4, daily_variation))
            
            temperature = (profile['temp_base']
                          + profile['temp_offset']
                          + daily_variation * 0.8  # Swing ±3.2°C từ base
                          + random.uniform(-0.5, 0.5))
            temperature = max(24.0, min(38.0, temperature))
            
            # --- Độ ẩm: cao vào đêm/sáng, thấp vào trưa/chiều ---
            humid_hour_factor = (hour_of_day - 14) / 14 if hour_of_day <= 14 else (24 - hour_of_day) / 10
            humid_variation = 15.0 * humid_hour_factor  # ±15% swing
            humidity = (profile['humid_base']
                       + profile['humid_offset']
                       + humid_variation
                       + random.uniform(-3.0, 3.0))
            humidity = max(50.0, min(95.0, humidity))
            
            # --- Feed level: giảm dần từ sáng, tăng mạnh sau giờ ăn ---
            # Giả sử cho ăn lúc 6h, 12h, 18h → feed_level tăng lên ~90% rồi giảm dần
            hours_since_last_feed = min(
                [(hour_of_day - fh) % 24 for fh in feed_schedule_hours],
                key=lambda x: x if x >= 0 else 24 + x
            )
            # Tìm giờ cho ăn gần nhất
            last_feed_hour = None
            min_dist = 24
            for fh in feed_schedule_hours:
                dist = (hour_of_day - fh) % 24
                if dist < min_dist:
                    min_dist = dist
                    last_feed_hour = fh
            
            decay_hours = (hour_of_day - last_feed_hour) % 24
            if decay_hours <= 2:
                # Vừa mới cho ăn: feed level cao 75-95%
                feed_level = random.uniform(75.0, 95.0)
            elif decay_hours <= 6:
                # 2-6h sau khi cho ăn: giảm dần 40-80%
                feed_level = random.uniform(40.0, 80.0)
            else:
                # Trước giờ ăn tiếp theo: thấp 15-50%
                feed_level = random.uniform(15.0, 50.0)
            
            # --- Water level: ổn định hơn, giảm chậm ---
            water_level = 95.0 - (hour_of_day / 24) * 40 + random.uniform(-5.0, 5.0)
            # Reset cao hơn khi gần giờ cấp nước (giả sử 8h và 16h)
            if 8 <= hour_of_day <= 10 or 16 <= hour_of_day <= 18:
                water_level = random.uniform(70.0, 95.0)
            water_level = max(30.0, min(98.0, water_level))
            
            env = Environment(
                coop_id=coop.id,
                temperature=round(temperature, 1),
                humidity=round(humidity, 1),
                feed_level=round(feed_level, 1),
                water_level=round(water_level, 1),
                recorded_at=recorded_at
            )
            db.session.add(env)
        
        print(f"    [OK] {coop.name}: 48 bản ghi môi trường")
    
    db.session.commit()


# =============================================================================
# SEED DỮ LIỆU VIDEO RECORDINGS CHO CAMERA
# =============================================================================

def seed_video_recordings(coops, coop_devices_map):
    """
    Tạo dữ liệu video recordings fake cho mỗi camera.

    Mỗi camera (device type='camera') được tạo 3-5 recordings với
    các loại nguồn khác nhau:
    - text: Nội dung mô tả video dạng text
    - video_url: Link URL video streaming
    - file_path: Đường dẫn file video cục bộ
    """
    print("  Đang tạo video recordings cho camera...")

    now = datetime.utcnow()
    recording_templates = [
        {'name': 'Giám sát buổi sáng', 'source_type': 'video_url',
         'source_value': 'https://storage.example.com/videos/morning_{cam_id}.mp4',
         'duration': 300, 'file_size': 45000000},
        {'name': 'Ghi nhận hoạt động đàn gà', 'source_type': 'text',
         'source_value': 'Đàn gà đang hoạt động bình thường. Nhiệt độ ổn định 25°C. Quan sát thấy khoảng 95% gà đang ăn/uống.',
         'duration': 600, 'file_size': 0},
        {'name': 'Record chiều tối', 'source_type': 'file_path',
         'source_value': 'D:\\Camera_Data\\coop_{coop_id}\\cam_{cam_id}\\20260515_180000.mp4',
         'duration': 900, 'file_size': 135000000},
        {'name': 'Cảnh báo bất thường', 'source_type': 'text',
         'source_value': '[CẢNH BÁO] Phát hiện gà tụ tập bất thường tại góc chuồng. Nhiệt độ khu vực này cao hơn 2°C so với trung bình.',
         'duration': 120, 'file_size': 0},
        {'name': 'Kiểm tra đèn sưởi', 'source_type': 'video_url',
         'source_value': 'https://storage.example.com/videos/heater_check_{cam_id}.mp4',
         'duration': 450, 'file_size': 68000000},
    ]

    count = 0
    for coop in coops:
        devices = coop_devices_map.get(coop.id, [])
        cameras = [d for d in devices if d.type == 'camera']

        for cam in cameras:
            num_recordings = random.randint(3, 5)
            for i in range(num_recordings):
                tmpl = random.choice(recording_templates)
                hours_ago = random.uniform(0, 72)
                recorded_at = now - timedelta(hours=hours_ago)

                source_value = tmpl['source_value'].format(
                    cam_id=cam.id, coop_id=coop.id
                )

                rec = VideoRecording(
                    device_id=cam.id,
                    coop_id=coop.id,
                    name=tmpl['name'],
                    source_type=tmpl['source_type'],
                    source_value=source_value,
                    thumbnail_url=f'/thumbnails/cameras/{cam.id}/thumb_{i+1}.jpg',
                    duration=tmpl['duration'],
                    file_size=tmpl['file_size'],
                    recorded_at=recorded_at,
                )
                db.session.add(rec)
                count += 1

            print(f"    [OK] {cam.name}: {num_recordings} recordings")

    db.session.commit()
    print(f"    [OK] Tổng số: {count} video recordings")


# =============================================================================
# SEED LỊCH CHO ĂN
# =============================================================================

def seed_feed_schedules(coops):
    """
    Tạo lịch cho ăn tự động cho mỗi chuồng.
    
    Mỗi chuồng có 3 mốc gi�� cố định:
    - 06:00: Cho ăn sáng (10kg)
    - 12:00: Cho ăn trưa (10kg)
    - 18:00: Cho ăn chiều (10kg)
    
    Tất cả lịch được bật (enabled=True) theo mặc định.
    """
    print("  Đang tạo lịch cho ăn (3 mốc/ chuồng)...")
    
    # Danh sách giờ cho ăn cố định
    feed_times = [
        (datetime.strptime('06:00', '%H:%M').time(), 'Sáng'),
        (datetime.strptime('12:00', '%H:%M').time(), 'Trưa'),
        (datetime.strptime('18:00', '%H:%M').time(), 'Chiều'),
    ]
    
    for coop in coops:
        for feed_time, label in feed_times:
            # Kiểm tra nếu đã tồn tại thì bỏ qua
            existing = FeedSchedule.query.filter_by(
                coop_id=coop.id,
                time=feed_time
            ).first()
            
            if not existing:
                schedule = FeedSchedule(
                    coop_id=coop.id,
                    time=feed_time,
                    amount=10.0,  # Lượng thức ăn: 10kg
                    enabled=True   # Bật lịch cho ăn
                )
                db.session.add(schedule)
        
        print(f"    [OK] {coop.name}: 3 lịch cho ăn (06:00, 12:00, 18:00)")
    
    db.session.commit()


# =============================================================================
# SEED THIẾT BỊ CHƯA KẾT NỐI
# =============================================================================

def seed_unconnected_devices():
    """
    Tạo một số thiết bị mẫu chưa kết nối để demo tính năng quét thiết bị.
    Tạo cả Device records và UnconnectedDevice records để test flow mới.
    """
    print("  Đang tạo thiết bị chưa kết nối...")
    
    from models import Device, UnconnectedDevice
    
    # Xóa dữ liệu cũ
    UnconnectedDevice.query.delete()
    Device.query.filter(Device.status == 'pending').delete()
    
    devices = [
        {'name': 'Cảm biến nhiệt độ mới', 'type': 'temperature', 'mac_address': 'FF:EE:DD:CC:BB:01'},
        {'name': 'Cảm biến độ ẩm mới', 'type': 'humidity', 'mac_address': 'FF:EE:DD:CC:BB:02'},
        {'name': 'Quạt công nghiệp', 'type': 'fan', 'mac_address': 'FF:EE:DD:CC:BB:03'},
        {'name': 'Đèn sưởi thông minh', 'type': 'light', 'mac_address': 'FF:EE:DD:CC:BB:04'},
        {'name': 'Máy cho ăn tự động v2', 'type': 'feeder', 'mac_address': 'FF:EE:DD:CC:BB:05'},
        {'name': 'Camera AI 4K', 'type': 'camera', 'mac_address': 'FF:EE:DD:CC:BB:06'},
        {'name': 'Camera hồng ngoại', 'type': 'camera', 'mac_address': 'FF:EE:DD:CC:BB:07'},
    ]
    
    for d in devices:
        # Tạo Device record trước (để có device_id)
        device = Device(
            name=d['name'],
            type=d['type'],
            mac_address=d['mac_address'],
            status='pending',  # Status 'pending' để eligible cho add-to-coop
            is_active=False,
            battery=100
        )
        db.session.add(device)
        db.session.flush()  # Lấy device.id
    
        # Tạo UnconnectedDevice với device_id trỏ tới Device
        unconnected = UnconnectedDevice(
            name=d['name'],
            type=d['type'],
            mac_address=d['mac_address'],
            status='pending',
            is_active=False,
            battery=100,
            device_id=device.id  # Liên kết với Device
        )
        db.session.add(unconnected)
    
    db.session.commit()
    print(f"    [OK] Đã tạo {len(devices)} thiết bị chưa kết nối (với Device records)")


# =============================================================================
# SEED DỮ LIỆU KHO
# =============================================================================

def seed_warehouse():
    """
    Tạo dữ liệu kho thức ăn và thuốc mẫu.
    """
    print("  Đang tạo dữ liệu kho...")
    
    items = [
        {'item_name': 'Cám tổng hợp', 'item_type': 'feed', 'quantity_kg': 2500},
        {'item_name': 'Cám viên',     'item_type': 'feed', 'quantity_kg': 1800},
        {'item_name': 'Cám gà con',   'item_type': 'feed', 'quantity_kg': 1200},
        {'item_name': 'Thuốc kháng sinh Enrofloxacin', 'item_type': 'medicine', 'quantity_kg': 50},
        {'item_name': 'Vaccine Newcastle',              'item_type': 'medicine', 'quantity_kg': 20},
        {'item_name': 'Thuốc sát trùng',               'item_type': 'medicine', 'quantity_kg': 100},
        {'item_name': 'Vitamin C dạng bột',            'item_type': 'medicine', 'quantity_kg': 30},
        {'item_name': 'Men tiêu hóa',                  'item_type': 'medicine', 'quantity_kg': 40},
    ]
    
    for item in items:
        existing = WarehouseInventory.query.filter_by(item_name=item['item_name']).first()
        if existing:
            print(f"    [Bỏ qua] {item['item_name']} đã tồn tại")
            continue
        
        inv = WarehouseInventory(
            item_name=item['item_name'],
            item_type=item['item_type'],
            quantity_kg=item['quantity_kg'],
            unit='kg'
        )
        db.session.add(inv)
        print(f"    [OK] {item['item_name']}: {item['quantity_kg']} kg ({item['item_type']})")
    
    db.session.commit()


# =============================================================================
# SEED DỮ LIỆU TIÊU THỤ (FeedConsumption)
# =============================================================================

def seed_feed_consumption(coops):
    """
    Tạo dữ liệu tiêu thụ thức ăn và thuốc trong 30 ngày qua.
    Mỗi ngày mỗi chuồng có 3-5 bản ghi tiêu thụ ngẫu nhiên.
    """
    from datetime import date, timedelta
    print("  Đang tạo dữ liệu tiêu thụ (30 ngày)...")

    feed_items = WarehouseInventory.query.filter_by(deleted=False).all()
    if not feed_items:
        print("    [Bỏ qua] Không có mặt hàng nào trong kho")
        return

    today = date.today()
    records = []
    for coop in coops:
        for day_offset in range(30):
            d = today - timedelta(days=29 - day_offset)
            # Xu hướng tăng dần: ngày càng về sau, gà càng lớn, ăn càng nhiều
            growth_factor = 0.5 + (day_offset / 29) * 1.0  # 0.5x → 1.5x
            num_records = random.randint(3, 5)
            for _ in range(num_records):
                item = random.choice(feed_items)
                # Lượng ăn tăng dần theo ngày
                base_qty = random.uniform(8.0, 25.0)
                qty = round(base_qty * growth_factor, 1)
                records.append(FeedConsumption(
                    coop_id=coop.id,
                    feed_item_id=item.id,
                    feed_item_category=item.item_type,
                    quantity_kg=qty,
                    recorded_date=d,
                ))
    db.session.add_all(records)
    db.session.commit()
    print(f"    [OK] Đã tạo {len(records)} bản ghi tiêu thụ")


# =============================================================================
# SEED CẢNH BÁO MẪU
# =============================================================================

def seed_alerts(coops):
    """
    Tạo một số cảnh báo mẫu để demo.
    
    Cảnh báo được tạo ngẫu nhiên với các loại:
    - temperature: Cảnh báo nhiệt độ cao/thấp
    - humidity: Cảnh báo độ ẩm cao/thấp
    - device: Cảnh báo thiết bị
    
    Mức độ cảnh báo (level):
    - info: Thông tin
    - warning: Cảnh báo
    - critical: Nghiêm trọng
    """
    print("  Đang tạo cảnh báo mẫu...")
    
    # Template cảnh báo
    alert_templates = [
        {'type': 'temperature', 'level': 'warning', 
         'message': 'Nhiệt độ chuồng cao hơn ngưỡng cho phép'},
        {'type': 'humidity', 'level': 'info', 
         'message': 'Độ ẩm trong chuồng ở mức ổn định'},
        {'type': 'device', 'level': 'warning', 
         'message': 'Cảm biến nhiệt độ mất kết nối tạm thời'},
        {'type': 'feed', 'level': 'info', 
         'message': 'Mức thức ăn còn 30%, cần bổ sung'},
    ]
    
    # Tạo 3 cảnh báo ngẫu nhiên cho mỗi chuồng
    now = datetime.utcnow()
    for coop in coops:
        for i in range(3):
            template = random.choice(alert_templates)
            # Alert không resolved: gần đây hơn (1-24h trước)
            # Alert đã resolved: xa hơn (12-48h trước)
            resolved = random.choice([True, False])
            if resolved:
                hours_ago = random.uniform(12, 48)
            else:
                hours_ago = random.uniform(1, 24)
            created_at = now - timedelta(hours=hours_ago)
            
            alert = Alert(
                coop_id=coop.id,
                type=template['type'],
                level=template['level'],
                message=f"{coop.name}: {template['message']}",
                is_resolved=resolved,
                created_at=created_at
            )
            db.session.add(alert)
    
    db.session.commit()
    print("    [OK] Đã tạo cảnh báo mẫu")


# =============================================================================
# XÓA DỮ LIỆU CŨ (RESET DATABASE)
# =============================================================================

def reset_database():
    """
    Xóa tất cả dữ liệu cũ trước khi seed dữ liệu mới.
    
    Thứ tự xóa rất quan trọng để tránh lỗi Foreign Key:
    1. Alert (phụ thuộc Coop, Device)
    2. Environment (phụ thuộc Coop)
    3. FeedSchedule (phụ thuộc Coop)
    4. CoopDevice (phụ thuộc Coop, Device)
    5. Device (độc lập sau khi xóa CoopDevice)
    6. Coop (độc lập sau khi xóa các bảng phụ thuộc)
    7. User (độc lập)
    """
    print("\n[1] Đang xóa dữ liệu cũ...")
    
    # Xóa theo thứ tự để tránh vi phạm ràng buộc khóa ngoài
    print("    Xóa FeedConsumption...")
    FeedConsumption.query.delete()

    print("    Xóa VideoRecording...")
    VideoRecording.query.delete()

    print("    Xóa WarehouseInventory...")
    WarehouseInventory.query.delete()

    print("    Xóa Alert...")
    Alert.query.delete()
    
    print("    Xóa Environment...")
    Environment.query.delete()
    
    print("    Xóa FeedSchedule...")
    FeedSchedule.query.delete()
    
    print("    Xóa CoopDevice...")
    CoopDevice.query.delete()
    
    print("    Xóa Device...")
    Device.query.delete()
    
    print("    Xóa Coop...")
    Coop.query.delete()
    
    print("    Xóa User...")
    User.query.delete()
    
    # Commit sau khi xóa tất cả
    db.session.commit()
    print("    [OK] Đã xóa toàn bộ dữ liệu cũ")


# =============================================================================
# HÀM CHÍNH - CHẠY SEED
# =============================================================================

def run_seed():
    """Hàm chính để chạy toàn bộ quá trình seed dữ liệu."""
    
    # Tạo ứng dụng Flask
    app = create_app()
    
    # Chạy trong application context để có quyền truy cập database
    with app.app_context():
        
        print("=" * 60)
        print("  SEED DỮ LIỆU - HỆ THỐNG QUẢN LÝ TRANG TRẠI GÀ")
        print("=" * 60)
        
        # Tạo bảng database nếu chưa tồn tại
        print("\n[0] Đang tạo bảng database...")
        db.create_all()
        print("    [OK] Bảng database đã sẵn sàng")
        
        # Bước 1: Xóa dữ liệu cũ
        reset_database()
        
        # Bước 2: Seed Users
        print("\n[2] Seed Users...")
        admin = seed_users()
        
        # Bước 3: Seed Coops
        print("\n[3] Seed Coops...")
        coops = seed_coops()
        
        # Bước 4: Seed Devices
        print("\n[4] Seed Devices...")
        devices = seed_devices(coops)
        
        # Bước 5: Seed CoopDevices (gán thiết bị vào chuồng)
        print("\n[5] Seed CoopDevices...")
        seed_coop_devices(coops, devices)
        
        # Bước 6: Seed Environments
        print("\n[6] Seed Environments...")
        seed_environments(coops)
        
        # Bước 7: Seed FeedSchedules
        print("\n[7] Seed FeedSchedules...")
        seed_feed_schedules(coops)

        # Bước 7.1: Seed Video Recordings
        print("\n[7.1] Seed Video Recordings...")
        seed_video_recordings(coops, devices)

        # Bước 7.2: Seed Unconnected Devices
        print("\n[7.2] Seed Unconnected Devices...")
        seed_unconnected_devices()

        # Bước 7.3: Seed Warehouse
        print("\n[7.3] Seed Warehouse...")
        seed_warehouse()
        
        # Bước 7.4: Seed FeedConsumption
        print("\n[7.4] Seed FeedConsumption...")
        seed_feed_consumption(coops)
        
        # Bước 8: Seed Alerts
        print("\n[8] Seed Alerts...")
        seed_alerts(coops)
        
        # In thống kê
        print("\n" + "=" * 60)
        print("  THỐNG KÊ DỮ LIỆU SAU KHI SEED")
        print("=" * 60)
        print(f"  Users:        {User.query.count()}")
        print(f"  Coops:        {Coop.query.count()}")
        print(f"  Devices:      {Device.query.count()}")
        print(f"  CoopDevices:  {CoopDevice.query.count()}")
        print(f"  Environments: {Environment.query.count()}")
        print(f"  FeedSchedules: {FeedSchedule.query.count()}")
        print(f"  VideoRecordings: {VideoRecording.query.count()}")
        print(f"  WarehouseInventory: {WarehouseInventory.query.count()}")
        print(f"  FeedConsumption: {FeedConsumption.query.count()}")
        print(f"  Alerts:       {Alert.query.count()}")
        print("=" * 60)
        
        print("\n[OK] Seed dữ liệu hoàn tất thành công!")
        print("\nThông tin đăng nhập:")
        print("  Username: admin")
        print("  Password: admin123")


# ============================================================================= 
# CHẠY SCRIPT
# =============================================================================

if __name__ == '__main__':
    run_seed()