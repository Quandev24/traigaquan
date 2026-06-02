"""
Warehouse Routes - API quản lý kho thức ăn

Module này cung cấp các endpoint public cho:
- Lấy danh sách thức ăn trong kho
- Cập nhật số lượng thức ăn
"""

from flask import Blueprint, jsonify, request
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

warehouse_bp = Blueprint('warehouse', __name__)


FEED_ITEMS = [
    {'id': 1, 'item_name': 'Cám gà con',   'quantity_kg': 1500, 'item_type': 'feed',     'min_threshold_kg': 300},
    {'id': 2, 'item_name': 'Cám gà đẻ',    'quantity_kg': 1200, 'item_type': 'feed',     'min_threshold_kg': 200},
    {'id': 3, 'item_name': 'Cám gà thịt',  'quantity_kg': 800,  'item_type': 'feed',     'min_threshold_kg': 150},
    {'id': 4, 'item_name': 'Premix khoáng', 'quantity_kg': 200,  'item_type': 'feed',     'min_threshold_kg': 50},
    {'id': 5, 'item_name': 'Thuốc phòng bệnh','quantity_kg': 50, 'item_type': 'medicine', 'min_threshold_kg': 10},
]


@warehouse_bp.route('/feed', methods=['GET'])
def get_feed_items():
    """Lấy danh sách thức ăn trong kho."""
    return jsonify({'items': FEED_ITEMS}), 200


@warehouse_bp.route('/feed/<int:item_id>', methods=['PUT'])
def update_feed_item(item_id):
    """Cập nhật số lượng thức ăn."""
    data = request.get_json(silent=True)
    if not data or 'quantity_kg' not in data:
        return jsonify({'error': 'Thiếu trường quantity_kg'}), 400

    for item in FEED_ITEMS:
        if item['id'] == item_id:
            item['quantity_kg'] = float(data['quantity_kg'])
            return jsonify(item), 200

    return jsonify({'error': 'Không tìm thấy mặt hàng'}), 404
