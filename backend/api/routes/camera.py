"""
Camera Routes - API quản lý camera

Module này cung cấp các endpoint cho việc:
- Lấy danh sách camera
- Lấy thông tin chi tiết camera
- Lấy camera theo chuồng
- Chụp ảnh snapshot
- Lấy URL stream video
- Lấy danh sách recordings
- Tạo recording mới (text / video_url / file_path)
- Xoá recording

Camera là một loại thiết bị đặc biệt (type='camera').
Mỗi camera có thể được gán vào một hoặc nhiều chuồng.

Source types cho recordings:
- text: Nội dung mô tả dạng text
- video_url: Link URL video
- file_path: Đường dẫn file video cục bộ
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Coop, Device, CoopDevice, Environment, VideoRecording

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
VIDEO_PATH_FILE = os.path.join(PROJECT_DIR, 'video_path.txt')


def read_video_path():
    """Đọc đường dẫn video đầu tiên từ file text. Trả về None nếu file không tồn tại hoặc rỗng."""
    paths = read_video_paths()
    return paths[0] if paths else None


def read_video_paths():
    """Đọc tất cả đường dẫn video từ file text (mỗi dòng một path).
    Trả về list các path, bỏ qua dòng trống."""
    if os.path.exists(VIDEO_PATH_FILE):
        with open(VIDEO_PATH_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            paths = [line.strip() for line in lines if line.strip()]
            return paths
    return []


def write_video_path(path):
    """Ghi đường dẫn video vào file text (dòng đầu tiên)."""
    existing = read_video_paths()
    if existing:
        existing[0] = path.strip()
    else:
        existing = [path.strip()]
    with open(VIDEO_PATH_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(existing))


def find_first_camera():
    """Tìm camera đầu tiên (device type='camera') chưa bị xóa. Trả về Device object hoặc None."""
    return Device.query.filter_by(type='camera', deleted=False).order_by(Device.id.asc()).first()


# Tạo Blueprint cho routes camera
# URL: /api/camera
camera_bp = Blueprint('camera', __name__)


@camera_bp.route('', methods=['GET'])
@jwt_required()
def get_cameras():
    """
    Lấy danh sách tất cả camera.
    
    Lọc các thiết bị có type='camera' và trả về thông tin
    kèm theo danh sách chuồng mà camera đó được gán.
    
    Returns:
        200: [
            {
                "id": 1,
                "name": "Camera Chuồng A",
                "status": "online",
                "is_active": true,
                "coops": [{"id": 1, "name": "Chuồng A"}]
            },
            ...
        ]
    """
    # Lọc chỉ lấy các thiết bị là camera (chưa bị xóa mềm)
    devices = Device.query.filter_by(type='camera', deleted=False).all()
    cameras = []
    
    for device in devices:
        # Lấy danh sách chuồng của camera (chưa bị xóa mềm)
        coop_devices = CoopDevice.query.filter_by(device_id=device.id, deleted=False).all()
        coop_ids = [cd.coop_id for cd in coop_devices]
        coops = Coop.query.filter(Coop.id.in_(coop_ids), Coop.deleted == False).all() if coop_ids else []
        
        cameras.append({
            'id': device.id,
            'name': device.name,
            'status': device.status,
            'is_active': device.is_active,
            'coops': [{'id': c.id, 'name': c.name} for c in coops]
        })
    
    return jsonify(cameras), 200


@camera_bp.route('/<int:device_id>', methods=['GET'])
@jwt_required()
def get_camera(device_id):
    """
    Lấy thông tin chi tiết một camera.
    
    Args:
        device_id (int): ID của camera
        
    Returns:
        200: {
            "id": 1,
            "name": "Camera Chuồng A",
            "status": "online",
            "is_active": true,
            "mac_address": "00:11:22:33:44:55",
            "battery": 85,
            "coops": [...],
            "created_at": "2025-01-01T00:00:00"
        }
        404: Không tìm thấy camera
    """
    # Tìm thiết bị là camera
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    # Lấy danh sách chuồng (chưa bị xóa mềm)
    coop_devices = CoopDevice.query.filter_by(device_id=device_id, deleted=False).all()
    coop_ids = [cd.coop_id for cd in coop_devices]
    coops = Coop.query.filter(Coop.id.in_(coop_ids), Coop.deleted == False).all() if coop_ids else []
    
    return jsonify({
        'id': device.id,
        'name': device.name,
        'status': device.status,
        'is_active': device.is_active,
        'mac_address': device.mac_address,
        'battery': device.battery,
        'coops': [{'id': c.id, 'name': c.name} for c in coops],
        'created_at': device.created_at.isoformat() if device.created_at else None
    }), 200


@camera_bp.route('/coop/<int:coop_id>', methods=['GET'])
@jwt_required()
def get_camera_by_coop(coop_id):
    """
    Lấy danh sách camera của một chuồng cụ thể.
    
    Args:
        coop_id (int): ID của chuồng
        
    Returns:
        200: [
            {"id": 1, "name": "Camera A1", "status": "online", "is_active": true},
            ...
        ]
        404: Không tìm thấy chuồng
    """
    # Kiểm tra chuồng tồn tại
    coop = Coop.query.get(coop_id)
    if not coop:
        return jsonify({'error': 'Coop not found'}), 404
    
    # Lấy danh sách thiết bị trong chuồng (chưa bị xóa mềm)
    coop_devices = CoopDevice.query.filter_by(coop_id=coop_id, deleted=False).all()
    device_ids = [cd.device_id for cd in coop_devices]
    
    # Lọc chỉ lấy camera (chưa bị xóa mềm)
    cameras = Device.query.filter(
        Device.id.in_(device_ids),
        Device.type == 'camera',
        Device.deleted == False
    ).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'status': c.status,
        'is_active': c.is_active
    } for c in cameras]), 200


@camera_bp.route('/<int:device_id>/snapshot', methods=['POST'])
@jwt_required()
def capture_snapshot(device_id):
    """
    Chụp ảnh snapshot từ camera.
    
    Gửi lệnh yêu cầu camera chụp 1 frame và lưu lại.
    (Đây là API mô phỏng - cần tích hợp với thiết bị thực tế)
    
    Args:
        device_id (int): ID của camera
        
    Returns:
        200: {
            "device_id": 1,
            "device_name": "Camera A1",
            "timestamp": "2025-01-01T00:00:00",
            "success": true,
            "image_url": "/uploads/cameras/1/snapshot.jpg"
        }
        404: Không tìm thấy camera
    """
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    # Mô phỏng snapshot (cần tích hợp với actual camera API)
    snapshot = {
        'device_id': device_id,
        'device_name': device.name,
        'timestamp': datetime.now().isoformat(),
        'success': True,
        'image_url': f'/uploads/cameras/{device_id}/snapshot.jpg'
    }
    
    return jsonify(snapshot), 200


@camera_bp.route('/<int:device_id>/stream', methods=['GET'])
@jwt_required()

def get_stream_url(device_id):
    """
    Lấy URL streaming của camera.
    
    Trả về URL RTSP/HTTP để truy cập video stream.
    (Đây là API mô phỏng - cần tích hợp với thiết bị thực tế)
    
    Args:
        device_id (int): ID của camera
        
    Returns:
        200: {
            "device_id": 1,
            "stream_url": "rtsp://camera-1.local:8554/stream",
            "status": "online"
        }
        404: Không tìm thấy camera
    """
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    # Mô phỏng stream URL (thay bằng actual camera stream URL)
    stream_url = f'rtsp://camera-{device_id}.local:8554/stream'
    
    return jsonify({
        'device_id': device_id,
        'stream_url': stream_url,
        'status': device.status
    }), 200


@camera_bp.route('/<int:device_id>/recordings', methods=['GET'])
@jwt_required()
def get_recordings(device_id):
    """
    Lấy danh sách recordings của camera.

    Query params:
        limit (int): Số lượng recordings (mặc định: 10)
        offset (int): Vị trí bắt đầu (mặc định: 0)

    Returns:
        200: {
            "device_id": 1,
            "device_name": "...",
            "recordings": [...],
            "count": 5,
            "total": 5
        }
    """
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404

    limit = request.args.get('limit', 10, type=int)
    offset = request.args.get('offset', 0, type=int)

    query = VideoRecording.query.filter_by(
        device_id=device_id, deleted=False
    ).order_by(VideoRecording.recorded_at.desc())

    total = query.count()
    recordings = query.offset(offset).limit(limit).all()

    return jsonify({
        'device_id': device_id,
        'device_name': device.name,
        'recordings': [r.to_dict() for r in recordings],
        'count': len(recordings),
        'total': total
    }), 200


@camera_bp.route('/<int:device_id>/recordings', methods=['POST'])
@jwt_required()
def create_recording(device_id):
    """
    Tạo recording mới cho camera.

    Body (JSON):
    {
        "source_type": "text" | "video_url" | "file_path",
        "source_value": "...",
        "name": "Tên recording (tuỳ chọn)",
        "duration": 300 (tuỳ chọn),
        "file_size": 45000000 (tuỳ chọn)
    }
    """
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    source_type = data.get('source_type')
    source_value = data.get('source_value')

    if not source_type or source_type not in VideoRecording.SOURCE_TYPES:
        return jsonify({'error': f'source_type must be one of: {VideoRecording.SOURCE_TYPES}'}), 400
    if not source_value:
        return jsonify({'error': 'source_value is required'}), 400

    coop_devices = CoopDevice.query.filter_by(device_id=device_id, deleted=False).first()
    coop_id = coop_devices.coop_id if coop_devices else None

    recording = VideoRecording(
        device_id=device_id,
        coop_id=coop_id,
        name=data.get('name', f'Recording {datetime.now().strftime("%Y%m%d_%H%M%S")}'),
        source_type=source_type,
        source_value=source_value,
        thumbnail_url=data.get('thumbnail_url', f'/thumbnails/cameras/{device_id}/live.jpg'),
        duration=data.get('duration'),
        file_size=data.get('file_size'),
        recorded_at=datetime.now()
    )
    db.session.add(recording)
    db.session.commit()

    return jsonify(recording.to_dict()), 201


@camera_bp.route('/<int:device_id>/recordings/<int:recording_id>', methods=['GET'])
@jwt_required()
def get_recording_detail(device_id, recording_id):
    """Lấy chi tiết một recording."""
    recording = VideoRecording.query.filter_by(
        id=recording_id, device_id=device_id, deleted=False
    ).first()
    if not recording:
        return jsonify({'error': 'Recording not found'}), 404
    return jsonify(recording.to_dict()), 200


@camera_bp.route('/<int:device_id>/recordings/<int:recording_id>', methods=['DELETE'])
@jwt_required()
def delete_recording(device_id, recording_id):
    """Xóa mềm một recording."""
    recording = VideoRecording.query.filter_by(
        id=recording_id, device_id=device_id, deleted=False
    ).first()
    if not recording:
        return jsonify({'error': 'Recording not found'}), 404

    recording.deleted = True
    db.session.commit()
    return jsonify({'message': 'Recording deleted successfully'}), 200


@camera_bp.route('/video-path', methods=['GET'])
@jwt_required()
def get_video_path():
    """Đọc đường dẫn video đầu tiên từ file text video_path.txt."""
    path = read_video_path()
    return jsonify({'video_path': path}), 200


@camera_bp.route('/video-paths', methods=['GET'])
@jwt_required()
def get_video_paths():
    """Đọc tất cả đường dẫn video từ file text video_path.txt (mỗi dòng một path)."""
    paths = read_video_paths()
    return jsonify({'video_paths': paths}), 200


@camera_bp.route('/video-path', methods=['PUT'])
@jwt_required()
def update_video_path():
    """Ghi đường dẫn video vào file text video_path.txt."""
    data = request.get_json()
    if not data or not data.get('video_path'):
        return jsonify({'error': 'video_path is required'}), 400
    path = data['video_path']
    write_video_path(path)
    return jsonify({'message': 'Video path updated', 'video_path': path}), 200


@camera_bp.route('/auto-load', methods=['POST'])
@jwt_required()
def auto_load_from_file():
    """
    Tự động load video từ file text vào camera đầu tiên.

    Luồng xử lý:
    1. Đọc đường dẫn video từ video_path.txt
    2. Tìm camera đầu tiên (Device.type == 'camera')
    3. Tạo VideoRecording với source_type='file_path'
    4. Broadcast WebSocket để frontend cập nhật

    Returns:
        201: Recording object đã tạo
        400: File text rỗng hoặc không có camera
    """
    source_value = read_video_path()
    if not source_value:
        return jsonify({'error': 'No video path in video_path.txt'}), 400

    if not os.path.exists(source_value):
        return jsonify({'error': f'Video file not found: {source_value}'}), 400

    camera = find_first_camera()
    if not camera:
        return jsonify({'error': 'No camera device found'}), 400

    coop_devices = CoopDevice.query.filter_by(device_id=camera.id, deleted=False).first()
    coop_id = coop_devices.coop_id if coop_devices else None

    recorded_at = datetime.now()
    name = f'Auto_{recorded_at.strftime("%Y%m%d_%H%M%S")}'

    recording = VideoRecording(
        device_id=camera.id,
        coop_id=coop_id,
        name=name,
        source_type='file_path',
        source_value=source_value,
        duration=None,
        file_size=None,
        recorded_at=recorded_at
    )
    db.session.add(recording)
    db.session.commit()

    from websocket import broadcast_dashboard_update
    broadcast_dashboard_update()

    return jsonify(recording.to_dict()), 201


@camera_bp.route('/serve-video', methods=['GET'])
def serve_video():
    """
    Phục vụ file video từ đường dẫn cục bộ (file_path).
    Hỗ trợ HTTP Range header cho phát video trong trình duyệt.

    Query params:
        path (str): Đường dẫn file video (VD: D:/Camera_Data/record.mp4)

    Returns:
        206: Partial content (khi có Range header)
        200: Full content (khi không có Range)
        400: Thiếu path
        404: File không tồn tại
        416: Range không hợp lệ
    """
    video_path = request.args.get('path')
    if not video_path:
        return jsonify({'error': 'path is required'}), 400

    if not os.path.exists(video_path):
        return jsonify({'error': 'File not found'}), 404

    # Xác định MIME type
    ext = os.path.splitext(video_path)[1].lower()
    mime_map = {
        '.mp4': 'video/mp4', '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime', '.mkv': 'video/x-matroska',
        '.webm': 'video/webm', '.flv': 'video/x-flv',
        '.wmv': 'video/x-ms-wmv', '.m4v': 'video/mp4',
    }
    mime = mime_map.get(ext, 'application/octet-stream')

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get('Range')

    from flask import Response

    if not range_header:
        # Trả về toàn bộ file
        def generate_full():
            with open(video_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
        response = Response(generate_full(), mimetype=mime, status=200)
        response.headers['Content-Length'] = file_size
        response.headers['Accept-Ranges'] = 'bytes'
        return response

    # Parse Range header: "bytes=start-end"
    try:
        range_match = range_header.replace('bytes=', '').split('-')
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
    except (ValueError, IndexError):
        return jsonify({'error': 'Invalid Range header'}), 416

    if start >= file_size or end >= file_size or start > end:
        resp = jsonify({'error': 'Range not satisfiable'})
        resp.status_code = 416
        resp.headers['Content-Range'] = f'bytes */{file_size}'
        return resp

    content_length = end - start + 1

    def generate_range():
        with open(video_path, 'rb') as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(8192, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)

    response = Response(generate_range(), mimetype=mime, status=206)
    response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    response.headers['Content-Length'] = content_length
    response.headers['Accept-Ranges'] = 'bytes'
    return response


@camera_bp.route('/coop-detail/<int:coop_id>', methods=['GET'])
@jwt_required()
def get_coop_camera_detail(coop_id):
    coop = db.session.get(Coop, coop_id)
    if not coop or coop.deleted:
        return jsonify({'error': 'Coop not found'}), 404

    latest_env = Environment.query.filter_by(
        coop_id=coop_id, deleted=False
    ).order_by(Environment.recorded_at.desc()).first()

    coop_device_links = CoopDevice.query.filter_by(
        coop_id=coop_id, deleted=False
    ).all()
    device_ids = [cd.device_id for cd in coop_device_links]
    devices = []
    if device_ids:
        devices = Device.query.filter(
            Device.id.in_(device_ids),
            Device.is_active == True,
            Device.deleted == False
        ).all()

    return jsonify({
        'coop': {
            'id': coop.id,
            'name': coop.name,
            'current_count': coop.current_count,
            'area': coop.area,
            'location': coop.location,
            'status': coop.status
        },
        'environment': latest_env.to_dict() if latest_env else None,
        'devices': [
            {
                'id': d.id,
                'name': d.name,
                'type': d.type,
                'status': d.status,
                'is_active': d.is_active
            } for d in devices
        ]
    }), 200