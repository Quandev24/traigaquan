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

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from datetime import datetime
import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Coop, Device, CoopDevice, Environment, VideoRecording, AIDetection, Alert
from Camera_AI.Lib_.ai_detector import AIDetector

logger = logging.getLogger(__name__)


def _get_stream_manager():
    """Lazy import stream_manager to avoid circular imports"""
    from services.stream_manager import stream_manager
    return stream_manager


def _get_websocket_functions():
    """Lazy import websocket functions to avoid circular imports"""
    from websocket_server import emit_detection_result, emit_camera_status, has_subscribers
    return emit_detection_result, emit_camera_status, has_subscribers

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


def detect_media_type(file_path):
    """Phát hiện loại media (video/image/unknown) dựa trên phần mở rộng file."""
    ext = os.path.splitext(file_path)[1].lower()
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg'}
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    if ext in image_exts:
        return 'image'
    if ext in video_exts:
        return 'video'
    return 'unknown'


def find_first_camera():
    """Tìm camera đầu tiên (device type='camera') chưa bị xóa. Trả về Device object hoặc None."""
    return Device.query.filter_by(type='camera', deleted=False).order_by(Device.id.asc()).first()


def find_camera_2():
    """Tìm camera thứ 2 (Camera 2) chưa bị xóa. Trả về Device object hoặc None."""
    return Device.query.filter(
        Device.type == 'camera',
        Device.deleted == False,
        Device.name.like('%Camera 2%')
    ).order_by(Device.id.asc()).first()


# Tạo Blueprint cho routes camera
# URL: /api/camera
camera_bp = Blueprint('camera', __name__)


@camera_bp.route('', methods=['GET'])
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
def get_video_path():
    """Đọc đường dẫn video/ảnh đầu tiên từ file text video_path.txt."""
    path = read_video_path()
    media_type = detect_media_type(path) if path else None
    return jsonify({'video_path': path, 'media_type': media_type}), 200


@camera_bp.route('/video-paths', methods=['GET'])
def get_video_paths():
    """Đọc tất cả đường dẫn từ file text video_path.txt (mỗi dòng một path)."""
    paths = read_video_paths()
    media_types = [detect_media_type(p) for p in paths]
    return jsonify({'video_paths': paths, 'media_types': media_types}), 200


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
    Tự động load video từ file text vào Camera 2.

    Luồng xử lý:
    1. Đọc đường dẫn video từ video_path.txt
    2. Tìm Camera 2 (Device.type == 'camera' và name chứa 'Camera 2')
    3. Tạo VideoRecording với source_type='file_path'
    4. Broadcast WebSocket để frontend cập nhật

    Returns:
        201: Recording object đã tạo
        400: File text rỗng hoặc không có Camera 2
    """
    source_value = read_video_path()
    if not source_value:
        return jsonify({'error': 'No media path in video_path.txt'}), 400

    if not os.path.exists(source_value):
        return jsonify({'error': f'File not found: {source_value}'}), 400

    camera = find_camera_2()
    if not camera:
        return jsonify({'error': 'No Camera 2 device found'}), 400

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

    ai_result = None
    try:
        detector = AIDetector()
        ext = os.path.splitext(source_value)[1].lower()
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
        is_video = ext in video_exts

        last_frame = None
        if is_video:
            result = detector.detect_video(source_value, coop_id=coop_id, device_id=camera.id)
            last_frame = result.pop('_last_frame', None)
        else:
            result = detector.detect(source_value, coop_id=coop_id, device_id=camera.id)

        if 'error' not in result:
            detection = AIDetection(
                device_id=camera.id,
                coop_id=coop_id,
                source_file=source_value,
                chicken_count=result.get('chicken_count', 0),
                has_disease=result.get('has_disease', False),
                diseases=result.get('diseases', []),
                details=result.get('chickens', []),
                detected_at=datetime.now(),
            )
            db.session.add(detection)
            db.session.commit()

            image_url = None
            try:
                image_url = detector.annotate_and_save(source_value, result, detection_id=detection.id, image=last_frame)
                if image_url is None:
                    logger.error("annotate_and_save returned None - image NOT saved for detection_id=%s", detection.id)
            except Exception as e:
                logger.exception("annotate_and_save failed for detection_id=%s: %s", detection.id, e)
                image_url = None

            ai_result = detection.to_dict()
            ai_result['image_url'] = image_url

            if result.get('has_disease') and coop_id:
                coop = db.session.get(Coop, coop_id)
                coop_name = coop.name if coop else 'Unknown'
                disease_names = ', '.join(d['disease'] for d in result.get('diseases', []))
                alert = Alert(
                    coop_id=coop_id,
                    device_id=camera.id,
                    type='disease',
                    level='warning',
                    message=f'{coop_name}: Phát hiện gà bệnh - {disease_names}',
                )
                db.session.add(alert)
                db.session.commit()
    except Exception as e:
        logger.exception("AI detection failed for camera_id=%s: %s", camera.id, e)
        ai_result = {'error': str(e)}

    response_data = recording.to_dict()
    response_data['ai_detection'] = ai_result

    return jsonify(response_data), 201


@camera_bp.route('/serve-video', methods=['GET'])
def serve_video():
    """
    Phục vụ file media (video/ảnh) từ đường dẫn cục bộ (file_path).
    Hỗ trợ HTTP Range header cho phát video trong trình duyệt.

    Query params:
        path (str): Đường dẫn file media (VD: D:/Camera_Data/record.mp4 hoặc D:/image.jpg)

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
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.bmp': 'image/bmp', '.webp': 'image/webp',
        '.tiff': 'image/tiff', '.tif': 'image/tiff',
        '.svg': 'image/svg+xml',
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


# ============================================================
# CAMERA STREAM & DETECTION CONTROL API
# ============================================================

@camera_bp.route('/<int:device_id>/stream-config', methods=['GET'])
@jwt_required()
def get_stream_config(device_id):
    """Get camera stream configuration"""
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    return jsonify({
        'device_id': device.id,
        'stream_url': device.stream_url,
        'stream_type': device.stream_type,
        'stream_enabled': device.stream_enabled,
        'frame_skip': device.frame_skip,
        'analysis_interval_seconds': getattr(device, 'analysis_interval_seconds', 10)
    }), 200


@camera_bp.route('/<int:device_id>/stream-config', methods=['PUT'])
@jwt_required()
def update_stream_config(device_id):
    """Update camera stream configuration"""
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    was_enabled = device.stream_enabled
    
    if 'stream_url' in data:
        device.stream_url = data['stream_url']
    if 'stream_type' in data:
        device.stream_type = data['stream_type']
    if 'stream_enabled' in data:
        device.stream_enabled = bool(data['stream_enabled'])
    if 'frame_skip' in data:
        device.frame_skip = max(1, int(data['frame_skip']))
    if 'analysis_interval_seconds' in data:
        device.analysis_interval_seconds = max(1, int(data['analysis_interval_seconds']))
    
    db.session.commit()
    
    # Update stream manager
    from services.stream_manager import stream_manager
    sm = _get_stream_manager()
    sm.update_camera_config(
        device_id, 
        stream_url=device.stream_url,
        frame_skip=device.frame_skip,
        analysis_interval_seconds=getattr(device, 'analysis_interval_seconds', 10)
    )
    
    # Auto-start/stop based on stream_enabled
    if device.stream_enabled and not was_enabled:
        sm = _get_stream_manager()
        sm.start_camera(device_id)
    elif not device.stream_enabled and was_enabled:
        sm = _get_stream_manager()
        sm.stop_camera(device_id)
    
    return jsonify({
        'message': 'Stream config updated',
        'device_id': device.id,
        'stream_url': device.stream_url,
        'stream_type': device.stream_type,
        'stream_enabled': device.stream_enabled,
        'frame_skip': device.frame_skip
    }), 200


@camera_bp.route('/<int:device_id>/detection/start', methods=['POST'])
@jwt_required()
def start_detection(device_id):
    """Start real-time detection for a camera"""
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    # Get coop_id
    coop_device = CoopDevice.query.filter_by(device_id=device_id, deleted=False).first()
    coop_id = coop_device.coop_id if coop_device else None
    
    if not coop_id:
        return jsonify({'error': 'Camera not assigned to a coop'}), 400
    
    # Register if not already registered
    sm = _get_stream_manager()
    if device_id not in sm.workers:
        stream_url = device.stream_url or f'rtsp://camera-{device_id}.local:8554/stream'
        frame_skip = device.frame_skip or 5
        sm.register_camera(device_id, stream_url, coop_id, frame_skip)
    
    success = sm.start_camera(device_id)
    
    if success:
        return jsonify({
            'message': 'Detection started',
            'device_id': device_id,
            'status': 'running'
        }), 200
    else:
        return jsonify({'error': 'Failed to start detection'}), 500


@camera_bp.route('/<int:device_id>/detection/stop', methods=['POST'])
@jwt_required()
def stop_detection(device_id):
    """Stop real-time detection for a camera"""
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    sm = _get_stream_manager()
    success = sm.stop_camera(device_id)
    
    if success:
        return jsonify({
            'message': 'Detection stopped',
            'device_id': device_id,
            'status': 'stopped'
        }), 200
    else:
        return jsonify({'error': 'Camera not running or not found'}), 400


@camera_bp.route('/<int:device_id>/detection/status', methods=['GET'])
@jwt_required()
def get_detection_status(device_id):
    """Get detection worker status"""
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    sm = _get_stream_manager()
    status = sm.get_camera_status(device_id)
    
    if not status:
        return jsonify({
            'device_id': device_id,
            'running': False,
            'registered': False
        }), 200
    
    status['registered'] = True
    return jsonify(status), 200


@camera_bp.route('/detection/start-all', methods=['POST'])
@jwt_required()
def start_all_detection():
    """Start detection for all Camera 2 devices"""
    sm = _get_stream_manager()
    started = sm.start_all()
    return jsonify({
        'message': f'Started {started} cameras',
        'started': started
    }), 200


@camera_bp.route('/detection/stop-all', methods=['POST'])
@jwt_required()
def stop_all_detection():
    """Stop detection for all cameras"""
    sm = _get_stream_manager()
    stopped = sm.stop_all()
    return jsonify({
        'message': f'Stopped {stopped} cameras',
        'stopped': stopped
    }), 200


@camera_bp.route('/detection/status-all', methods=['GET'])
@jwt_required()
def get_all_detection_status():
    """Get status of all camera workers"""
    sm = _get_stream_manager()
    status_list = sm.get_all_status()
    health = sm.health_check()
    
    return jsonify({
        'cameras': status_list,
        'health': health
    }), 200


@camera_bp.route('/<int:device_id>/live.mjpeg', methods=['GET'])
def live_mjpeg_stream(device_id):
    """MJPEG stream for live camera viewing"""
    sm = _get_stream_manager()
    
    device = Device.query.filter_by(id=device_id, type='camera').first()
    if not device:
        return jsonify({'error': 'Camera not found'}), 404
    
    worker = sm.workers.get(device_id)
    if not worker or not worker.running:
        return jsonify({'error': 'Camera not running'}), 400
    
    def generate():
        while worker.running:
            try:
                # Get latest frame from worker
                if hasattr(worker, 'mock_frame') and worker.mock_frame is not None:
                    frame = worker.mock_frame.copy()
                else:
                    # For real cameras, we'd need a frame buffer
                    # This is a placeholder
                    time.sleep(0.1)
                    continue
                
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
                       b'\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(0.05)  # ~20 FPS
            except Exception as e:
                logger.error(f"MJPEG stream error: {e}")
                break
    
    from flask import Response
    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@camera_bp.route('/camera2/list', methods=['GET'])
@jwt_required()
def list_camera2_devices():
    """List all Camera 2 devices with their stream config"""
    cameras = Device.query.filter(
        Device.type == 'camera',
        Device.deleted == False,
        Device.name.like('%Camera 2%')
    ).order_by(Device.id.asc()).all()
    
    result = []
    sm = _get_stream_manager()
    
    for cam in cameras:
        coop_device = CoopDevice.query.filter_by(device_id=cam.id, deleted=False).first()
        coop = Coop.query.get(coop_device.coop_id) if coop_device else None
        
        worker_status = sm.get_camera_status(cam.id)
        
        result.append({
            'device_id': cam.id,
            'name': cam.name,
            'coop_id': coop.id if coop else None,
            'coop_name': coop.name if coop else None,
            'stream_url': cam.stream_url,
            'stream_type': cam.stream_type,
            'stream_enabled': cam.stream_enabled,
            'frame_skip': cam.frame_skip,
            'status': cam.status,
            'worker': worker_status
        })
    
    return jsonify(result), 200