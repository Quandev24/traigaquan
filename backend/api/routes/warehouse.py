"""
Warehouse Routes - API quản lý kho

Module này cung cấp các endpoint cho việc:
- Xem danh sách thức ăn trong kho
- Cập nhật số lượng (inline edit từ dashboard)
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func
from datetime import datetime, UTC
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, WarehouseInventory

warehouse_bp = Blueprint('warehouse', __name__)


@warehouse_bp.route('/feed', methods=['GET'])
def get_feed_stock():
    """
    Lấy danh sách thức ăn trong kho.

    Returns:
        200: {
            "items": [ ... ],
            "total_kg": <float>
        }
    """
    items = WarehouseInventory.query.filter_by(item_type='feed', deleted=False).all()
    total_kg = db.session.query(func.sum(WarehouseInventory.quantity_kg)).filter(
        WarehouseInventory.item_type == 'feed',
        WarehouseInventory.deleted == False
    ).scalar() or 0

    return jsonify({
        'items': [item.to_dict() for item in items],
        'total_kg': round(total_kg, 1)
    }), 200


@warehouse_bp.route('/feed/<int:item_id>', methods=['PUT'])
def update_feed_quantity(item_id):
    """
    Cập nhật số lượng thức ăn (inline edit).

    Body: { "quantity_kg": <float> }

    Returns:
        200: Updated item
        404: Item not found
    """
    item = db.session.get(WarehouseInventory, item_id)
    if not item or item.deleted:
        return jsonify({'error': 'Item not found'}), 404

    data = request.get_json()
    if 'quantity_kg' not in data:
        return jsonify({'error': 'quantity_kg is required'}), 400

    new_qty = float(data['quantity_kg'])
    if new_qty < 0:
        return jsonify({'error': 'quantity_kg cannot be negative'}), 400

    item.quantity_kg = new_qty
    item.updated_at = datetime.now(UTC)
    db.session.commit()

    return jsonify(item.to_dict()), 200
