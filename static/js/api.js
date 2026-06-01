/**
 * API Helper - Kết nối Frontend với Backend Flask
 *
 * Sử dụng: Nhúng vào HTML và sử dụng object: window.API (công khai) hoặc các API object riêng
 *
 * Các object có sẵn:
 *   window.API          - Gộp tất cả method (ưu tiên dùng)
 *   window.authAPI      - Xác thực (JWT)
 *   window.publicAPI    - API công khai (không cần JWT)
 *   window.warehouseAPI - Kho hàng
 *   window.cameraAPI    - Camera (JWT)
 *   window.coopsAPI     - Chuồng (JWT)
 *   window.devicesAPI   - Thiết bị (JWT)
 *   window.dashboardAPI - Dashboard (JWT)
 *   window.alertsAPI    - Cảnh báo (JWT)
 */

(function () {
  'use strict';

  // ============================================================
  // 1. CẤU HÌNH
  // ============================================================

  window.API_BASE_URL = '/api';

  // ============================================================
  // 2. TOKEN MANAGEMENT
  // ============================================================

  window.getAuthToken = function () {
    var token = localStorage.getItem('token') || sessionStorage.getItem('token');
    if (token === 'null' || token === 'undefined' || token === '') return null;
    return token;
  };

  window.setAuthToken = function (token, remember) {
    remember = remember || false;
    if (remember) localStorage.setItem('token', token);
    else sessionStorage.setItem('token', token);
  };

  window.removeAuthToken = function () {
    localStorage.removeItem('token');
    sessionStorage.removeItem('token');
  };

  window.isAuthenticated = function () {
    return !!window.getAuthToken();
  };

  // ============================================================
  // 3. API FETCH WRAPPER (có JWT)
  // ============================================================

  window.apiFetch = async function (endpoint, options) {
    options = options || {};
    var token = window.getAuthToken();
    var headers = { 'Content-Type': 'application/json' };
    if (options.headers) Object.assign(headers, options.headers);
    if (token) headers['Authorization'] = 'Bearer ' + token;
    var fetchOptions = { headers: headers };
    if (options.method) fetchOptions.method = options.method;
    if (options.body) fetchOptions.body = options.body;
    try {
      var response = await fetch(window.API_BASE_URL + endpoint, fetchOptions);
      if (response.status === 401 || response.status === 422) {
        var errData = {};
        try { errData = await response.json(); } catch (e) {}
        console.error('Auth error:', response.status, errData);
        window.removeAuthToken();
        if (
          window.location.pathname.indexOf('/login') === -1 &&
          window.location.pathname.indexOf('/register') === -1
        ) {
          window.location.href = '/login';
        }
        throw new Error(errData.message || 'Phiên đăng nhập hết hạn');
      }
      if (!response.ok) {
        var errData2 = {};
        try { errData2 = await response.json(); } catch (e) {}
        throw new Error(errData2.message || 'HTTP Error ' + response.status);
      }
      var ct = response.headers.get('content-type');
      if (ct && ct.indexOf('application/json') !== -1) return await response.json();
      return await response.text();
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  };

  // ============================================================
  // 4. PUBLIC FETCH (không JWT, dùng cho publicAPI)
  // ============================================================

  async function publicFetch(endpoint, options) {
    options = options || {};
    var headers = { 'Content-Type': 'application/json' };
    if (options.headers) Object.assign(headers, options.headers);
    var fetchOptions = { headers: headers };
    if (options.method) fetchOptions.method = options.method;
    if (options.body) fetchOptions.body = options.body;
    try {
      var response = await fetch(window.API_BASE_URL + endpoint, fetchOptions);
      if (!response.ok) {
        var errMsg = 'HTTP Error ' + response.status;
        try {
          var errData = await response.json();
          if (errData.message) errMsg = errData.message;
        } catch (e) {}
        throw new Error(errMsg);
      }
      var ct = response.headers.get('content-type');
      if (ct && ct.indexOf('application/json') !== -1) return await response.json();
      return await response.text();
    } catch (error) {
      console.error('Public API Error:', error);
      throw error;
    }
  }

  // ============================================================
  // 5. AUTH API (JWT)
  // ============================================================

  window.authAPI = {
    login: async function (username, password) {
      var data = await window.apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username, password: password }),
      });
      if (data.access_token) window.setAuthToken(data.access_token, true);
      return data;
    },
    register: async function (username, email, password) {
      return await window.apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ username: username, email: email, password: password }),
      });
    },
    logout: function () {
      window.removeAuthToken();
      window.location.href = '/login';
    },
    getMe: async function () {
      return await window.apiFetch('/auth/me');
    },
  };

  // ============================================================
  // 6. DASHBOARD API (JWT)
  // ============================================================

  window.dashboardAPI = {
    subscribeOverview: function (callback) {
      if (window.wsManager && window.wsManager.connected) {
        window.wsManager.subscribe(window.WS_EVENTS.DASHBOARD_OVERVIEW, callback);
        return null;
      }
      return window.dashboardAPI.getOverview().then(function (data) { callback(data); return data; });
    },
    getOverview: async function () { return await window.apiFetch('/dashboard'); },
    getStats: async function () { return await window.apiFetch('/dashboard/stats'); },
    getAlerts: async function () { return await window.apiFetch('/dashboard/alerts'); },
    getRecentActivities: async function () { return await window.apiFetch('/dashboard/recent-activities'); },
  };

  // ============================================================
  // 7. COOPS API (JWT)
  // ============================================================

  window.coopsAPI = {
    subscribeStatus: function (callback) {
      if (window.wsManager && window.wsManager.connected) {
        window.wsManager.subscribe(window.WS_EVENTS.COOP_STATUS, callback);
        return function () { window.wsManager.unsubscribe(window.WS_EVENTS.COOP_STATUS, callback); };
      }
      window.coopsAPI.getAll().then(function (data) { callback(data); });
      return null;
    },
    subscribeCoop: function (id, callback) {
      var event = window.WS_EVENTS.COOP_UPDATE + ':' + id;
      if (window.wsManager && window.wsManager.connected) {
        window.wsManager.subscribe(event, callback);
        return function () { window.wsManager.unsubscribe(event, callback); };
      }
      window.coopsAPI.getOne(id).then(function (data) { callback(data); });
      return null;
    },
    getAll: async function () { return await window.apiFetch('/coops'); },
    getWithCamera: async function () { return await window.apiFetch('/coops?has_camera=1'); },
    getOne: async function (id) { return await window.apiFetch('/coops/' + id); },
    create: async function (data) {
      return await window.apiFetch('/coops', { method: 'POST', body: JSON.stringify(data) });
    },
    update: async function (id, data) {
      return await window.apiFetch('/coops/' + id, { method: 'PUT', body: JSON.stringify(data) });
    },
    delete: async function (id) {
      return await window.apiFetch('/coops/' + id, { method: 'DELETE' });
    },
    getDevices: async function (id) { return await window.apiFetch('/coops/' + id + '/devices'); },
    getEnvironment: async function (id) { return await window.apiFetch('/coops/' + id + '/environment'); },
    getHistory: async function (id, limit) {
      limit = limit || 24;
      return await window.apiFetch('/coops/' + id + '/history?limit=' + limit);
    },
  };

  // ============================================================
  // 8. DEVICES API (JWT)
  // ============================================================

  window.devicesAPI = {
    subscribeStatus: function (callback) {
      if (window.wsManager && window.wsManager.connected) {
        window.wsManager.subscribe(window.WS_EVENTS.DEVICE_STATUS, callback);
        return function () { window.wsManager.unsubscribe(window.WS_EVENTS.DEVICE_STATUS, callback); };
      }
      window.devicesAPI.getAll().then(function (data) { callback(data); });
      return null;
    },
    subscribeDevice: function (id, callback) {
      var event = window.WS_EVENTS.DEVICE_UPDATE + ':' + id;
      if (window.wsManager && window.wsManager.connected) {
        window.wsManager.subscribe(event, callback);
        return function () { window.wsManager.unsubscribe(event, callback); };
      }
      window.devicesAPI.getOne(id).then(function (data) { callback(data); });
      return null;
    },
    getAll: async function () { return await window.apiFetch('/devices/public/all'); },
    getOne: async function (id) { return await window.apiFetch('/devices/public/' + id); },
    toggle: async function (id) {
      return await window.apiFetch('/devices/' + id + '/toggle', { method: 'POST' });
    },
    assign: async function (id, coopId) {
      return await window.apiFetch('/devices/' + id + '/assign', {
        method: 'POST',
        body: JSON.stringify({ coop_id: coopId }),
      });
    },
    updateName: async function (id, name) {
      return await window.apiFetch('/devices/' + id + '/name', {
        method: 'PATCH',
        body: JSON.stringify({ name: name }),
      });
    },
    create: async function (data) {
      return await window.apiFetch('/devices', { method: 'POST', body: JSON.stringify(data) });
    },
    delete: async function (id) {
      return await window.apiFetch('/devices/' + id, { method: 'DELETE' });
    },
  };

  // ============================================================
  // 9. CAMERA API (JWT)
  // ============================================================

  window.cameraAPI = {
    getAll: async function () { return await window.apiFetch('/camera'); },
    getOne: async function (id) { return await window.apiFetch('/camera/' + id); },
    getByCoop: async function (coopId) { return await window.apiFetch('/camera/coop/' + coopId); },
    getVideoPath: async function () { return await window.apiFetch('/camera/video-path'); },
    setVideoPath: async function (videoPath) {
      return await window.apiFetch('/camera/video-path', {
        method: 'PUT',
        body: JSON.stringify({ video_path: videoPath }),
      });
    },
    createRecordingFromFile: async function (deviceId, data) {
      data = data || {};
      return await window.apiFetch('/camera/' + deviceId + '/recordings/from-file', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
  };

  // ============================================================
  // 10. ALERTS API (JWT)
  // ============================================================

  window.alertsAPI = {
    subscribeNewAlerts: function (callback) {
      if (window.wsManager && window.wsManager.connected) {
        window.wsManager.subscribe(window.WS_EVENTS.ALERT_NEW, callback);
        return function () { window.wsManager.unsubscribe(window.WS_EVENTS.ALERT_NEW, callback); };
      }
      var interval = setInterval(function () {
        window.alertsAPI.getAll().then(function (data) { callback(data); });
      }, 30000);
      return function () { clearInterval(interval); };
    },
    getAll: async function (filters) {
      filters = filters || {};
      var qs = new URLSearchParams(filters).toString();
      return await window.apiFetch(qs ? '/alerts?' + qs : '/alerts');
    },
    resolve: async function (id) {
      return await window.apiFetch('/alerts/' + id + '/resolve', { method: 'PUT' });
    },
  };

  // ============================================================
  // 11. PUBLIC API (không JWT - dùng cho trang dashboard)
  // ============================================================

  window.publicAPI = {
    // Dashboard
    getDashboard: async function () {
      return await publicFetch('/dashboard/public');
    },

    // Coops
    getCoops: async function () {
      return await publicFetch('/coops/public');
    },
    getCoopDetail: async function (id) {
      return await publicFetch('/coops/public/' + id);
    },
    getCoopDevices: async function (coopId) {
      return await publicFetch('/coops/public/' + coopId + '/devices');
    },
    getCoopEnvironment: async function (coopId) {
      return await publicFetch('/coops/public/' + coopId + '/environment');
    },

    // Devices
    getAllDevices: async function () {
      var data = await publicFetch('/devices/public/all');
      return data.value || data || [];
    },
    getDeviceDetail: async function (id) {
      return await publicFetch('/devices/public/' + id);
    },
    deleteDevice: async function (deviceId) {
      await publicFetch('/devices/public/' + deviceId, { method: 'DELETE' });
      return true;
    },
    toggleDevice: async function (deviceId) {
      return await publicFetch('/devices/public/' + deviceId + '/toggle', { method: 'POST' });
    },
    updateDevice: async function (deviceId, data) {
      return await publicFetch('/devices/public/' + deviceId, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    getUnconnectedDevices: async function () {
      return await publicFetch('/devices/public/unconnected/available');
    },
    attachToCoop: async function (deviceId, coopId) {
      return await publicFetch('/devices/public/attach-to-coop', {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId, coop_id: coopId }),
      });
    },
    addDeviceToCoop: async function (deviceId, coopId) {
      return await publicFetch('/devices/public/add-to-coop', {
        method: 'POST',
        body: JSON.stringify({ device_id: deviceId, coop_id: coopId }),
      });
    },
    removeDeviceFromCoop: async function (deviceId) {
      return await publicFetch('/devices/public/remove-from-coop/' + deviceId, { method: 'DELETE' });
    },
    createUnconnectedDevice: async function (data) {
      return await publicFetch('/devices/public/unconnected', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    deleteUnconnectedDevice: async function (id) {
      return await publicFetch('/devices/public/unconnected/' + id, { method: 'DELETE' });
    },
    getDeviceStatusStats: async function () {
      return await publicFetch('/devices/status-stats');
    },
    getRecentDevices: async function () {
      return await publicFetch('/devices/public/recent');
    },

    // Warehouse (public)
    getFeedItems: async function () {
      return await publicFetch('/warehouse/feed');
    },
    updateFeedItem: async function (id, quantityKg) {
      return await publicFetch('/warehouse/feed/' + id, {
        method: 'PUT',
        body: JSON.stringify({ quantity_kg: quantityKg }),
      });
    },

    // Camera (public - video-path only)
    getCameraVideoPaths: async function () {
      return await publicFetch('/camera/video-paths-public');
    },
  };

  // ============================================================
  // 12. WAREHOUSE API (JWT - full CRUD)
  // ============================================================

  window.warehouseAPI = {
    getFeedItems: async function () {
      return await publicFetch('/warehouse/feed');
    },
    updateFeedItem: async function (id, quantityKg) {
      return await publicFetch('/warehouse/feed/' + id, {
        method: 'PUT',
        body: JSON.stringify({ quantity_kg: quantityKg }),
      });
    },
    getItems: async function (itemType) {
      var params = itemType && itemType !== 'all' ? '?item_type=' + itemType : '';
      return await publicFetch('/warehouse' + params);
    },
    getConsumption: async function (coopId, itemType) {
      var params = new URLSearchParams();
      if (coopId) params.set('coop_id', coopId);
      if (itemType && itemType !== 'all') params.set('item_type', itemType);
      return await publicFetch('/warehouse/consumption?' + params.toString());
    },
    getConsumptionOverview: async function (itemType) {
      var params = itemType && itemType !== 'all' ? '?item_type=' + itemType : '';
      return await publicFetch('/warehouse/consumption/overview' + params);
    },
    getConsumptionByCoop: async function (coopId, itemType) {
      var params = itemType && itemType !== 'all' ? '?item_type=' + itemType : '';
      return await publicFetch('/warehouse/consumption/coop/' + coopId + params);
    },
  };

  // ============================================================
  // 13. UTILITY FUNCTIONS
  // ============================================================

  window.requireAuth = function () {
    if (!window.isAuthenticated()) {
      window.location.href = '/login';
      return false;
    }
    return true;
  };

  window.showToast = function (message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.className = 'toast-notification toast-' + type;
    toast.textContent = message;
    toast.style.cssText =
      'position:fixed;top:20px;right:20px;padding:12px 24px;border-radius:8px;color:white;font-weight:500;z-index:9999;' +
      'animation:slideIn 0.3s ease;background:' +
      (type === 'success' ? '#22c55e' : type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : '#3b82f6');
    document.body.appendChild(toast);
    setTimeout(function () {
      toast.style.animation = 'slideOut 0.3s ease';
      setTimeout(function () { toast.remove(); }, 300);
    }, 3000);
  };

  window.formatDateTime = function (date) {
    var d = new Date(date);
    return d.toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // ============================================================
  // 14. UNIFIED API OBJECT (dùng cho index.html)
  // ============================================================

  window.API = {};

  // Copy publicAPI methods
  var pubKeys = Object.keys(window.publicAPI);
  for (var i = 0; i < pubKeys.length; i++) {
    window.API[pubKeys[i]] = window.publicAPI[pubKeys[i]];
  }

  // Copy warehouseAPI methods (không ghi đè)
  var whKeys = Object.keys(window.warehouseAPI);
  for (var j = 0; j < whKeys.length; j++) {
    if (!window.API[whKeys[j]]) {
      window.API[whKeys[j]] = window.warehouseAPI[whKeys[j]];
    }
  }

  // Copy selected cameraAPI methods (chỉ thêm nếu có JWT)
  if (window.isAuthenticated()) {
    window.API.getCameras = window.cameraAPI.getAll;
    window.API.getCamerasByCoop = window.cameraAPI.getByCoop;
    window.API.getCamera = window.cameraAPI.getOne;
  }

  // Copy selected feed-schedule methods (JWT)
  if (window.isAuthenticated()) {
    window.API.getFeedSchedules = async function () {
      return await window.apiFetch('/feed-schedule');
    };
    window.API.createFeedSchedule = async function (data) {
      return await window.apiFetch('/feed-schedule', { method: 'POST', body: JSON.stringify(data) });
    };
    window.API.deleteFeedSchedule = async function (id) {
      return await window.apiFetch('/feed-schedule/' + id, { method: 'DELETE' });
    };
    window.API.executeFeedSchedule = async function (id) {
      return await window.apiFetch('/feed-schedule/' + id + '/execute', { method: 'POST' });
    };
  }

  console.log('api.js loaded - API helper ready');
})();
