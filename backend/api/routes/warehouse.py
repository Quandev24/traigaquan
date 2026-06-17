"""
Warehouse Routes - API quản lý kho thức ăn

Module này cung cấp các endpoint public cho:
- Lấy danh sách thức ăn trong kho
- Cập nhật số lượng thức ăn
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from sqlalchemy import extract
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Coop, WarehouseInventory, FeedConsumption, MedicineConsumption, FeedImport

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


@warehouse_bp.route('/feed/<int:item_id>/status', methods=['PUT'])
def toggle_item_status(item_id):
    """Chuyển trạng thái active / depreciated (khấu hao)."""
    item = WarehouseInventory.query.filter_by(id=item_id, deleted=False).first()
    if not item:
        return jsonify({'error': 'Không tìm thấy mặt hàng'}), 404

    data = request.get_json(silent=True) or {}
    if item.status == 'depreciated':
        item.status = 'active'
        item.depreciation_reason = None
    else:
        item.status = 'depreciated'
        item.depreciation_reason = data.get('reason')
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


@warehouse_bp.route('/balance-flow', methods=['GET'])
def get_balance_flow():
    """Cân bằng kho: tồn đầu + nhập - tiêu thụ - khấu hao = tồn cuối."""
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)

    imports = db.session.query(db.func.coalesce(db.func.sum(FeedImport.quantity_kg), 0))\
        .filter(extract('year', FeedImport.import_date) == year)\
        .filter(extract('month', FeedImport.import_date) == month)\
        .scalar()

    consumption = db.session.query(db.func.coalesce(db.func.sum(FeedConsumption.quantity_kg), 0))\
        .filter(extract('year', FeedConsumption.recorded_date) == year)\
        .filter(extract('month', FeedConsumption.recorded_date) == month)\
        .scalar()

    depreciation = db.session.query(db.func.coalesce(db.func.sum(WarehouseInventory.quantity_kg), 0))\
        .filter(WarehouseInventory.status == 'depreciated')\
        .filter(extract('year', WarehouseInventory.updated_at) == year)\
        .filter(extract('month', WarehouseInventory.updated_at) == month)\
        .scalar()

    closing = db.session.query(db.func.coalesce(db.func.sum(WarehouseInventory.quantity_kg), 0))\
        .filter(WarehouseInventory.status == 'active')\
        .filter(WarehouseInventory.deleted == False)\
        .scalar()

    opening = round(closing + consumption + depreciation - imports, 2)

    return jsonify({
        'period': f'{year}-{month:02d}',
        'opening_balance': opening,
        'imports': round(imports, 2),
        'consumption': round(consumption, 2),
        'depreciation': round(depreciation, 2),
        'closing_balance': round(closing, 2),
    }), 200


@warehouse_bp.route('/unit-price-trend', methods=['GET'])
def get_unit_price_trend():
    """Biến động giá nhập thức ăn theo thời gian."""
    months = request.args.get('months', type=int, default=12)

    today = datetime.now()
    start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    for _ in range(months - 1):
        start_date = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1)

    rows = db.session.query(
        extract('year', FeedImport.import_date).label('yr'),
        extract('month', FeedImport.import_date).label('mo'),
        db.func.sum(FeedImport.quantity_kg).label('total_kg'),
        db.func.sum(FeedImport.cost).label('total_cost'),
        db.func.group_concat(db.distinct(FeedImport.supplier)).label('suppliers_raw'),
    ).filter(
        FeedImport.import_date >= start_date.date(),
        FeedImport.deleted == False,
    ).group_by('yr', 'mo').order_by('yr', 'mo').all()

    trend = []
    for r in rows:
        total_kg = float(r.total_kg or 0)
        total_cost = float(r.total_cost or 0)
        avg_price = round(total_cost / total_kg, 0) if total_kg > 0 else 0
        suppliers = list(set(s.strip() for s in (r.suppliers_raw or '').split(',') if s.strip()))
        trend.append({
            'period': f'{int(r.yr)}-{int(r.mo):02d}',
            'avg_price': avg_price,
            'total_kg': round(total_kg, 2),
            'total_cost': round(total_cost, 2),
            'suppliers': suppliers,
        })

    return jsonify({'trend': trend}), 200


@warehouse_bp.route('/consumption/efficiency', methods=['GET'])
def get_consumption_efficiency():
    """Hiệu quả tiêu thụ: thực tế vs định mức theo chuồng."""
    period = request.args.get('period', 'month')
    coop_id = request.args.get('coop_id', type=int)
    type_filter = request.args.get('type', 'feed')

    feed_rates = {'broiler': 0.12, 'layer': 0.10, 'chick': 0.05}

    today = datetime.now().date()
    if period == 'day':
        date_from = today
        days = 1
    elif period == 'week':
        date_from = today - timedelta(days=today.weekday())
        days = 7
    elif period == 'year':
        date_from = today.replace(month=1, day=1)
        days = (today - date_from).days + 1
    else:
        date_from = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        days = (next_month - date_from).days

    coop_query = Coop.query.filter(Coop.deleted == False)
    if coop_id:
        coop_query = coop_query.filter(Coop.id == coop_id)

    coops = coop_query.all()
    result = []

    if type_filter == 'medicine':
        for coop in coops:
            actual = db.session.query(db.func.coalesce(db.func.sum(MedicineConsumption.quantity_kg), 0))\
                .filter(MedicineConsumption.coop_id == coop.id)\
                .filter(MedicineConsumption.recorded_date >= date_from)\
                .filter(MedicineConsumption.recorded_date <= today)\
                .scalar()
            result.append({
                'coop_id': coop.id,
                'coop_name': coop.name,
                'chicken_type': coop.chicken_type,
                'chicken_count': coop.current_count or 0,
                'actual': round(actual, 2),
                'expected': 0,
                'days': days,
            })
    else:
        for coop in coops:
            rate = feed_rates.get(coop.chicken_type, 0.10)
            chicken_count = coop.current_count or 0
            expected = round(chicken_count * rate * days, 2)
            actual = db.session.query(db.func.coalesce(db.func.sum(FeedConsumption.quantity_kg), 0))\
                .filter(FeedConsumption.coop_id == coop.id)\
                .filter(FeedConsumption.recorded_date >= date_from)\
                .filter(FeedConsumption.recorded_date <= today)\
                .scalar()
            result.append({
                'coop_id': coop.id,
                'coop_name': coop.name,
                'chicken_type': coop.chicken_type,
                'chicken_count': chicken_count,
                'actual': round(actual, 2),
                'expected': expected,
                'days': days,
            })

    return jsonify({
        'period': period,
        'date_from': date_from.isoformat(),
        'date_to': today.isoformat(),
        'coops': result,
    }), 200
