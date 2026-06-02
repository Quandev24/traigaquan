"""
Database Models cho Hệ thống Quản lý Trang trại Gà

Sử dụng Flask-SQLAlchemy với SQLite.
Định nghĩa các models và relationships.
"""

from datetime import datetime, UTC
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """
    Model người dùng hệ thống.
    
    Attributes:
        id: Primary key tự tăng
        username: Tên đăng nhập (unique)
        email: Email (unique)
        password_hash: Mật khẩu đã băm
        full_name: Họ tên đầy đủ
        role: Vai trò (admin/worker)
        created_at: Thời gian tạo tài khoản
        updated_at: Thời gian cập nhật cuối
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(20), default='worker')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        """Băm mật khẩu và lưu vào password_hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Kiểm tra mật khẩu."""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self): #cung cấp thông tin chi tiết hơn cho lập trình viên, hữu ích khi debug
        return f'<User {self.username}>'


class Coop(db.Model):
    """
    Model chuồng gà.
    
    Attributes:
        id: Primary key tự tăng
        name: Tên chuồng (VD: Chuồng A, Chuồng B)
        location: Vị trí chuồng
        capacity: Sức chứa tối đa (số gà)
        current_count: Số lượng gà hiện tại
        area: Diện tích chuồng (m²)
        
        Ngưỡng cảnh báo:
        temp_min, temp_max: Nhiệt độ (°C)
        humidity_min, humidity_max: Độ ẩm (%)
        feed_threshold: Ngưỡng thức ăn (%)
        water_threshold: Ngưỡng nước (%)
        
        Lịch trình cho ăn:
        feed_time_1, feed_time_2, feed_time_3: Giờ cho ăn
        
        Chế độ tự động:
        auto_fan: Tự động bật quạt
        auto_light: Tự động bật đèn
        auto_feed: Tự động cho ăn
        auto_water: Tự động cấp nước
        
        Trạng thái:
        emergency_alert: Bật cảnh báo khẩn cấp
        status: Trạng thái chuồng (active/cleaning/empty)
    """
    __tablename__ = 'coops'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100))
    capacity = db.Column(db.Integer, default=500)
    current_count = db.Column(db.Integer, default=0)
    area = db.Column(db.Float, default=50.0)
    
    temp_min = db.Column(db.Float, default=18.0)
    temp_max = db.Column(db.Float, default=28.0)
    humidity_min = db.Column(db.Float, default=40.0)
    humidity_max = db.Column(db.Float, default=70.0)
    feed_threshold = db.Column(db.Float, default=20.0)
    water_threshold = db.Column(db.Float, default=20.0)
    
    feed_time_1 = db.Column(db.Time, default=datetime.strptime('06:00', '%H:%M').time())
    feed_time_2 = db.Column(db.Time, default=datetime.strptime('12:00', '%H:%M').time())
    feed_time_3 = db.Column(db.Time, default=datetime.strptime('18:00', '%H:%M').time())
    
    auto_fan = db.Column(db.Boolean, default=True)
    auto_light = db.Column(db.Boolean, default=True)
    auto_feed = db.Column(db.Boolean, default=True)
    auto_water = db.Column(db.Boolean, default=True)
    
    emergency_alert = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    has_camera = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    devices = db.relationship('Device', secondary='coop_devices', back_populates='coops')
    environments = db.relationship('Environment', backref='coop', lazy='dynamic')
    feed_schedules = db.relationship('FeedSchedule', backref='coop', lazy='dynamic')
    alerts = db.relationship('Alert', backref='coop', lazy='dynamic')
    
    def to_dict(self, include_environment=False):
        """Chuyển đổi thành dictionary cho JSON response.
        
        Args:
            include_environment (bool): Có bao gồm dữ liệu môi trường mới nhất không
        """
        result = {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'capacity': self.capacity,
            'current_count': self.current_count,
            'area': self.area,
            'temp_min': self.temp_min,
            'temp_max': self.temp_max,
            'humidity_min': self.humidity_min,
            'humidity_max': self.humidity_max,
            'feed_threshold': self.feed_threshold,
            'water_threshold': self.water_threshold,
            'feed_time_1': self.feed_time_1.isoformat() if self.feed_time_1 else None,
            'feed_time_2': self.feed_time_2.isoformat() if self.feed_time_2 else None,
            'feed_time_3': self.feed_time_3.isoformat() if self.feed_time_3 else None,
            'auto_fan': self.auto_fan,
            'auto_light': self.auto_light,
            'auto_feed': self.auto_feed,
            'auto_water': self.auto_water,
            'emergency_alert': self.emergency_alert,
            'status': self.status,
            'has_camera': self.has_camera,
            'deleted': self.deleted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_environment:
            latest_env = Environment.query.filter_by(coop_id=self.id).order_by(Environment.recorded_at.desc()).first()
            if latest_env:
                result['environment'] = {
                    'temperature': latest_env.temperature,
                    'humidity': latest_env.humidity,
                    'feed_level': latest_env.feed_level,
                    'water_level': latest_env.water_level,
                    'recorded_at': latest_env.recorded_at.isoformat() if latest_env.recorded_at else None
                }
            else:
                result['environment'] = None
        
        return result
    
    def __repr__(self):
        return f'<Coop {self.name}>'


class Device(db.Model):
    """
    Model thiết bị IoT.
    
    Attributes:
        id: Primary key tự tăng
        name: Tên thiết bị
        type: Loại thiết bị
            - temperature: Cảm biến nhiệt độ
            - humidity: Cảm biến độ ẩm
            - fan: Quạt thông gió
            - light: Đèn chiếu sáng
            - feeder: Máy cho ăn
            - camera: Camera giám sát
        mac_address: Địa chỉ MAC (unique)
        status: Trạng thái kết nối (online/offline/connecting)
        is_active: Thiết bị đang bật/tắt
        battery: Mức pin (%)
        created_at: Thời gian thêm thiết bị
    """
    __tablename__ = 'devices'
    
    DEVICE_TYPES = [
        'temperature',
        'humidity',
        'fan',
        'light',
        'feeder',
        'water',
        'camera'
    ]
    
    DEVICE_STATUS = [
        'online',
        'offline',
        'connecting',
        'pending'
    ]
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    mac_address = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), default='offline')
    is_active = db.Column(db.Boolean, default=False)
    battery = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    coops = db.relationship('Coop', secondary='coop_devices', back_populates='devices')
    alerts = db.relationship('Alert', backref='device', lazy='dynamic')
    
    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'mac_address': self.mac_address,
            'status': self.status,
            'is_active': self.is_active,
            'battery': self.battery,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'coop_id': self.coops[0].id if self.coops else None
        }
    
    def __repr__(self):
        return f'<Device {self.name}>'


class CoopDevice(db.Model):
    """
    Model bảng trung gian cho quan hệ Many-to-Many giữa Coop và Device.
    
    Thiết lập quan hệ Nhiều-Coop-Nhiều-Device.
    Một thiết bị có thể được gán vào nhiều chuồng.
    Một chuồng có thể có nhiều thiết bị.
    
    Attributes:
        id: Primary key tự tăng
        coop_id: Foreign key đến Coop
        device_id: Foreign key đến Device
        is_active: Thiết bị có đang hoạt động trong chuồng này không
    """
    __tablename__ = 'coop_devices'
    
    id = db.Column(db.Integer, primary_key=True)
    coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'coop_id': self.coop_id,
            'device_id': self.device_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<CoopDevice coop={self.coop_id} device={self.device_id}>'


class Environment(db.Model):
    """
    Model dữ liệu môi trường chuồng.
    
    Lưu trữ dữ liệu cảm biến theo thời gian.
    Mỗi bản ghi represents một lần đo.
    
    Attributes:
        id: Primary key tự tăng
        coop_id: Foreign key đến Coop
        temperature: Nhiệt độ (°C)
        humidity: Độ ẩm (%)
        feed_level: Mức thức ăn (%)
        water_level: Mức nước (%)
        recorded_at: Thời gian ghi nhận
    """
    __tablename__ = 'environments'
    
    id = db.Column(db.Integer, primary_key=True)
    coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'), nullable=False)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    feed_level = db.Column(db.Float)
    water_level = db.Column(db.Float)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'coop_id': self.coop_id,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'feed_level': self.feed_level,
            'water_level': self.water_level,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }
    
    def __repr__(self):
        return f'<Environment coop={self.coop_id} time={self.recorded_at}>'


class FeedSchedule(db.Model):
    """
    Model lịch cho ăn tự động.
    
    Lưu trữ lịch trình cho ăn tự động cho mỗi chuồng.
    Một chuồng có thể có nhiều lịch cho ăn.
    
    Attributes:
        id: Primary key tự tăng
        coop_id: Foreign key đến Coop
        time: Giờ cho ăn
        amount: Lượng thức ăn (kg)
        enabled: Bật/tắt lịch cho ăn
    """
    __tablename__ = 'feed_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'), nullable=False)
    time = db.Column(db.Time, nullable=False)
    amount = db.Column(db.Float, default=10.0)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'coop_id': self.coop_id,
            'time': self.time.isoformat() if self.time else None,
            'amount': self.amount,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<FeedSchedule coop={self.coop_id} time={self.time}>'


class Alert(db.Model):
    """
    Model cảnh báo hệ thống.
    
    Lưu trữ các cảnh báo về nhiệt độ, độ ẩm, thiết bị...
    
    Attributes:
        id: Primary key tự tăng
        coop_id: Foreign key đến Coop (nullable vì có thể cảnh báo chung)
        device_id: Foreign key đến Device (optional)
        type: Loại cảnh báo (temperature/humidity/feed/water/device)
        level: Mức độ
            - info: Thông tin
            - warning: Cảnh báo
            - critical: Nghiêm trọng
        message: Nội dung cảnh báo
        is_resolved: Đã xử lý chưa
        created_at: Thời gian tạo cảnh báo
    """
    __tablename__ = 'alerts'
    
    ALERT_TYPES = [
        'temperature',
        'humidity',
        'feed',
        'water',
        'device'
    ]
    
    ALERT_LEVELS = [
        'info',
        'warning',
        'critical'
    ]
    
    id = db.Column(db.Integer, primary_key=True)
    coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'), nullable=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=True)
    type = db.Column(db.String(20), nullable=False)
    level = db.Column(db.String(20), default='info')
    message = db.Column(db.Text, nullable=False)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    resolved_at = db.Column(db.DateTime)
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'coop_id': self.coop_id,
            'device_id': self.device_id,
            'type': self.type,
            'level': self.level,
            'message': self.message,
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
    
    def __repr__(self):
        return f'<Alert {self.level}:{self.type}>'


class UnconnectedDevice(db.Model):
    """
    Model thiết bị chưa kết nối (unconnected devices).

    Lưu trữ các thiết bị chưa được gán vào bất kỳ chuồng nào.
    Khi thêm thiết bị vào chuồng, bản ghi này sẽ bị xóa.
    Khi gỡ thiết bị khỏi chuồng, bản ghi mới sẽ được tạo.

    Attributes:
        id: Primary key tự tăng
        name: Tên thiết bị
        type: Loại thiết bị (temperature/humidity/fan/light/feeder/camera)
        mac_address: Địa chỉ MAC
        status: Trạng thái (online/offline/connecting)
        is_active: Bật/tắt thiết bị
        battery: Mức pin (%)
        device_id: FK đến thiết bị gốc trong bảng devices
        previous_coop_id: FK đến chuồng trước đó
        unconnected_at: Thời gian ngắt kết nối
        created_at: Thời gian thêm vào danh sách
    """
    __tablename__ = 'unconnected_devices'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    type = db.Column(db.String(20), nullable=False)
    mac_address = db.Column(db.String(50))
    status = db.Column(db.String(20), default='offline')
    is_active = db.Column(db.Boolean, default=False)
    battery = db.Column(db.Integer, default=100)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    previous_coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'))
    unconnected_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Chuyển đổi thành dictionary cho JSON response."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'mac_address': self.mac_address,
            'status': self.status,
            'is_active': self.is_active,
            'battery': self.battery,
            'device_id': self.device_id,
            'previous_coop_id': self.previous_coop_id,
            'unconnected_at': self.unconnected_at.isoformat() if self.unconnected_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<UnconnectedDevice {self.name}>'


class VideoRecording(db.Model):
    __tablename__ = 'video_recordings'

    SOURCE_TYPES = ['text', 'video_url', 'file_path']

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(20), nullable=False)
    source_value = db.Column(db.Text, nullable=False)
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.Float)
    file_size = db.Column(db.Integer)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    device = db.relationship('Device', backref='video_recordings', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'coop_id': self.coop_id,
            'name': self.name,
            'source_type': self.source_type,
            'source_value': self.source_value,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'file_size': self.file_size,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<VideoRecording {self.name} ({self.source_type})>'


class WarehouseInventory(db.Model):
    __tablename__ = 'warehouse_inventory'

    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    item_type = db.Column(db.String(50), default='feed')
    quantity_kg = db.Column(db.Float, default=0)
    min_threshold_kg = db.Column(db.Float, default=0)
    unit = db.Column(db.String(20), default='kg')
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item_name,
            'item_type': self.item_type,
            'quantity_kg': self.quantity_kg,
            'min_threshold_kg': self.min_threshold_kg,
            'unit': self.unit,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<WarehouseInventory {self.item_name}>'


class FeedConsumption(db.Model):
    __tablename__ = 'feed_consumption'

    id = db.Column(db.Integer, primary_key=True)
    coop_id = db.Column(db.Integer, db.ForeignKey('coops.id'), nullable=False)
    recorded_date = db.Column(db.Date, nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint('coop_id', 'recorded_date'),)
    coop = db.relationship('Coop', backref=db.backref('feed_consumptions', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'coop_id': self.coop_id,
            'recorded_date': self.recorded_date.isoformat(),
            'quantity_kg': self.quantity_kg,
        }