# AutomatedChickenFarmManagement

## 1. Tổng quan Dự án

**Mục tiêu:** Hệ thống quản lý trang trại gà thông minh sử dụng tự động hóa và giám sát dựa trên dữ liệu để tối ưu hóa hiệu quả chăn nuôi và sức khỏe gà.

**Trạng thái phát triển:**
- Frontend: ✓ Hoàn tất đầy đủ chức năng quản lý
- Backend: ✓ API đầy đủ, database models hoàn tất, WebSocket real-time

---

## 2. Cấu trúc Dự án

```
AutomatedChickenFarmManagement/
├── static/                      # Frontend (SB Admin 2 theme)
│   ├── index.html               # Dashboard chính
│   ├── coop-list.html           # Danh sách chuồng
│   ├── coop-detail.html         # Chi tiết chuồng
│   ├── device-list.html          # Danh sách thiết bị
│   ├── device-detail.html        # Chi tiết thiết bị
│   ├── camera.html              # Danh sách camera
│   ├── camera-detail.html       # Chi tiết camera
│   ├── other.html               # Chức năng khác
│   └── css/js/vendor/img/       # Tài nguyên frontend
├── backend/                     # Flask Backend API
│   ├── app.py                   # Entry point
│   ├── models.py                # Database models (7 tables)
│   ├── config.py                # Cấu hình hệ thống
│   ├── requirements.txt         # Python dependencies
│   └── api/routes/              # API Endpoints
│       ├── auth.py              # Authentication
│       ├── coops.py              # Coop CRUD
│       ├── devices.py           # Device management
│       ├── dashboard.py         # Dashboard & stats
│       ├── camera.py            # Camera control
│       ├── feed_schedule.py     # Lịch cho ăn
│       ├── environment.py       # Dữ liệu môi trường
│       └── alerts.py            # Quản lý cảnh báo
├── README.md                    # Tài liệu chính
└── .gitignore
```

---

## 3. Cấu trúc Backend & Database

### Thư mục Backend
```
backend/
├── config.py              # Cấu hình (Development/Production/Testing)
├── models.py              # Database Models (Flask-SQLAlchemy)
├── requirements.txt       # Python dependencies
├── app.py                 # Flask entry point
└── api/
    ├── __init__.py       # API Blueprint Factory
    └── routes/           # API endpoints
```

### Database Schema

| Table | Mô tả | Relationships |
|-------|-------|---------------|
| `users` | Người dùng hệ thống | 1-N → alerts |
| `coops` | Chuồng gà | 1-N → environments, feed_schedules, alerts; N-N ← devices |
| `devices` | Thiết bị IoT | 1-N → alerts; N-N ← coops |
| `coop_devices` | Bảng trung gian N-N | - |
| `environments` | Dữ liệu môi trường | N-1 → coops |
| `feed_schedules` | Lịch cho ăn | N-1 → coops |
| `alerts` | Cảnh báo | N-1 → coops, devices |
| `unconnected_devices` | Thiết bị chưa kết nối | FK → devices, coops |

### ERD Sơ Đồ

       +-------------------+             +-----------------------+
       |       USER        |             |         ALERT         |
       +-------------------+             +-----------------------+
       | id (PK)           |             | id (PK)               |
       | username          |             | level (info/warn/crit)|
       | email             |             | message               |
       | password_hash     |             | is_resolved (bool)    |
       | role (admin/worker)             | resolved_at           |
       | full_name         |       +---->| coop_id (FK)          |
       | created_at        |       |     | device_id (FK)        |
       +-------------------+       |     +-----------------------+
                                   |
                                   |             
       +-------------------+       |     +-----------------------+
       |       COOP        |-------+     |      ENVIRONMENT      |
       +-------------------+             +-----------------------+
       | id (PK)           |             | id (PK)               |
       | name              |             | temperature           |
       | location          |             | humidity              |
       | capacity          |       +---->| feed_level            |
       | current_count     |       |     | water_level           |
       | status            |       |     | recorded_at           |
       | [Thresholds...]   |       |     | coop_id (FK)          |
       +---------+---------+       |     +-----------------------+
                 |                 |
                 | (1)             | (1)
                 |                 |
                 | (n)             | (n)
       +---------+---------+       |     +-----------------------+
       |    COOP_DEVICE    |-------+     |        DEVICE         |
       +-------------------+             +-----------------------+
       | id (PK)           |             | id (PK)               |
       | coop_id (FK)      |------------>| name                  |
       | device_id (FK)    |        (1)  | type (camera/sensor..)|
       +-------------------+             | status                |
                                         | mac_address           |
                                         | is_active (bool)      |
                                         +-----------------------+

### Relationships Summary

```
USERS ──────────────► ALERTS
   │                    ▲
   │                    │
   ▼                    │
COOPS ◄───────────────► DEVICES
   │                    │
   ├──► ENVIRONMENTS     │
   │                    │
   ├──► FEED_SCHEDULES  │
   │                    │
   └─► COOP_DEVICES ◄───┘
   │
   └─► UNCONNECTED_DEVICES ◄── DEVICES (FK reference)
```

### Mermaid ERD Diagram

```mermaid
erDiagram
    USERS ||--o{ ALERTS : creates
    COOPS ||--o{ ALERTS : generates
    DEVICES ||--o{ ALERTS : triggers
    COOPS }o--o{ DEVICES : monitors
    
    DEVICES }o--o{ UNCONNECTED_DEVICES : "moved to when coop deleted"
    COOPS }o--o{ UNCONNECTED_DEVICES : "previous coop reference"
    
    COOPS {
        int id PK
        string name
        string location
        int capacity
        int current_count
        float area
        float temp_min
        float temp_max
        float humidity_min
        float humidity_max
        float feed_threshold
        float water_threshold
        time feed_time_1
        time feed_time_2
        time feed_time_3
        bool auto_fan
        bool auto_light
        bool auto_feed
        bool auto_water
        bool emergency_alert
        string status
        datetime created_at
        datetime updated_at
    }
    
    DEVICES {
        int id PK
        string name
        string type
        string mac_address UK
        string status
        bool is_active
        int battery
        datetime created_at
        datetime updated_at
    }
    
    COOP_DEVICES {
        int id PK
        int coop_id FK
        int device_id FK
        datetime created_at
        bool deleted
    }
    
    UNCONNECTED_DEVICES {
        int id PK
        string name
        string type
        string mac_address
        string status
        bool is_active
        int battery
        int device_id FK
        int previous_coop_id FK
        datetime unconnected_at
        datetime created_at
        bool deleted
    }
    
    ENVIRONMENTS {
        int id PK
        int coop_id FK
        float temperature
        float humidity
        float feed_level
        float water_level
        datetime recorded_at
    }
    
    FEED_SCHEDULES {
        int id PK
        int coop_id FK
        time time
        float amount
        bool enabled
        datetime created_at
    }
    
    ALERTS {
        int id PK
        int coop_id FK
        int device_id FK
        string type
        string level
        string message
        bool is_resolved
        datetime created_at
        datetime resolved_at
    }
    
    USERS {
        int id PK
        string username UK
        string email UK
        string password_hash
        string full_name
        string role
        datetime created_at
        datetime updated_at
    }
    
    COOPS ||--o{ ENVIRONMENTS : records
    COOPS ||--o{ FEED_SCHEDULES : has
    COOPS ||--o{ UNCONNECTED_DEVICES : "devices moved here on delete"
    DEVICES ||--o{ UNCONNECTED_DEVICES : "references original device"
```

### Chi tiết Tables (bao gồm cột deleted cho soft delete)

```
users:          id, username, email, password_hash, full_name, role, created_at, updated_at, deleted
coops:          id, name, location, capacity, current_count, area,
                 temp_min, temp_max, humidity_min, humidity_max,
                 feed_threshold, water_threshold,
                 feed_time_1, feed_time_2, feed_time_3,
                 auto_fan, auto_light, auto_feed, auto_water,
                 emergency_alert, status, created_at, updated_at, deleted
devices:        id, name, type, mac_address, status, is_active, battery, created_at, updated_at, deleted
coop_devices:   id, coop_id, device_id, is_active, created_at, deleted
environments:   id, coop_id, temperature, humidity, feed_level, water_level, recorded_at, deleted
feed_schedules: id, coop_id, time, amount, enabled, created_at, deleted
alerts:         id, coop_id, device_id, type, level, message, is_resolved, created_at, resolved_at, deleted
unconnected_devices: id, name, type, mac_address, status, is_active, battery, device_id (FK→devices), previous_coop_id (FK→coops), unconnected_at, created_at, deleted
```

**Chú thích:** Tất cả bảng có thêm cột `deleted` (Boolean, default=False) để hỗ trợ soft delete - khi xóa chỉ đánh dấu deleted=1 thay vì xóa vĩnh viễn khỏi database. Bảng `unconnected_devices` có thêm các cột `device_id`, `previous_coop_id`, `unconnected_at` để theo dõi thiết bị sau khi chuồng bị xóa.

---

## 4. API Endpoints

| Nhóm | Method | Endpoint | Mô tả |
|------|--------|----------|-------|
| **Auth** | POST | `/api/auth/login` | Đăng nhập, nhận JWT token |
| | POST | `/api/auth/register` | Đăng ký user mới |
| | GET | `/api/auth/me` | Lấy thông tin user hiện tại |
| | POST | `/api/auth/logout` | Đăng xuất |
| **Coops** | GET | `/api/coops` | Danh sách chuồng |
| | POST | `/api/coops` | Tạo chuồng mới |
| | GET | `/api/coops/<id>` | Chi tiết chuồng |
| | PUT | `/api/coops/<id>` | Cập nhật chuồng |
| | DELETE | `/api/coops/<id>` | Soft delete chuồng + chuyển thiết bị sang unconnected |
| | GET | `/api/coops/<id>/devices` | Thiết bị trong chuồng |
| | GET | `/api/coops/<id>/environment` | Dữ liệu môi trường hiện tại |
| | GET | `/api/coops/<id>/history` | Lịch sử dữ liệu |
| **Devices** | GET | `/api/devices` | Danh sách thiết bị |
| | POST | `/api/devices` | Tạo thiết bị mới |
| | POST | `/api/devices/connect` | Kết nối thiết bị (QR/mã) |
| | GET | `/api/devices/<id>` | Chi tiết thiết bị |
| | PUT | `/api/devices/<id>` | Cập nhật thiết bị |
| | DELETE | `/api/devices/<id>` | Xóa thiết bị |
| | POST | `/api/devices/<id>/toggle` | Bật/tắt thiết bị |
| | POST | `/api/devices/<id>/assign` | Gán thiết bị vào chuồng |
| | PATCH | `/api/devices/<id>/name` | Đặt tên thiết bị |
| **Dashboard** | GET | `/api/dashboard` | Tổng quan dashboard |
| | GET | `/api/dashboard/stats` | Thống kê chi tiết |
| | GET | `/api/dashboard/alerts` | Danh sách cảnh báo |
| | GET | `/api/dashboard/alerts-count` | Đếm cảnh báo (offline + môi trường) |
| | GET | `/api/dashboard/recent-activities` | Hoạt động gần đây |
| **Camera** | GET | `/api/camera` | Danh sách camera |
| | GET | `/api/camera/<id>` | Chi tiết camera |
| | GET | `/api/camera/coop/<id>` | Camera theo chuồng |
| | GET | `/api/camera/coop-detail/<id>` | Tổng hợp dữ liệu chuồng (coop + environment + devices) |
| | POST | `/api/camera/<id>/snapshot` | Chụp ảnh |
| | GET | `/api/camera/<id>/stream` | Lấy URL stream |
| | GET | `/api/camera/<id>/recordings` | Danh sách recordings |
| **Feed Schedule** | GET | `/api/feed-schedule` | Danh sách lịch cho ăn |
| | POST | `/api/feed-schedule` | Tạo lịch mới |
| | PUT | `/api/feed-schedule/<id>` | Cập nhật lịch |
| | DELETE | `/api/feed-schedule/<id>` | Xóa lịch |
| **Environment** | POST | `/api/environment` | Nhận dữ liệu từ IoT |
| | GET | `/api/environment/<coop_id>` | Dữ liệu môi trường hiện tại |
| | GET | `/api/environment/<coop_id>/history` | Lịch sử dữ liệu môi trường |
| **Alerts** | GET | `/api/alerts` | Danh sách cảnh báo |
| | PUT | `/api/alerts/<id>/resolve` | Đánh dấu đã xử lý |

---

## 5. Cập nhật gần đây (May 2026)

### May 7, 2026 - Đồng bộ Dashboard & Tích hợp Camera Toàn diện

| Thay đổi | File | Chi tiết |
|----------|------|----------|
| Đồng bộ Dashboard | `backend/api/routes/dashboard.py` | Cập nhật tất cả các endpoint thống kê (Total Coops, Devices, Alerts, Activities) để lọc bỏ dữ liệu đã xóa mềm (`deleted=False`). |
| Dashboard Dynamic | `static/index.html` | Thêm ID `totalCoopsDisplay`, `donutTotalDisplay`, xóa giá trị tĩnh "5", "15" để cập nhật dữ liệu thực tế từ API. |
| Tích hợp Camera Seeding | `backend/seed.py` | Tất cả 5 chuồng mặc định đều có `has_camera=1` và được gán 1 thiết bị camera. Thêm các mẫu camera AI/Hồng ngoại vào danh sách chưa kết nối. |
| API Device Type | `backend/api/routes/devices.py` | Bổ sung trường `type` vào endpoint `/api/devices/public/recent` để frontend nhận diện icon. |
| Icon thiết bị động | `static/device-list.html` | Hiển thị icon tương ứng cho từng loại thiết bị (`fa-video` cho camera, `fa-thermometer-half` cho cảm biến nhiệt, v.v.) thay vì dùng chung icon wifi. |
| Tối ưu UI Camera | `static/camera.html` | Loại bỏ các nút "Xem camera" dư thừa trong danh sách tóm tắt chuồng để giao diện gọn gàng hơn. |

### May 6, 2026 - Camera Detail API + Soft Delete Chuồng với Device Migration

| Thay đổi | File | Chi tiết |
|----------|------|----------|
| API camera-detail mới | `backend/api/routes/camera.py` | Endpoint `GET /api/camera/coop-detail/<id>` trả về coop info + environment mới nhất + danh sách thiết bị đang hoạt động |
| Camera-detail dynamic | `static/camera-detail.html` | Xóa toàn bộ dữ liệu tĩnh `coopData`, thay bằng gọi API, skeleton loading, polling 30s, color-coded device status (online=xanh, connecting=vàng, offline=đỏ) |
| Camera links dùng ID | `static/camera.html` | Cập nhật tất cả link từ `?coop=A` → `?coop=<numeric_id>`, render camera cards từ API |
| Soft delete chuồng | `backend/api/routes/coops.py` | Endpoint DELETE: soft delete coop + tạo unconnected_devices + cập nhật device status=pending/is_active=False + soft delete coop_device links, tất cả trong transaction |
| UnconnectedDevice schema | `backend/models.py` | Thêm 3 cột mới: `device_id`, `previous_coop_id`, `unconnected_at` |
| Auto-migration | `backend/app.py` | Tự động `ALTER TABLE ADD COLUMN` cho các cột mới khi startup |
| Delete confirmation | `static/coop-list.html` | Modal xác nhận xóa với icon, tên chuồng, loading state, fade-out card, toast notification |

### May 6, 2026 - Cập nhật Backend Soft Delete

| Thay đổi | File | Chi tiết |
|----------|------|----------|
| Thêm cột deleted | `backend/models.py` | Thêm `deleted = db.Column(db.Boolean, default=False)` vào 8 models |
| Cập nhật DELETE queries | `backend/api/routes/devices.py` | Thay `db.session.delete()` → `deleted = True` |
| Cập nhật SELECT queries | `backend/api/routes/*.py` | Thêm `.filter(Model.deleted == False)` vào tất cả queries |
| API cảnh báo mới | `backend/api/routes/dashboard.py` | Thêm `/api/dashboard/alerts-count` |

**Models đã thêm cột deleted:** User, Coop, Device, CoopDevice, Environment, FeedSchedule, Alert, UnconnectedDevice

### May 5, 2026 - Cập nhật Index Page

| Thay đổi | File | Chi tiết |
|----------|------|----------|
| Dynamic statistics | `static/index.html` | Tổng chuồng, tổng thiết bị, thiết bị online được tính từ database |
| Loading states | `static/index.html` | Hiển thị "..." khi đang tải dữ liệu |
| Auto-refresh | `static/index.html` | Cập nhật dữ liệu mỗi 30 giây |
| Remove search | `static/index.html` | Xóa nút tìm kiếm trên topbar |
| Alert card | `static/index.html` | Viền tô vàng khi có cảnh báo |

### May 4, 2026 - Cập nhật Device List

| Thay đổi | File | Chi tiết |
|----------|------|----------|
| Toggle button | `static/device-list.html` | Hiển thị "Bật"/"Tắt" theo is_active |
| Thông tin button | `static/device-list.html` | Chỉ hiển thị cho thiết bị online/offline |
| Delete confirmation | `static/device-list.html` | Xác nhận bằng mã 4 ký tự ngẫu nhiên |
| Sort by status | `static/device-list.html` | Sắp xếp offline → connecting → online |
| Hide toggle | `static/device-list.html` | Ẩn nút toggle cho offline/connecting |
| Status badge | `static/device-list.html` | Fix CSS cho các trạng thái |

### May 2, 2026 - Bổ sung API mới

| API | File | Endpoints |
|-----|------|-----------|
| Feed Schedule | `backend/api/routes/feed_schedule.py` | GET, POST, PUT, DELETE |
| Environment | `backend/api/routes/environment.py` | POST (IoT data), GET current, GET history |
| Alerts | `backend/api/routes/alerts.py` | GET list, PUT resolve |

### May 1, 2026 - Tối ưu Dashboard API

- Chuyển các phép tính thống kê (count, sum) xuống cấp độ Database
- Sử dụng `SQLAlchemy func` thay vì Python list comprehension
- Kết quả: Tăng hiệu suất truy vấn

```python
# Trước: sum(c.current_count for c in coops)
# Sau: db.session.query(func.sum(Coop.current_count)).scalar()
```

---

## 6. Tech Stack & Setup

### Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Bootstrap 4.6.0, jQuery 3.6.0, Chart.js 3.x, Font Awesome 6.0 |
| Backend | Python 3.x, Flask, Flask-SQLAlchemy, Flask-SocketIO |
| Database | SQLite (Development) |
| Auth | JWT (flask-jwt-extended) |
| IoT | REST API, QR Code / Manual code connection |
| Real-time | WebSocket (SocketIO) với REST polling fallback |

### Setup - Frontend Only

```bash
# Mở trực tiếp trong trình duyệt
static/index.html

# Hoặc chạy local server
python -m http.server 8000 --directory static
```

### Setup - Full (Backend + Frontend)

```bash
# 1. Di chuyển vào thư mục backend
cd backend

# 2. Tạo virtual environment
python -m venv venv

# 3. Kích hoạt virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Cài đặt dependencies
pip install -r requirements.txt

# 5. Chạy server
python app.py
# Hoặc
flask run

# 6. Truy cập
# Frontend: http://localhost:5000
# API: http://localhost:5000/api/
```

### API Test Example

```bash
# Đăng nhập
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Lấy dashboard stats (cần token)
curl -X GET http://localhost:5000/api/dashboard/stats \
  -H "Authorization: Bearer <token>"
```

---

## 7. Features Planned

### Đã hoàn thành ✓

- [x] Tổng quan trang trại (Dashboard)
- [x] Số lượng gà hiện tại
- [x] Giám sát môi trường (nhiệt độ, độ ẩm)
- [x] Biểu đồ thống kê (Donut Chart, Area Chart)
- [x] Trạng thái thiết bị IoT
- [x] Quản lý chuồng (CRUD)
- [x] Quản lý thiết bị (CRUD, toggle, assign)
- [x] Lịch cho ăn tự động
- [x] Điều khiển tự động (quạt, đèn, cho ăn, nước)
- [x] Cảnh báo nhiệt độ
- [x] Theo dõi camera
- [x] Giao diện Mobile (Fixed Bottom Navigation)
- [x] Responsive design
- [x] **Soft Delete** - Xóa không mất dữ liệu (thêm cột deleted vào tất cả bảng)
- [x] **Xóa chuồng với device migration** - Soft delete + chuyển thiết bị sang unconnected_devices trong transaction
- [x] **Xác nhận xóa thiết bị** - Mã 4 ký tự ngẫu nhiên
- [x] **Sắp xếp thiết bị** - Ưu tiên offline → connecting → online
- [x] **Thông tin thiết bị** - Modal hiển thị chi tiết và chỉnh sửa tên
- [x] **Cảnh báo động** - Tính từ database, viền vàng khi có cảnh báo
- [x] **Tự động làm mới** - Cập nhật dữ liệu mỗi 30 giây
- [x] **Camera detail dynamic** - API tổng hợp, skeleton loading, realtime polling 30s, color-coded device status

### Chưa hoàn thành

- [ ] Thêm/xóa/sửa thông tin gà (Chicken management)
- [ ] Theo dõi tuổi, giống, cân nặng gà
- [ ] Ghi chép tiêm phòng, lịch sử sức khỏe
- [ ] Cài đặt lượng thức ăn chi tiết
- [ ] Thống kê tiêu thụ thức ăn/nước
- [ ] Xuất báo cáo Excel/PDF
- [ ] Biểu đồ tăng trọng
- [ ] Thống kê sản lượng trứng

---

## License

MIT License