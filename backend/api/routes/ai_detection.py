"""
AI Detection Routes - API cho phát hiện gà bệnh bằng AI

Các endpoint:
  POST /api/ai/detect           - Chạy AI detection trên file
  GET  /api/ai/detections       - Lấy kết quả AI gần nhất (có filter coop_id/device_id)
  GET  /api/ai/detections/<id>  - Chi tiết một kết quả AI
"""

import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
from models import db, Coop, Device, CoopDevice, AIDetection, Alert
from Camera_AI.Lib_.ai_detector import AIDetector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ai_bp = Blueprint('ai', __name__)
detector = AIDetector()
logger = logging.getLogger(__name__)


@ai_bp.route('/detect', methods=['POST'])
@jwt_required()
def run_detection():
    """
    Chạy AI detection trên file media (video/ảnh).

    Body:
        file_path (str): Đường dẫn file media
        coop_id (int, optional): ID chuồng
        device_id (int, optional): ID camera

    Returns:
        200: Kết quả detection
        400: Thiếu file_path
    """
    data = request.get_json()
    if not data or not data.get('file_path'):
        return jsonify({'error': 'file_path is required'}), 400

    file_path = data['file_path']
    coop_id = data.get('coop_id')
    device_id = data.get('device_id')

    if not os.path.exists(file_path):
        return jsonify({'error': f'File not found: {file_path}'}), 400

    ext = os.path.splitext(file_path)[1].lower()
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    is_video = ext in video_exts

    last_frame = None
    if is_video:
        result = detector.detect_video(file_path, coop_id=coop_id, device_id=device_id)
        last_frame = result.pop('_last_frame', None)
    else:
        result = detector.detect(file_path, coop_id=coop_id, device_id=device_id)

    if 'error' in result:
        return jsonify(result), 400

    detection = AIDetection(
        device_id=device_id,
        coop_id=coop_id,
        source_file=file_path,
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
        image_url = detector.annotate_and_save(file_path, result, detection_id=detection.id, image=last_frame)
        if image_url is None:
            logger.error("annotate_and_save returned None - image NOT saved for detection_id=%s", detection.id)
    except Exception as e:
        logger.exception("annotate_and_save failed for detection_id=%s: %s", detection.id, e)
        image_url = None

    if result.get('has_disease') and coop_id:
        coop = db.session.get(Coop, coop_id)
        coop_name = coop.name if coop else 'Unknown'
        disease_names = ', '.join(d['disease'] for d in result.get('diseases', []))
        alert = Alert(
            coop_id=coop_id,
            device_id=device_id,
            type='disease',
            level='warning',
            message=f'{coop_name}: Phát hiện gà bệnh - {disease_names}',
        )
        db.session.add(alert)
        db.session.commit()

    response_data = detection.to_dict()
    response_data['image_url'] = image_url
    return jsonify(response_data), 200


@ai_bp.route('/detections', methods=['GET'])
@jwt_required()
def get_detections():
    """
    Lấy danh sách kết quả AI detection.

    Query params:
        coop_id (int, optional): Lọc theo chuồng
        device_id (int, optional): Lọc theo camera
        limit (int): Số lượng (mặc định: 20)

    Returns:
        200: Array of detection objects
    """
    coop_id = request.args.get('coop_id', type=int)
    device_id = request.args.get('device_id', type=int)
    limit = request.args.get('limit', 20, type=int)

    query = AIDetection.query.filter(AIDetection.deleted == False)

    if coop_id:
        query = query.filter_by(coop_id=coop_id)
    if device_id:
        query = query.filter_by(device_id=device_id)

    detections = query.order_by(AIDetection.detected_at.desc()).limit(limit).all()
    result_list = []
    for d in detections:
        item = d.to_dict()
        img_path = os.path.join(BASE_DIR, 'static', 'ai_detections', f'detection_{d.id}.jpg')
        item['image_url'] = f'/ai_detections/detection_{d.id}.jpg' if os.path.exists(img_path) else None
        result_list.append(item)
    return jsonify(result_list), 200


@ai_bp.route('/detections/<int:detection_id>', methods=['GET'])
@jwt_required()
def get_detection(detection_id):
    """
    Chi tiết một kết quả AI detection.

    Args:
        detection_id: ID của detection

    Returns:
        200: Detection object
        404: Không tìm thấy
    """
    detection = AIDetection.query.filter_by(id=detection_id, deleted=False).first()
    if not detection:
        return jsonify({'error': 'Detection not found'}), 404

    response_data = detection.to_dict()
    img_path = os.path.join(BASE_DIR, 'static', 'ai_detections', f'detection_{detection.id}.jpg')
    response_data['image_url'] = f'/ai_detections/detection_{detection.id}.jpg' if os.path.exists(img_path) else None
    return jsonify(response_data), 200
