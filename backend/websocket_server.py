"""
WebSocket Server - SocketIO integration for real-time camera detection
"""

from flask_socketio import SocketIO, emit, join_room, leave_room
import base64
import logging

logger = logging.getLogger(__name__)

# SocketIO instance will be initialized by app.py
socketio = None

# Store connected clients per camera
camera_rooms = {}  # device_id -> set of session ids


def init_socketio(socketio_instance):
    """Initialize socketio and register event handlers"""
    global socketio
    socketio = socketio_instance
    
    # Register event handlers
    socketio.on_event('connect', handle_connect)
    socketio.on_event('disconnect', handle_disconnect)
    socketio.on_event('subscribe_camera', handle_subscribe_camera)
    socketio.on_event('unsubscribe_camera', handle_unsubscribe_camera)
    socketio.on_event('start_detection', handle_start_detection)
    socketio.on_event('stop_detection', handle_stop_detection)


def handle_connect():
    """Handle client connection"""
    from flask import request
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to camera detection server'})


def handle_disconnect():
    """Handle client disconnection"""
    from flask import request
    logger.info(f"Client disconnected: {request.sid}")
    # Remove from all camera rooms
    for device_id, sessions in camera_rooms.items():
        if request.sid in sessions:
            sessions.discard(request.sid)


def handle_subscribe_camera(data):
    """Subscribe to camera detection updates"""
    from flask import request
    device_id = data.get('device_id')
    if not device_id:
        emit('error', {'message': 'device_id required'})
        return
    
    # Join room for this camera
    room = f'camera_{device_id}'
    join_room(room)
    
    # Track session
    if device_id not in camera_rooms:
        camera_rooms[device_id] = set()
    camera_rooms[device_id].add(request.sid)
    
    logger.info(f"Client {request.sid} subscribed to camera {device_id}")
    emit('subscribed', {'device_id': device_id, 'room': room})


def handle_unsubscribe_camera(data):
    """Unsubscribe from camera detection updates"""
    from flask import request
    device_id = data.get('device_id')
    if not device_id:
        return
    
    room = f'camera_{device_id}'
    leave_room(room)
    
    # Remove from tracking
    if device_id in camera_rooms:
        camera_rooms[device_id].discard(request.sid)
        if not camera_rooms[device_id]:
            del camera_rooms[device_id]
    
    logger.info(f"Client {request.sid} unsubscribed from camera {device_id}")
    emit('unsubscribed', {'device_id': device_id})


def handle_start_detection(data):
    """Start detection for a camera"""
    device_id = data.get('device_id')
    if not device_id:
        emit('error', {'message': 'device_id required'})
        return
    
    # This will be handled by the API, but we can acknowledge
    emit('detection_started', {'device_id': device_id})


def handle_stop_detection(data):
    """Stop detection for a camera"""
    device_id = data.get('device_id')
    if not device_id:
        return
    
    emit('detection_stopped', {'device_id': device_id})


# Helper functions for emitting detection results
def emit_detection_result(device_id: int, detections: list, annotated_frame=None, frame_base64: str = None, image_path: str = None):
    """Emit detection result to subscribed clients"""
    room = f'camera_{device_id}'
    
    # Convert frame to base64 if provided
    if annotated_frame is not None and frame_base64 is None:
        try:
            import cv2
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            logger.error(f"Frame encoding error: {e}")
            frame_base64 = None
    
    # Prepare detection data
    from datetime import datetime
    detection_data = {
        'device_id': device_id,
        'timestamp': datetime.now().isoformat(),
        'frame': frame_base64,
        'image_path': image_path,
        'detections': detections,
        'chicken_count': len(detections),
        'has_disease': any(d.get('has_disease', False) for d in detections),
        'disease_count': sum(1 for d in detections if d.get('has_disease', False))
    }
    
    # Emit to room
    socketio.emit('detection_result', detection_data, room=room)


def emit_camera_status(device_id: int, status: str, message: str = None):
    """Emit camera status change"""
    room = f'camera_{device_id}'
    from datetime import datetime
    socketio.emit('camera_status', {
        'device_id': device_id,
        'status': status,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }, room=room)


def emit_stats_update(device_id: int, stats: dict):
    """Emit worker statistics"""
    room = f'camera_{device_id}'
    from datetime import datetime
    socketio.emit('stats_update', {
        'device_id': device_id,
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    }, room=room)


def get_subscriber_count(device_id: int) -> int:
    """Get number of subscribers for a camera"""
    return len(camera_rooms.get(device_id, set()))


def has_subscribers(device_id: int) -> bool:
    """Check if camera has any subscribers"""
    return device_id in camera_rooms and len(camera_rooms[device_id]) > 0