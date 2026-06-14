"""
Script seed.py - Nạp dữ liệu mẫu vào cơ sở dữ liệu

Script này tạo dữ liệu mẫu cho hệ thống Quản lý Trang trại Gà.
Chạy độc lập với: python seed.py

Dữ liệu được tạo:
- 1 tài khoản admin
- 5 chuồng gà (A, B, C, D, E)
- 40 thiết bị IoT (8 thiết bị/chuồng: nhiệt, ẩm, quạt, đèn, feeder, water, 2 camera)
- 600 bản ghi dữ liệu môi trường (120/chuồng - 4 tháng)
- 15 lịch cho ăn (3/chuồng)
- 7 thiết bị chưa kết nối
"""

import sys
import os
import random
from datetime import datetime, timedelta

# Thêm thư mục hiện tại vào path để import được config và models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import ứng dụng Flask và cấu hình
from flask import Flask
from config import config

# Import database models và db instance
from models import db, User, Coop, Device, CoopDevice, Environment, FeedSchedule, Alert, VideoRecording, UnconnectedDevice, WarehouseInventory, FeedConsumption, MedicineConsumption, ChickenBatch, VaccinationRecord, InventoryLog, HealthRecord


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
		{'name': 'Chuồng B', 'current_count': 450, 'location': 'Tầng 1 - Khu B', 'has_camera': 1},
		{'name': 'Chuồng C', 'current_count': 420, 'location': 'Tầng 2 - Khu A', 'has_camera': 1},
		{'name': 'Chuồng D', 'current_count': 500, 'location': 'Tầng 2 - Khu B', 'has_camera': 1},
		{'name': 'Chuồng E', 'current_count': 380, 'location': 'Tầng 3 - Khu A', 'has_camera': 1},
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

	Mỗi chuồng được gán 8 thiết bị:
	- 01 Cảm biến nhiệt độ (type: temperature) — online
	- 01 Cảm biến độ ẩm (type: humidity) — online
	- 01 Quạt thông gió (type: fan) — online (trừ chuồng D: offline)
	- 01 Đèn LED (type: light) — online
	- 01 Máy cho ăn (type: feeder) — online (trừ chuồng C: connecting)
	- 01 Máy uống (type: water) — online
	- 02 Camera (type: camera) — online
	"""
	print("  Đang tạo thiết bị IoT...")

	# Định nghĩa thiết bị cho từng chuồng (theo coop_id)
	# Mỗi tuple: (type, tên, status)
	device_defs = {
		'A': [
			('temperature', 'Cảm biến nhiệt A',    'online'),
			('humidity',    'Cảm biến ẩm A',       'online'),
			('fan',         'Quạt thông gió A',     'online'),
			('light',       'Đèn LED A',            'online'),
			('feeder',      'Máy cho ăn A',         'online'),
			('water',       'Máy uống A',           'online'),
			('camera',      'Camera 1 - Chuồng A',  'online'),
			('camera',      'Camera 2 - Chuồng A',  'online'),
		],
		'B': [
			('temperature', 'Cảm biến nhiệt B',    'online'),
			('humidity',    'Cảm biến ẩm B',       'online'),
			('fan',         'Quạt thông gió B',     'online'),
			('light',       'Đèn LED B',            'online'),
			('feeder',      'Máy cho ăn B',         'online'),
			('water',       'Máy uống B',           'online'),
			('camera',      'Camera 1 - Chuồng B',  'online'),
			('camera',      'Camera 2 - Chuồng B',  'online'),
		],
		'C': [
			('temperature', 'Cảm biến nhiệt C',    'online'),
			('humidity',    'Cảm biến ẩm C',       'online'),
			('fan',         'Quạt thông gió C',     'online'),
			('light',       'Đèn LED C',            'online'),
			('feeder',      'Máy cho ăn C',         'connecting'),  # Đang chờ kết nối
			('water',       'Máy uống C',           'online'),
			('camera',      'Camera 1 - Chuồng C',  'online'),
			('camera',      'Camera 2 - Chuồng C',  'online'),
		],
		'D': [
			('temperature', 'Cảm biến nhiệt D',    'online'),
			('humidity',    'Cảm biến ẩm D',       'online'),
			('fan',         'Quạt thông gió D',     'offline'),     # Lỗi không kết nối được
			('light',       'Đèn LED D',            'online'),
			('feeder',      'Máy cho ăn D',         'online'),
			('water',       'Máy uống D',           'online'),
			('camera',      'Camera 1 - Chuồng D',  'online'),
			('camera',      'Camera 2 - Chuồng D',  'online'),
		],
		'E': [
			('temperature', 'Cảm biến nhiệt E',    'online'),
			('humidity',    'Cảm biến ẩm E',       'online'),
			('fan',         'Quạt thông gió E',     'online'),
			('light',       'Đèn LED E',            'online'),
			('feeder',      'Máy cho ăn E',         'online'),
			('water',       'Máy uống E',           'online'),
			('camera',      'Camera 1 - Chuồng E',  'online'),
			('camera',      'Camera 2 - Chuồng E',  'online'),
		],
	}

	coop_devices_map = {}
	mac_index = 1

	for coop in coops:
		letter = coop.name[-1]
		devices_for_coop = device_defs.get(letter, [])
		coop_devices_map[coop.id] = []

		for dtype, dname, dstatus in devices_for_coop:
			mac = f'AA:BB:CC:DD:EE:{str(mac_index).zfill(2)}'
			is_active = (dstatus != 'pending')
			battery = 100 if dtype == 'camera' else random.randint(60, 100)

			device = Device(
				name=dname,
				type=dtype,
				mac_address=mac,
				status=dstatus,
				is_active=is_active,
				battery=battery
			)
			db.session.add(device)
			coop_devices_map[coop.id].append(device)
			mac_index += 1

		# Đảm bảo device lỗi (offline) vẫn có is_active=True
		for dev in coop_devices_map[coop.id]:
			if dev.status == 'offline':
				dev.is_active = True

		print(f"    [OK] {coop.name}: {len(devices_for_coop)} thiết bị")

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
	Tạo dữ liệu môi trường trong 4 tháng (120 ngày).

	Mỗi chuồng tạo 120 bản ghi (1 bản ghi/ngày) trong 4 tháng qua.
	Bổ sung thêm dữ liệu chi tiết 30 phút/lần trong 24 giờ gần nhất
	để biểu đồ dashboard hiển thị đường biến động đầy đủ.
	Dữ liệu bao gồm:
	- Nhiệt độ: 22-28°C với xu hướng theo mùa
	- Độ ẩm: 50-80% với biến đổi ngẫu nhiên
	- Mức thức ăn: 30-95%
	- Mức nước: 30-95%
	"""
	print("  Đang tạo dữ liệu môi trường (120 bản ghi/chuồng - 4 tháng)...")

	now = datetime.utcnow()

	for coop in coops:
		for day_offset in range(120):
			recorded_at = now - timedelta(days=119 - day_offset)

			# Nhiệt độ dao động theo ngày: mát hơn vào "mùa trước" (120 ngày trước)
			# Giả lập xu hướng nhiệt độ tăng dần từ 22°C lên 28°C trong 4 tháng
			base_temp = 22.0 + (day_offset / 120) * 6.0  # 22→28°C
			temperature = round(base_temp + random.uniform(-2.0, 2.0), 1)

			# Độ ẩm: 65% ±15%, ngẫu nhiên nhưng ổn định
			humidity = round(random.uniform(50.0, 80.0), 1)

			# Mức thức ăn: dao động từ 30-95% (giả lập việc bổ sung định kỳ)
			feed_level = round(random.uniform(30.0, 95.0), 1)

			# Mức nước: dao động từ 30-95%
			water_level = round(random.uniform(30.0, 95.0), 1)

			env = Environment(
				coop_id=coop.id,
				temperature=temperature,
				humidity=humidity,
				feed_level=feed_level,
				water_level=water_level,
				recorded_at=recorded_at
			)
			db.session.add(env)

		print(f"    [OK] {coop.name}: 120 bản ghi môi trường")

	# Bổ sung dữ liệu chi tiết 30 phút/lần trong 24 giờ gần nhất
	# để biểu đồ biến động nhiệt độ/độ ẩm trên dashboard có đủ data points
	print("  Đang tạo dữ liệu môi trường granular (30 phút/lần - 24 giờ qua)...")

	for coop in coops:
		for minute_offset in range(0, 24 * 60, 30):
			recorded_at = now - timedelta(minutes=(24 * 60 - minute_offset))

			# Nhiệt độ dao động quanh giá trị hiện tại ±1.5°C
			base_temp = 28.0 + random.uniform(-1.5, 1.5)
			temperature = round(base_temp + random.uniform(-0.5, 0.5), 1)

			# Độ ẩm dao động quanh 65% ±10%
			humidity = round(random.uniform(55.0, 75.0), 1)

			feed_level = round(random.uniform(30.0, 95.0), 1)
			water_level = round(random.uniform(30.0, 95.0), 1)

			env = Environment(
				coop_id=coop.id,
				temperature=temperature,
				humidity=humidity,
				feed_level=feed_level,
				water_level=water_level,
				recorded_at=recorded_at
			)
			db.session.add(env)

		print(f"    [OK] {coop.name}: 48 bản ghi granular (24 giờ x 30 phút)")

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
	Tạo dữ liệu kho thức ăn mẫu.

	Gồm 5 mặt hàng (4 loại feed + 1 medicine) với số lượng và ngưỡng tồn tối thiểu.
	"""
	print("  Đang tạo dữ liệu kho thức ăn...")

	items = [
		{'item_name': 'Cám gà con',   'item_type': 'feed',     'quantity_kg': 1500, 'min_threshold_kg': 300},
		{'item_name': 'Cám gà đẻ',    'item_type': 'feed',     'quantity_kg': 1200, 'min_threshold_kg': 200},
		{'item_name': 'Cám gà thịt',  'item_type': 'feed',     'quantity_kg': 800,  'min_threshold_kg': 150},
		{'item_name': 'Premix khoáng', 'item_type': 'feed',     'quantity_kg': 200,  'min_threshold_kg': 50},
		{'item_name': 'Thuốc phòng bệnh','item_type': 'medicine','quantity_kg': 50,  'min_threshold_kg': 10},
	]

	for item in items:
		existing = WarehouseInventory.query.filter_by(item_name=item['item_name']).first()
		if existing:
			print(f"    [Bỏ qua] {item['item_name']} đã tồn tại")
			continue

		inv = WarehouseInventory(**item)
		db.session.add(inv)
		print(f"    [OK] {item['item_name']}: {item['quantity_kg']} kg (ngưỡng: {item['min_threshold_kg']} kg)")

	db.session.commit()
	print("    [OK] Kho thức ăn đã sẵn sàng")


# =============================================================================
# SEED DỮ LIỆU TIÊU THỤ THỨC ĂN
# =============================================================================

def seed_feed_consumption(coops):
	"""
	Tạo dữ liệu tiêu thụ thức ăn mẫu cho 90 ngày gần nhất.
	Mỗi chuồng tiêu thụ 20-80 kg/ngày với biến động ngẫu nhiên.
	"""
	print("  Đang tạo dữ liệu tiêu thụ thức ăn...")
	today = datetime.now().date()
	for coop in coops:
		for i in range(90):
			d = today - timedelta(days=i)
			existing = FeedConsumption.query.filter_by(coop_id=coop.id, recorded_date=d).first()
			if existing:
				continue
			kg = round(random.uniform(20, 80), 1)
			fc = FeedConsumption(coop_id=coop.id, recorded_date=d, quantity_kg=kg)
			db.session.add(fc)
		print(f"    [OK] {coop.name}: 90 ngày dữ liệu")
	db.session.commit()
	print("    [OK] Dữ liệu tiêu thụ thức ăn đã sẵn sàng")


def seed_medicine_consumption(coops):
	"""
	Tạo dữ liệu tiêu thụ thuốc mẫu cho 90 ngày gần nhất.
	Mỗi chuồng tiêu thụ 3-12 kg/ngày với biến động ngẫu nhiên.
	"""
	print("  Đang tạo dữ liệu tiêu thụ thuốc...")
	today = datetime.now().date()
	for coop in coops:
		for i in range(90):
			d = today - timedelta(days=i)
			existing = MedicineConsumption.query.filter_by(coop_id=coop.id, recorded_date=d).first()
			if existing:
				continue
			kg = round(random.uniform(3, 12), 1)
			mc = MedicineConsumption(coop_id=coop.id, recorded_date=d, quantity_kg=kg)
			db.session.add(mc)
		print(f"    [OK] {coop.name}: 90 ngày dữ liệu")
	db.session.commit()
	print("    [OK] Dữ liệu tiêu thụ thuốc đã sẵn sàng")


# =============================================================================
# SEED DỮ LIỆU ĐÀN GÀ & TIÊM PHÒNG
# =============================================================================

def seed_chicken_batches(coops):
	"""Tạo dữ liệu đàn gà mẫu cho các chuồng."""
	print("  Đang tạo dữ liệu đàn gà...")
	breeds = ['Ai Cập', 'Gà Ta', 'Lương Phượng', 'Gà Mía']
	batches = []
	for coop in coops:
		# Tạo 1-2 đàn cho mỗi chuồng
		for i in range(random.randint(1, 2)):
			arrival_date = datetime.now().date() - timedelta(days=random.randint(10, 100))
			batch = ChickenBatch(
				coop_id=coop.id,
				batch_name=f"Đợt {coop.name[-1]}{i+1}",
				quantity=random.randint(100, 250),
				breed=random.choice(breeds),
				arrival_date=arrival_date,
				status='active'
			)
			db.session.add(batch)
			batches.append(batch)
		print(f"    [OK] {coop.name}: Đã tạo đàn gà")
	db.session.commit()
	return batches


def seed_vaccinations(batches):
	"""Tạo dữ liệu tiêm phòng mẫu cho các đàn gà."""
	print("  Đang tạo dữ liệu tiêm phòng...")
	vaccines = ['Newcastle', 'Gumboro', 'Cúm gia cầm', 'Đậu gà']
	for batch in batches:
		# Mỗi đàn tiêm 2-3 loại
		selected_vaccines = random.sample(vaccines, random.randint(2, 3))
		for v_name in selected_vaccines:
			admin_date = batch.arrival_date + timedelta(days=random.randint(5, 15))
			vaccination = VaccinationRecord(
				batch_id=batch.id,
				vaccine_name=v_name,
				administered_date=admin_date,
				next_dose_date=admin_date + timedelta(days=30),
				status='completed',
				notes=f"Tiêm định kỳ cho đàn {batch.batch_name}"
			)
			db.session.add(vaccination)
	db.session.commit()
	print("    [OK] Đã tạo lịch sử tiêm phòng")


def seed_health_records(batches):
	"""Tạo dữ liệu kiểm tra sức khỏe mẫu."""
	print("  Đang tạo dữ liệu kiểm tra sức khỏe...")
	inspectors = ['Nguyễn Văn An', 'Trần Thị Bình', 'Lê Văn Cường']
	results = ['Khỏe mạnh', 'Gà ăn tốt', 'Cần theo dõi thêm', 'Phát hiện gà ủ rũ']
	for batch in batches:
		# Mỗi đàn có 2-4 lần kiểm tra
		for i in range(random.randint(2, 4)):
			check_date = datetime.now() - timedelta(days=random.randint(1, 20))
			r_type = random.choice(['inspection', 'medical_exam'])
			record = HealthRecord(
				batch_id=batch.id,
				record_type=r_type,
				check_date=check_date,
				inspector=random.choice(inspectors),
				result=random.choice(results),
				notes=f"Ghi chú kiểm tra ngày {check_date.strftime('%d/%m')}: Tình trạng đàn ổn định."
			)
			db.session.add(record)
	db.session.commit()
	print("    [OK] Đã tạo lịch sử kiểm tra sức khỏe")


# =============================================================================
# SEED DỮ LIỆU NHẬT KÝ KHO
# =============================================================================

def seed_inventory_logs():
	"""Tạo nhật ký kho mẫu."""
	print("  Đang tạo nhật ký kho...")
	items = WarehouseInventory.query.all()
	suppliers = ['Công ty CP', 'GreenFeed', 'De Heus', 'Dabaco']
	for item in items:
		# Tạo 3-5 log cho mỗi mặt hàng
		for i in range(random.randint(3, 5)):
			transaction_date = datetime.now() - timedelta(days=random.randint(1, 30))
			t_type = random.choice(['import', 'export', 'adjustment'])
			qty = random.uniform(50, 200)
			if t_type == 'export': qty = -qty
			
			log = InventoryLog(
				item_id=item.id,
				transaction_type=t_type,
				quantity=qty,
				unit_price=random.uniform(10000, 20000) if t_type == 'import' else None,
				supplier=random.choice(suppliers) if t_type == 'import' else None,
				transaction_date=transaction_date,
				notes=f"Giao dịch mẫu cho {item.item_name}"
			)
			db.session.add(log)
	db.session.commit()
	print("    [OK] Đã tạo nhật ký kho")


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
	for coop in coops:
		for _ in range(3):
			template = random.choice(alert_templates)
			alert = Alert(
				coop_id=coop.id,
				type=template['type'],
				level=template['level'],
				message=f"{coop.name}: {template['message']}",
				is_resolved=random.choice([True, False])  # Ngẫu nhiên đã xử lý hoặc chưa
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
	"""
	print("\n[1] Đang xóa dữ liệu cũ...")
	
	# Xóa theo thứ tự để tránh vi phạm ràng buộc khóa ngoài
	print("    Xóa HealthRecord...")
	HealthRecord.query.delete()

	print("    Xóa VaccinationRecord...")
	VaccinationRecord.query.delete()
	
	print("    Xóa ChickenBatch...")
	ChickenBatch.query.delete()
	
	print("    Xóa InventoryLog...")
	InventoryLog.query.delete()

	print("    Xóa VideoRecording...")
	VideoRecording.query.delete()

	print("    Xóa FeedConsumption...")
	FeedConsumption.query.delete()

	print("    Xóa MedicineConsumption...")
	MedicineConsumption.query.delete()

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

	print("    Xóa UnconnectedDevice...")
	UnconnectedDevice.query.delete()
	
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

		# Bước 7: Seed Video Recordings
		print("\n[6.1] Seed Video Recordings...")
		seed_video_recordings(coops, devices)

		# Bước 7.1: Seed Unconnected Devices
		print("\n[7.1] Seed Unconnected Devices...")
		seed_unconnected_devices()

		# Bước 7.2: Seed Warehouse
		print("\n[7.2] Seed Warehouse...")
		seed_warehouse()

		# Bước 7.3: Seed FeedConsumption
		print("\n[7.3] Seed FeedConsumption...")
		seed_feed_consumption(coops)

		# Bước 7.4: Seed MedicineConsumption
		print("\n[7.4] Seed MedicineConsumption...")
		seed_medicine_consumption(coops)

		# Bước 7.5: Seed Chicken Batches & Vaccinations
		print("\n[7.5] Seed Chicken Batches & Vaccinations...")
		batches = seed_chicken_batches(coops)
		seed_vaccinations(batches)
		seed_health_records(batches)

		# Bước 7.6: Seed Inventory Logs
		print("\n[7.6] Seed Inventory Logs...")
		seed_inventory_logs()

		# Bước 8: Seed Alerts
		print("\n[8] Seed Alerts...")
		seed_alerts(coops)

		# In thống kê
		print("\n" + "=" * 60)
		print("  THỐNG KÊ DỮ LIỆU SAU KHI SEED")
		print("=" * 60)
		print(f"  Users:               {User.query.count()}")
		print(f"  Coops:               {Coop.query.count()}")
		print(f"  Devices:             {Device.query.count()}")
		print(f"  CoopDevices:         {CoopDevice.query.count()}")
		print(f"  Environments:        {Environment.query.count()}")
		print(f"  FeedSchedules:       {FeedSchedule.query.count()}")
		print(f"  VideoRecordings:     {VideoRecording.query.count()}")
		print(f"  WarehouseInventory:  {WarehouseInventory.query.count()}")
		print(f"  InventoryLogs:       {InventoryLog.query.count()}")
		print(f"  ChickenBatches:      {ChickenBatch.query.count()}")
		print(f"  VaccinationRecords:  {VaccinationRecord.query.count()}")
		print(f"  HealthRecords:       {HealthRecord.query.count()}")
		print(f"  FeedConsumption:     {FeedConsumption.query.count()}")
		print(f"  MedicineConsumption: {MedicineConsumption.query.count()}")
		print(f"  Alerts:              {Alert.query.count()}")
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