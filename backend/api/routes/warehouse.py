"""
Warehouse Routes - API quản lý kho thức ăn

Module này cung cấp các endpoint public cho:
- Lấy danh sách thức ăn trong kho
- Cập nhật số lượng thức ăn
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Coop, WarehouseInventory, FeedConsumption

warehouse_bp = Blueprint('warehouse', __name__)


@warehouse_bp.route('/feed', methods=['GET'])
def get_feed_items():
    """Lấy danh sách thức ăn trong kho."""
    items = WarehouseInventory.query.filter_by(deleted=False).all()
    return jsonify({'items': [item.to_dict() for item in items]}), 200


@warehouse_bp.route('/feed/<int:item_id>', methods=['PUT'])
def update_feed_item(item_id):
    """Cập nhật số lượng thức ăn."""
    data = request.get_json(silent=True)
    if not data or 'quantity_kg' not in data:
        return jsonify({'error': 'Thiếu trường quantity_kg'}), 400

    item = WarehouseInventory.query.filter_by(id=item_id, deleted=False).first()
    if not item:
        return jsonify({'error': 'Không tìm thấy mặt hàng'}), 404

    item.quantity_kg = float(data['quantity_kg'])
    db.session.commit()
    return jsonify(item.to_dict()), 200


@warehouse_bp.route('/consumption/feed/by-coop', methods=['GET'])
def get_feed_consumption_by_coop():
    """Lấy dữ liệu tiêu thụ thức ăn theo chuồng, gộp theo thời gian."""
    period = request.args.get('period', 'day')

    query = FeedConsumption.query.order_by(FeedConsumption.recorded_date)

    records = query.all()

    daily_map = {}
    for r in records:
        d = r.recorded_date
        if period == 'week':
            d = d - timedelta(days=d.weekday())
        elif period == 'month':
            d = d.replace(day=1)
        elif period == 'year':
            d = d.replace(month=1, day=1)

        key = d.isoformat()
        if key not in daily_map:
            daily_map[key] = {}
        daily_map[key][str(r.coop_id)] = (daily_map[key].get(str(r.coop_id), 0)) + r.quantity_kg

    daily = [{'date': k, 'coops': v} for k, v in sorted(daily_map.items())]

    return jsonify({'daily': daily}), 200


@warehouse_bp.route('/consumption/feed/overview', methods=['GET'])
def get_feed_consumption_overview():
    """Lấy tổng quan tiêu thụ thức ăn: mỗi chuồng tiêu thụ bao nhiêu kg."""
    coops = Coop.query.all()
    per_coop = {}
    total = 0.0
    for coop in coops:
        s = db.session.query(db.func.coalesce(db.func.sum(FeedConsumption.quantity_kg), 0))\
            .filter(FeedConsumption.coop_id == coop.id).scalar()
        per_coop[str(coop.id)] = s
        total += s
    return jsonify({'per_coop': per_coop, 'total': total}), 200
