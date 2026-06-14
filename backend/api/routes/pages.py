"""
Pages Blueprint - Chỉ giữ lại route trang chủ / cho index.html
"""

from flask import Blueprint, jsonify
from functools import partial


# ============================================================
# 1. KHỞI TẠO BLUEPRINT
# ============================================================

pages_bp = Blueprint('pages', __name__)


# ============================================================
# 2. TRANG CHỦ - DASHBOARD
# ============================================================

@pages_bp.route('/')
def index():
    """Trang chủ - Dashboard chính"""
    from flask import render_template
    return render_template('index.html')


@pages_bp.route('/login')
def login_page():
    """Trang đăng nhập (dùng chung index.html, login form hiển thị qua hash/state)"""
    from flask import render_template
    return render_template('index.html')


@pages_bp.route('/register')
def register_page():
    """Trang đăng ký (dùng chung index.html)"""
    from flask import render_template
    return render_template('index.html')


@pages_bp.route('/logout')
def logout_page():
    """Đăng xuất - chuyển hướng về trang chủ"""
    from flask import redirect, url_for
    return redirect(url_for('pages.index'))


# ============================================================
# 3. CÁC ROUTE CŨ TRẢ VỀ 404
# ============================================================

_OLD_ROUTES = {
    'coops':              '/coops',
    'coop_list_old':      '/coop-list',
    'device_list_old':    '/device-list',
    'camera_old':         '/camera',
    'coop_detail':        '/coops/<int:coop_id>',
    'devices':            '/devices',
    'device_detail':      '/devices/<int:device_id>',
    'cameras':            '/cameras',
    'camera_detail':      '/cameras/<coop>',
    'other':              '/other',
}

def _not_found():
    return jsonify({'error': 'Not found'}), 404

for _ep, _route in _OLD_ROUTES.items():
    pages_bp.add_url_rule(_route, endpoint=_ep, view_func=_not_found)


# ============================================================
# 4. ERROR HANDLERS
# ============================================================

@pages_bp.errorhandler(404)
def page_not_found(error):
    return jsonify({'error': 'Not found'}), 404


@pages_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500