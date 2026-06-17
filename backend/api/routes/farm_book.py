"""
Farm Book Routes - API Sổ trang trại

Module này cung cấp các endpoint cho:
- CRUD lịch sử đàn gà (FlockHistory)
- CRUD nhập thức ăn (FeedImport)
- CRUD nhập thuốc (MedicineImport)
- Tổng hợp chi phí theo tháng
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, date, UTC
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models import db, Coop, FlockHistory, FeedImport, MedicineImport

farm_book_bp = Blueprint('farm_book', __name__)


def parse_date(val):
    if isinstance(val, str):
        return datetime.strptime(val, '%Y-%m-%d').date()
    return val


# ============================================================
# FLOCK HISTORY
# ============================================================

@farm_book_bp.route('/flock', methods=['GET'])
def get_flock_history():
    coop_id = request.args.get('coop_id', type=int)
    month = request.args.get('month')
    date_param = request.args.get('date')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    year = request.args.get('year')
    query = FlockHistory.query.filter_by(deleted=False)
    if coop_id:
        query = query.filter_by(coop_id=coop_id)
    if date_param:
        try:
            dv = datetime.strptime(date_param, '%Y-%m-%d').date()
            query = query.filter(FlockHistory.record_date == dv)
        except:
            pass
    elif date_from and date_to:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(FlockHistory.record_date >= df, FlockHistory.record_date <= dt)
        except:
            pass
    elif year:
        try:
            query = query.filter(db.extract('year', FlockHistory.record_date) == int(year))
        except:
            pass
    elif month:
        try:
            y, m = int(month[:4]), int(month[5:7])
            query = query.filter(db.extract('year', FlockHistory.record_date) == y,
                                 db.extract('month', FlockHistory.record_date) == m)
        except:
            pass
    records = query.order_by(FlockHistory.record_date.desc()).all()
    return jsonify({'items': [r.to_dict() for r in records]}), 200


@farm_book_bp.route('/flock', methods=['POST'])
def create_flock_history():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Không có dữ liệu'}), 400
    required = ['coop_id', 'record_date', 'total_count']
    for f in required:
        if f not in data:
            return jsonify({'error': f'Thiếu trường {f}'}), 400
    coop = Coop.query.get(data['coop_id'])
    if not coop:
        return jsonify({'error': 'Không tìm thấy chuồng'}), 404
    record = FlockHistory(
        coop_id=data['coop_id'],
        record_date=parse_date(data['record_date']),
        total_count=int(data['total_count']),
        dead_count=int(data.get('dead_count', 0)),
        sold_count=int(data.get('sold_count', 0)),
        notes=data.get('notes', ''),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@farm_book_bp.route('/flock/<int:id>', methods=['PUT'])
def update_flock_history(id):
    record = FlockHistory.query.filter_by(id=id, deleted=False).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy bản ghi'}), 404
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Không có dữ liệu'}), 400
    if 'record_date' in data:
        record.record_date = parse_date(data['record_date'])
    if 'total_count' in data:
        record.total_count = int(data['total_count'])
    if 'dead_count' in data:
        record.dead_count = int(data['dead_count'])
    if 'sold_count' in data:
        record.sold_count = int(data['sold_count'])
    if 'notes' in data:
        record.notes = data['notes']
    record.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify(record.to_dict()), 200


@farm_book_bp.route('/flock/<int:id>', methods=['DELETE'])
def delete_flock_history(id):
    record = FlockHistory.query.filter_by(id=id, deleted=False).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy bản ghi'}), 404
    record.deleted = True
    record.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'message': 'Đã xóa bản ghi'}), 200


# ============================================================
# FEED IMPORT
# ============================================================

@farm_book_bp.route('/feed', methods=['GET'])
def get_feed_imports():
    coop_id = request.args.get('coop_id', type=int)
    month = request.args.get('month')
    date_param = request.args.get('date')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    year = request.args.get('year')
    query = FeedImport.query.filter_by(deleted=False)
    if coop_id:
        query = query.filter_by(coop_id=coop_id)
    if date_param:
        try:
            dv = datetime.strptime(date_param, '%Y-%m-%d').date()
            query = query.filter(FeedImport.import_date == dv)
        except:
            pass
    elif date_from and date_to:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(FeedImport.import_date >= df, FeedImport.import_date <= dt)
        except:
            pass
    elif year:
        try:
            query = query.filter(db.extract('year', FeedImport.import_date) == int(year))
        except:
            pass
    elif month:
        try:
            y, m = int(month[:4]), int(month[5:7])
            query = query.filter(db.extract('year', FeedImport.import_date) == y,
                                 db.extract('month', FeedImport.import_date) == m)
        except:
            pass
    records = query.order_by(FeedImport.import_date.desc()).all()
    return jsonify({'items': [r.to_dict() for r in records]}), 200


@farm_book_bp.route('/feed', methods=['POST'])
def create_feed_import():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Không có dữ liệu'}), 400
    required = ['coop_id', 'import_date', 'feed_type', 'quantity_kg']
    for f in required:
        if f not in data:
            return jsonify({'error': f'Thiếu trường {f}'}), 400
    coop = Coop.query.get(data['coop_id'])
    if not coop:
        return jsonify({'error': 'Không tìm thấy chuồng'}), 404
    record = FeedImport(
        coop_id=data['coop_id'],
        import_date=parse_date(data['import_date']),
        feed_type=data['feed_type'],
        quantity_kg=float(data['quantity_kg']),
        supplier=data.get('supplier', ''),
        cost=float(data.get('cost', 0)),
        notes=data.get('notes', ''),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@farm_book_bp.route('/feed/<int:id>', methods=['PUT'])
def update_feed_import(id):
    record = FeedImport.query.filter_by(id=id, deleted=False).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy bản ghi'}), 404
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Không có dữ liệu'}), 400
    if 'import_date' in data:
        record.import_date = parse_date(data['import_date'])
    if 'feed_type' in data:
        record.feed_type = data['feed_type']
    if 'quantity_kg' in data:
        record.quantity_kg = float(data['quantity_kg'])
    if 'supplier' in data:
        record.supplier = data['supplier']
    if 'cost' in data:
        record.cost = float(data['cost'])
    if 'notes' in data:
        record.notes = data['notes']
    record.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify(record.to_dict()), 200


@farm_book_bp.route('/feed/<int:id>', methods=['DELETE'])
def delete_feed_import(id):
    record = FeedImport.query.filter_by(id=id, deleted=False).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy bản ghi'}), 404
    record.deleted = True
    record.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'message': 'Đã xóa bản ghi'}), 200


# ============================================================
# MEDICINE IMPORT
# ============================================================

@farm_book_bp.route('/medicine', methods=['GET'])
def get_medicine_imports():
    coop_id = request.args.get('coop_id', type=int)
    month = request.args.get('month')
    date_param = request.args.get('date')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    year = request.args.get('year')
    query = MedicineImport.query.filter_by(deleted=False)
    if coop_id:
        query = query.filter_by(coop_id=coop_id)
    if date_param:
        try:
            dv = datetime.strptime(date_param, '%Y-%m-%d').date()
            query = query.filter(MedicineImport.import_date == dv)
        except:
            pass
    elif date_from and date_to:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(MedicineImport.import_date >= df, MedicineImport.import_date <= dt)
        except:
            pass
    elif year:
        try:
            query = query.filter(db.extract('year', MedicineImport.import_date) == int(year))
        except:
            pass
    elif month:
        try:
            y, m = int(month[:4]), int(month[5:7])
            query = query.filter(db.extract('year', MedicineImport.import_date) == y,
                                 db.extract('month', MedicineImport.import_date) == m)
        except:
            pass
    records = query.order_by(MedicineImport.import_date.desc()).all()
    return jsonify({'items': [r.to_dict() for r in records]}), 200


@farm_book_bp.route('/medicine', methods=['POST'])
def create_medicine_import():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Không có dữ liệu'}), 400
    required = ['coop_id', 'import_date', 'medicine_name', 'quantity', 'unit']
    for f in required:
        if f not in data:
            return jsonify({'error': f'Thiếu trường {f}'}), 400
    coop = Coop.query.get(data['coop_id'])
    if not coop:
        return jsonify({'error': 'Không tìm thấy chuồng'}), 404
    record = MedicineImport(
        coop_id=data['coop_id'],
        import_date=parse_date(data['import_date']),
        medicine_name=data['medicine_name'],
        quantity=float(data['quantity']),
        unit=data['unit'],
        purpose=data.get('purpose', 'phòng'),
        supplier=data.get('supplier', ''),
        cost=float(data.get('cost', 0)),
        notes=data.get('notes', ''),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@farm_book_bp.route('/medicine/<int:id>', methods=['PUT'])
def update_medicine_import(id):
    record = MedicineImport.query.filter_by(id=id, deleted=False).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy bản ghi'}), 404
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Không có dữ liệu'}), 400
    if 'import_date' in data:
        record.import_date = parse_date(data['import_date'])
    if 'medicine_name' in data:
        record.medicine_name = data['medicine_name']
    if 'quantity' in data:
        record.quantity = float(data['quantity'])
    if 'unit' in data:
        record.unit = data['unit']
    if 'purpose' in data:
        record.purpose = data['purpose']
    if 'supplier' in data:
        record.supplier = data['supplier']
    if 'cost' in data:
        record.cost = float(data['cost'])
    if 'notes' in data:
        record.notes = data['notes']
    record.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify(record.to_dict()), 200


@farm_book_bp.route('/medicine/<int:id>', methods=['DELETE'])
def delete_medicine_import(id):
    record = MedicineImport.query.filter_by(id=id, deleted=False).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy bản ghi'}), 404
    record.deleted = True
    record.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({'message': 'Đã xóa bản ghi'}), 200


# ============================================================
# MONTHLY SUMMARY
# ============================================================

@farm_book_bp.route('/summary/monthly', methods=['GET'])
def get_monthly_summary():
    coop_id = request.args.get('coop_id', type=int)
    month = request.args.get('month')
    if not month:
        today = date.today()
        month = today.strftime('%Y-%m')
    try:
        y, m = int(month[:4]), int(month[5:7])
    except:
        return jsonify({'error': 'Tháng không hợp lệ'}), 400

    query_kwargs = {}
    coop_chicken_type = 'broiler'
    if coop_id:
        query_kwargs['coop_id'] = coop_id
        coop = Coop.query.get(coop_id)
        if coop:
            coop_chicken_type = coop.chicken_type

    # Feed cost
    feed_records = FeedImport.query.filter_by(deleted=False, **query_kwargs).filter(
        db.extract('year', FeedImport.import_date) == y,
        db.extract('month', FeedImport.import_date) == m,
    ).all()
    total_feed_cost = sum(r.cost for r in feed_records)
    total_feed_kg = sum(r.quantity_kg for r in feed_records)

    # Medicine cost
    med_records = MedicineImport.query.filter_by(deleted=False, **query_kwargs).filter(
        db.extract('year', MedicineImport.import_date) == y,
        db.extract('month', MedicineImport.import_date) == m,
    ).all()
    total_medicine_cost = sum(r.cost for r in med_records)

    # Flock stats
    flock_records = FlockHistory.query.filter_by(deleted=False, **query_kwargs).filter(
        db.extract('year', FlockHistory.record_date) == y,
        db.extract('month', FlockHistory.record_date) == m,
    ).all()
    total_dead = sum(r.dead_count for r in flock_records)
    total_sold = sum(r.sold_count for r in flock_records)

    total_flock_count = 0
    if flock_records:
        latest = flock_records[0]
        total_flock_count = latest.total_count

    return jsonify({
        'month': month,
        'coop_id': coop_id,
        'total_feed_cost': total_feed_cost,
        'total_feed_kg': total_feed_kg,
        'total_medicine_cost': total_medicine_cost,
        'total_cost': total_feed_cost + total_medicine_cost,
        'total_dead': total_dead,
        'total_sold': total_sold,
        'total_remaining': total_flock_count - total_dead - total_sold,
        'total_flock_count': total_flock_count,
        'coop_chicken_type': coop_chicken_type,
    }), 200
