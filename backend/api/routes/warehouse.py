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
from models import db, WarehouseInventory, FeedConsumption

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


@warehouse_bp.route('', methods=['GET'])
def get_warehouse_items():
    item_type = request.args.get('item_type')
    query = WarehouseInventory.query.filter_by(deleted=False)
    if item_type:
        query = query.filter_by(item_type=item_type)
    items = query.all()
    total_kg = db.session.query(func.sum(WarehouseInventory.quantity_kg)).filter(
        WarehouseInventory.deleted == False
    ).scalar() or 0
    if item_type:
        total_kg = sum(i.quantity_kg for i in items)
    return jsonify({
        'items': [item.to_dict() for item in items],
        'total_kg': round(total_kg, 1)
    }), 200


@warehouse_bp.route('/consumption', methods=['GET'])
def get_consumption():
    coop_id = request.args.get('coop_id', type=int)
    item_type = request.args.get('item_type')
    days = request.args.get('days', default=30, type=int)
    query = FeedConsumption.query.filter_by(deleted=False)
    if coop_id:
        query = query.filter_by(coop_id=coop_id)
    if item_type:
        query = query.join(WarehouseInventory).filter(WarehouseInventory.item_type == item_type)
    cutoff = datetime.now(UTC).date()
    from datetime import timedelta
    start_date = cutoff - timedelta(days=days)
    query = query.filter(FeedConsumption.recorded_date >= start_date)
    records = query.order_by(FeedConsumption.recorded_date.asc()).all()

    daily = {}
    for r in records:
        d = r.recorded_date.isoformat() if r.recorded_date else ''
        cat = r.feed_item_category or (r.feed_item.item_type if r.feed_item else 'feed')
        key = f'{d}|{cat}'
        if key not in daily:
            daily[key] = {'date': d, 'category': cat, 'total_kg': 0}
        daily[key]['total_kg'] += r.quantity_kg

    return jsonify({
        'records': [r.to_dict() for r in records],
        'daily': list(daily.values()),
        'total_records': len(records)
    }), 200


@warehouse_bp.route('/consumption/overview', methods=['GET'])
def get_consumption_overview():
    item_type = request.args.get('item_type')
    coop_id = request.args.get('coop_id', type=int)
    query = FeedConsumption.query.filter_by(deleted=False).join(WarehouseInventory)
    if coop_id:
        query = query.filter(FeedConsumption.coop_id == coop_id)
    if item_type:
        query = query.filter(WarehouseInventory.item_type == item_type)

    rows = query.with_entities(
        FeedConsumption.coop_id,
        WarehouseInventory.item_type,
        func.sum(FeedConsumption.quantity_kg).label('total_kg')
    ).group_by(FeedConsumption.coop_id, WarehouseInventory.item_type).all()

    result = {}
    total_by_type = {}
    for row in rows:
        t = row.item_type or 'feed'
        if row.coop_id not in result:
            result[row.coop_id] = {}
        result[row.coop_id][t] = round(row.total_kg, 1)
        total_by_type[t] = total_by_type.get(t, 0) + round(row.total_kg, 1)

    return jsonify({
        'per_coop': result,
        'total_by_type': total_by_type
    }), 200


@warehouse_bp.route('/consumption/coop/<int:coop_id>', methods=['GET'])
def get_consumption_by_coop(coop_id):
    item_type = request.args.get('item_type')
    days = request.args.get('days', default=30, type=int)
    query = FeedConsumption.query.filter_by(coop_id=coop_id, deleted=False)
    if item_type:
        query = query.join(WarehouseInventory).filter(WarehouseInventory.item_type == item_type)
    cutoff = datetime.now(UTC).date()
    from datetime import timedelta
    start_date = cutoff - timedelta(days=days)
    query = query.filter(FeedConsumption.recorded_date >= start_date)
    records = query.order_by(FeedConsumption.recorded_date.asc()).all()
    return jsonify({
        'records': [r.to_dict() for r in records],
        'total_records': len(records)
    }), 200
