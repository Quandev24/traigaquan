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
from models import db, Coop, WarehouseInventory, FeedConsumption, MedicineConsumption, InventoryLog

warehouse_bp = Blueprint('warehouse', __name__)


@warehouse_bp.route('/feed', methods=['GET'])
def get_feed_items():
    """Lấy danh sách thức ăn trong kho."""
    items = WarehouseInventory.query.filter_by(deleted=False).all()
    return jsonify({'items': [item.to_dict() for item in items]}), 200


@warehouse_bp.route('/feed/<int:item_id>', methods=['PUT'])
def update_feed_item(item_id):
    """Cập nhật số lượng thức ăn (manual adjustment)."""
    data = request.get_json(silent=True)
    if not data or 'quantity_kg' not in data:
        return jsonify({'error': 'Thiếu trường quantity_kg'}), 400

    item = WarehouseInventory.query.filter_by(id=item_id, deleted=False).first()
    if not item:
        return jsonify({'error': 'Không tìm thấy mặt hàng'}), 404

    old_quantity = item.quantity_kg
    item.quantity_kg = float(data['quantity_kg'])
    
    # Create log for adjustment
    log = InventoryLog(
        item_id=item.id,
        transaction_type='adjustment',
        quantity=item.quantity_kg - old_quantity,
        notes=data.get('notes', 'Cập nhật thủ công')
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify(item.to_dict()), 200


@warehouse_bp.route('/import', methods=['POST'])
def import_inventory():
    """Nhập hàng vào kho và tạo log."""
    data = request.get_json(silent=True)
    if not data or 'item_id' not in data or 'quantity' not in data:
        return jsonify({'error': 'Thiếu thông tin item_id hoặc quantity'}), 400

    item = WarehouseInventory.query.filter_by(id=data['item_id'], deleted=False).first()
    if not item:
        return jsonify({'error': 'Không tìm thấy mặt hàng'}), 404

    quantity = float(data['quantity'])
    item.quantity_kg += quantity
    
    log = InventoryLog(
        item_id=item.id,
        transaction_type='import',
        quantity=quantity,
        unit_price=data.get('unit_price'),
        supplier=data.get('supplier'),
        notes=data.get('notes')
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'message': 'Nhập hàng thành công',
        'item': item.to_dict(),
        'log': log.to_dict()
    }), 201


@warehouse_bp.route('/logs', methods=['GET'])
def get_inventory_logs():
    """Lấy lịch sử nhập/xuất kho."""
    item_id = request.args.get('item_id', type=int)
    query = InventoryLog.query.filter_by(deleted=False)
    
    if item_id:
        query = query.filter_by(item_id=item_id)
        
    logs = query.order_by(InventoryLog.transaction_date.desc()).all()
    return jsonify([log.to_dict() for log in logs]), 200


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


@warehouse_bp.route('/consumption/overview', methods=['GET'])
def get_consumption_overview():
    """Lấy tổng quan tiêu thụ theo loại và thời gian."""
    type_filter = request.args.get('type', 'all')
    per_coop = {}
    total_by_type = {}

    if type_filter in ('all', 'feed'):
        coops = Coop.query.all()
        for coop in coops:
            s = db.session.query(db.func.coalesce(db.func.sum(FeedConsumption.quantity_kg), 0))\
                .filter(FeedConsumption.coop_id == coop.id).scalar()
            per_coop[str(coop.id)] = s
        total_by_type['feed'] = sum(per_coop.values())
    if type_filter in ('all', 'medicine'):
        med_per_coop = {}
        for coop in Coop.query.all():
            s = db.session.query(db.func.coalesce(db.func.sum(MedicineConsumption.quantity_kg), 0))\
                .filter(MedicineConsumption.coop_id == coop.id).scalar()
            med_per_coop[str(coop.id)] = s
        total_by_type['medicine'] = sum(med_per_coop.values())
        if type_filter == 'medicine':
            per_coop = med_per_coop

    per_coop['total'] = sum(per_coop.values())
    return jsonify({'per_coop': per_coop, 'total_by_type': total_by_type}), 200


@warehouse_bp.route('/consumption', methods=['GET'])
def get_consumption():
    """Lấy dữ liệu tiêu thụ theo chuồng, loại và thời gian."""
    coop_id = request.args.get('coop_id', type=int)
    type_filter = request.args.get('type', 'all')
    period = request.args.get('period', 'day')

    records = []
    if type_filter in ('all', 'feed'):
        query = FeedConsumption.query
        if coop_id:
            query = query.filter(FeedConsumption.coop_id == coop_id)
        query = query.order_by(FeedConsumption.recorded_date)
        for r in query.all():
            d = r.recorded_date
            if period == 'week':
                d = d - timedelta(days=d.weekday())
            elif period == 'month':
                d = d.replace(day=1)
            elif period == 'year':
                d = d.replace(month=1, day=1)

            records.append({
                'id': r.id,
                'coop_id': r.coop_id,
                'recorded_date': d.isoformat(),
                'quantity_kg': r.quantity_kg,
                'feed_item_category': 'feed',
            })

    daily_map = {}
    for rec in records:
        key = rec['recorded_date']
        if key not in daily_map:
            daily_map[key] = {'date': key, 'coops': {}}
        coop_key = str(rec['coop_id'])
        daily_map[key]['coops'][coop_key] = daily_map[key]['coops'].get(coop_key, 0) + rec['quantity_kg']

    daily = sorted(daily_map.values(), key=lambda x: x['date'])
    return jsonify({
        'daily': daily,
        'records': records,
        'total_records': len(records)
    }), 200


@warehouse_bp.route('/consumption/coop/<int:coop_id>', methods=['GET'])
def get_consumption_by_coop(coop_id):
    """Lấy dữ liệu tiêu thụ cho một chuồng cụ thể."""
    type_filter = request.args.get('type', 'all')
    period = request.args.get('period', 'day')

    records = []
    if type_filter in ('all', 'feed'):
        query = FeedConsumption.query.filter(FeedConsumption.coop_id == coop_id)
        query = query.order_by(FeedConsumption.recorded_date)
        for r in query.all():
            d = r.recorded_date
            if period == 'week':
                d = d - timedelta(days=d.weekday())
            elif period == 'month':
                d = d.replace(day=1)
            elif period == 'year':
                d = d.replace(month=1, day=1)

            records.append({
                'id': r.id,
                'coop_id': r.coop_id,
                'recorded_date': d.isoformat(),
                'quantity_kg': r.quantity_kg,
                'feed_item_category': 'feed',
            })

    daily_map = {}
    for rec in records:
        key = rec['recorded_date']
        if key not in daily_map:
            daily_map[key] = {'date': key, 'coops': {}}
        coop_key = str(rec['coop_id'])
        daily_map[key]['coops'][coop_key] = daily_map[key]['coops'].get(coop_key, 0) + rec['quantity_kg']

    daily = sorted(daily_map.values(), key=lambda x: x['date'])
    return jsonify({
        'daily': daily,
        'records': records,
        'total_records': len(records)
    }), 200


@warehouse_bp.route('/consumption/medicine/by-coop', methods=['GET'])
def get_medicine_consumption_by_coop():
    """Lấy dữ liệu tiêu thụ thuốc theo chuồng, gộp theo thời gian."""
    period = request.args.get('period', 'day')

    query = MedicineConsumption.query.order_by(MedicineConsumption.recorded_date)

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


@warehouse_bp.route('/consumption/medicine/overview', methods=['GET'])
def get_medicine_consumption_overview():
    """Lấy tổng quan tiêu thụ thuốc: mỗi chuồng tiêu thụ bao nhiêu kg."""
    coops = Coop.query.all()
    per_coop = {}
    total = 0.0
    for coop in coops:
        s = db.session.query(db.func.coalesce(db.func.sum(MedicineConsumption.quantity_kg), 0))\
            .filter(MedicineConsumption.coop_id == coop.id).scalar()
        per_coop[str(coop.id)] = s
        total += s
    return jsonify({'per_coop': per_coop, 'total': total}), 200
