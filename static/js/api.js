/**
 * API Helper - Kết nối Frontend với Backend Flask
 * 
 * Sử dụng: Nhúng vào HTML và sử dụng các object: authAPI, dashboardAPI, coopsAPI, devicesAPI, cameraAPI
 * 
 * Ví dụ:
 *   const token = await authAPI.login('admin', 'admin123');
 *   const coops = await coopsAPI.getAll();
 * 
 * Real-time: Sử dụng WebSocket (Socket.io) với fallback về REST API
 *   window.wsManager.subscribe(WINDOW.WS_EVENTS.DASHBOARD_OVERVIEW, (data) => { ... });
 */

(function() {
    'use strict';

    // ============================================================
    // 1. CẤU HÌNH
    // ============================================================
    
    window.API_BASE_URL = '/api';


    // ============================================================
    // 2. TOKEN MANAGEMENT
    // ============================================================

    /**
     * Lấy JWT token từ localStorage
     * @returns {string|null} Token hoặc null nếu không có
     */
    window.getAuthToken = function() {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        if (token === 'null' || token === 'undefined' || token === '') {
            return null;
        }
        return token;
    };

    /**
     * Lưu JWT token vào localStorage
     * @param {string} token - JWT token
     * @param {boolean} remember - Có nhớ không (localStorage vs sessionStorage)
     */
    window.setAuthToken = function(token, remember = false) {
        if (remember) {
            localStorage.setItem('token', token);
        } else {
            sessionStorage.setItem('token', token);
        }
    };

    /**
     * Xóa JWT token
     */
    window.removeAuthToken = function() {
        localStorage.removeItem('token');
        sessionStorage.removeItem('token');
    };

    /**
     * Kiểm tra đã đăng nhập chưa
     * @returns {boolean}
     */
    window.isAuthenticated = function() {
        return !!window.getAuthToken();
    };


    // ============================================================
    // 3. API WRAPPER VỚI ERROR HANDLING
    // ============================================================

    /**
     * Wrapper cho fetch API
     * Tự động thêm Authorization header và xử lý lỗi
     * 
     * @param {string} endpoint - API endpoint (sau /api/)
     * @param {object} options - Options cho fetch
     * @returns {Promise} - Response hoặc throw error
     */
    window.apiFetch = async function(endpoint, options = {}) {
        const token = window.getAuthToken();
        
        // Default headers
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Thêm Authorization header nếu có token
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // Merge options
        const fetchOptions = {
            ...options,
            headers
        };

        try {
            const response = await fetch(`${window.API_BASE_URL}${endpoint}`, fetchOptions);
            
            // Xử lý 401 (Unauthorized) hoặc 422 (Unprocessable Entity - Token hỏng)
            if (response.status === 401 || response.status === 422) {
                const errorData = await response.json().catch(() => ({}));
                console.error('Auth error:', response.status, errorData);
                window.removeAuthToken();
                // Chuyển về trang login nếu không phải đang ở trang login/register
                if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
                    window.location.href = '/login';
                }
                throw new Error(errorData.message || 'Phiên đăng nhập hết hạn hoặc không hợp lệ');
            }

            // Xử lý các mã lỗi khác
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `HTTP Error ${response.status}`);
            }

            // Parse JSON response
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();

        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    };


    // ============================================================
    // 4. AUTH API
    // ============================================================

    window.authAPI = {
        /**
         * Đăng nhập
         * @param {string} username 
         * @param {string} password 
         * @returns {object} { token, user }
         */
        login: async function(username, password) {
            const data = await window.apiFetch('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            if (data.access_token) {
                window.setAuthToken(data.access_token, true);
            }
            
            return data;
        },

        /**
         * Đăng ký
         * @param {string} username 
         * @param {string} email 
         * @param {string} password 
         * @returns {object}
         */
        register: async function(username, email, password) {
            return await window.apiFetch('/auth/register', {
                method: 'POST',
                body: JSON.stringify({ username, email, password })
            });
        },

        /**
         * Đăng xuất
         */
        logout: function() {
            window.removeAuthToken();
            window.location.href = '/login';
        },

        /**
         * Lấy thông tin user hiện tại
         * @returns {object}
         */
        getMe: async function() {
            return await window.apiFetch('/auth/me');
        }
    };


    // ============================================================
    // 5. DASHBOARD API (WebSocket + Fallback)
    // ============================================================

    window.dashboardAPI = {
        /**
         * Lấy tổng quan dashboard (WebSocket real-time hoặc fallback REST)
         * @param {function} callback - Callback khi có dữ liệu mới từ WebSocket
         * @returns {Promise|null} - Promise nếu dùng fallback, null nếu đăng ký WebSocket thành công
         */
        subscribeOverview: function(callback) {
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(window.WS_EVENTS.DASHBOARD_OVERVIEW, callback);
                return null; // WebSocket mode
            } else {
                // Fallback to REST API
                return window.dashboardAPI.getOverview().then(data => {
                    callback(data);
                    return data;
                });
            }
        },

        /**
         * Lấy tổng quan dashboard (REST API với fallback)
         * @returns {object}
         */
        getOverview: async function() {
            return await window.apiFetch('/dashboard');
        },

        /**
         * Lấy thống kê chi tiết
         * @returns {object}
         */
        getStats: async function() {
            return await window.apiFetch('/dashboard/stats');
        },

        /**
         * Lấy danh sách cảnh báo
         * @returns {array}
         */
        getAlerts: async function() {
            return await window.apiFetch('/dashboard/alerts');
        },

        /**
         * Lấy hoạt động gần đây
         * @returns {array}
         */
        getRecentActivities: async function() {
            return await window.apiFetch('/dashboard/recent-activities');
        }
    };


    // ============================================================
    // 6. COOPS API (WebSocket + Fallback)
    // ============================================================

    window.coopsAPI = {
        /**
         * Đăng ký nhận cập nhật trạng thái tất cả chuồng qua WebSocket
         * @param {function} callback - Callback với dữ liệu chuồng
         * @returns {function|null} - Hàm unsubscribe hoặc null
         */
        subscribeStatus: function(callback) {
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(window.WS_EVENTS.COOP_STATUS, callback);
                return () => window.wsManager.unsubscribe(window.WS_EVENTS.COOP_STATUS, callback);
            } else {
                // Fallback: fetch once
                window.coopsAPI.getAll().then(data => callback(data));
                return null;
            }
        },

        /**
         * Đăng ký nhận cập nhật cho một chuồng cụ thể
         * @param {number} id - ID chuồng
         * @param {function} callback - Callback với dữ liệu chuồng
         */
        subscribeCoop: function(id, callback) {
            const event = `${window.WS_EVENTS.COOP_UPDATE}:${id}`;
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(event, callback);
                return () => window.wsManager.unsubscribe(event, callback);
            } else {
                window.coopsAPI.getOne(id).then(data => callback(data));
                return null;
            }
        },

        /**
         * Đăng ký nhận cập nhật môi trường cho một chuồng
         * @param {number} id - ID chuồng
         * @param {function} callback - Callback với dữ liệu môi trường
         */
        subscribeEnvironment: function(id, callback) {
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(window.WS_EVENTS.ENVIRONMENT_UPDATE, (data) => {
                    if (data.coop_id === id || data.coopId === id) {
                        callback(data);
                    }
                });
                return () => window.wsManager.unsubscribe(window.WS_EVENTS.ENVIRONMENT_UPDATE, callback);
            } else {
                window.coopsAPI.getEnvironment(id).then(data => callback(data));
                return null;
            }
        },

        /**
         * Lấy danh sách tất cả chuồng (REST fallback)
         * @returns {array}
         */
        getAll: async function() {
            return await window.apiFetch('/coops');
        },

        /**
         * Lấy danh sách chuồng có camera
         * @returns {array}
         */
        getWithCamera: async function() {
            return await window.apiFetch('/coops?has_camera=1');
        },

        /**
         * Lấy thông tin một chuồng (REST fallback)
         * @param {number} id - ID của chuồng
         * @returns {object}
         */
        getOne: async function(id) {
            return await window.apiFetch(`/coops/${id}`);
        },

        /**
         * Tạo chuồng mới
         * @param {object} coopData 
         * @returns {object}
         */
        create: async function(coopData) {
            return await window.apiFetch('/coops', {
                method: 'POST',
                body: JSON.stringify(coopData)
            });
        },

        /**
         * Cập nhật chuồng
         * @param {number} id 
         * @param {object} coopData 
         * @returns {object}
         */
        update: async function(id, coopData) {
            return await window.apiFetch(`/coops/${id}`, {
                method: 'PUT',
                body: JSON.stringify(coopData)
            });
        },

        /**
         * Xóa chuồng
         * @param {number} id 
         */
        delete: async function(id) {
            return await window.apiFetch(`/coops/${id}`, {
                method: 'DELETE'
            });
        },

        /**
         * Lấy thiết bị trong chuồng
         * @param {number} id 
         * @returns {array}
         */
        getDevices: async function(id) {
            return await window.apiFetch(`/coops/${id}/devices`);
        },

        /**
         * Lấy dữ liệu môi trường hiện tại (REST fallback)
         * @param {number} id 
         * @returns {object}
         */
        getEnvironment: async function(id) {
            return await window.apiFetch(`/coops/${id}/environment`);
        },

        /**
         * Lấy lịch sử dữ liệu môi trường
         * @param {number} id 
         * @param {number} limit 
         * @returns {array}
         */
        getHistory: async function(id, limit = 24) {
            return await window.apiFetch(`/coops/${id}/history?limit=${limit}`);
        }
    };


    // ============================================================
    // 7. DEVICES API (WebSocket + Fallback)
    // ============================================================

    window.devicesAPI = {
        /**
         * Đăng ký nhận cập nhật trạng thái thiết bị qua WebSocket
         * @param {function} callback - Callback với dữ liệu thiết bị
         * @returns {function|null} - Hàm unsubscribe hoặc null
         */
        subscribeStatus: function(callback) {
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(window.WS_EVENTS.DEVICE_STATUS, callback);
                return () => window.wsManager.unsubscribe(window.WS_EVENTS.DEVICE_STATUS, callback);
            } else {
                // Fallback: fetch once
                window.devicesAPI.getAll().then(data => callback(data));
                return null;
            }
        },

        /**
         * Đăng ký nhận cập nhật cho một thiết bị cụ thể
         * @param {number} id - ID thiết bị
         * @param {function} callback - Callback với dữ liệu thiết bị
         */
        subscribeDevice: function(id, callback) {
            const event = `${window.WS_EVENTS.DEVICE_UPDATE}:${id}`;
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(event, callback);
                return () => window.wsManager.unsubscribe(event, callback);
            } else {
                window.devicesAPI.getOne(id).then(data => callback(data));
                return null;
            }
        },

        /**
         * Lấy danh sách thiết bị (REST fallback)
         * @returns {array}
         */
        getAll: async function() {
            return await window.apiFetch('/devices/public/all');
        },

        /**
         * Lấy thông tin một thiết bị (REST fallback)
         * @param {number} id 
         * @returns {object}
         */
        getOne: async function(id) {
            return await window.apiFetch(`/devices/public/${id}`);
        },

        /**
         * Bật/tắt thiết bị
         * @param {number} id 
         * @returns {object}
         */
        toggle: async function(id) {
            return await window.apiFetch(`/devices/${id}/toggle`, {
                method: 'POST'
            });
        },

        /**
         * Gán thiết bị vào chuồng
         * @param {number} id 
         * @param {number} coopId 
         * @returns {object}
         */
        assign: async function(id, coopId) {
            return await window.apiFetch(`/devices/${id}/assign`, {
                method: 'POST',
                body: JSON.stringify({ coop_id: coopId })
            });
        },

        /**
         * Cập nhật tên thiết bị
         * @param {number} id 
         * @param {string} name 
         * @returns {object}
         */
        updateName: async function(id, name) {
            return await window.apiFetch(`/devices/${id}/name`, {
                method: 'PATCH',
                body: JSON.stringify({ name })
            });
        },

        /**
         * Tạo thiết bị mới
         * @param {object} deviceData 
         * @returns {object}
         */
        create: async function(deviceData) {
            return await window.apiFetch('/devices', {
                method: 'POST',
                body: JSON.stringify(deviceData)
            });
        },

        /**
         * Xóa thiết bị
         * @param {number} id 
         */
        delete: async function(id) {
            return await window.apiFetch(`/devices/${id}`, {
                method: 'DELETE'
            });
        }
    };


    // ============================================================
    // 8. CAMERA API
    // ============================================================

    window.cameraAPI = {
        /**
         * Lấy danh sách camera
         * @returns {array}
         */
        getAll: async function() {
            return await window.apiFetch('/camera');
        },

        /**
         * Lấy thông tin một camera
         * @param {number} id 
         * @returns {object}
         */
        getOne: async function(id) {
            return await window.apiFetch(`/camera/${id}`);
        },

        /**
         * Lấy camera theo chuồng
         * @param {number} coopId 
         * @returns {array}
         */
        getByCoop: async function(coopId) {
            return await window.apiFetch(`/camera/coop/${coopId}`);
        },

        /**
         * Đọc đường dẫn video từ file text
         * @returns {object} { video_path }
         */
        getVideoPath: async function() {
            return await window.apiFetch('/camera/video-path');
        },

        /**
         * Đọc tất cả đường dẫn video từ file text
         * @returns {object} { video_paths }
         */
        getVideoPaths: async function() {
            return await window.apiFetch('/camera/video-paths');
        },

        /**
         * Ghi đường dẫn video vào file text
         * @param {string} videoPath - Đường dẫn video
         * @returns {object}
         */
        setVideoPath: async function(videoPath) {
            return await window.apiFetch('/camera/video-path', {
                method: 'PUT',
                body: JSON.stringify({ video_path: videoPath })
            });
        },

        /**
         * Tạo recording từ đường dẫn trong file text
         * @param {number} deviceId - ID camera
         * @param {object} data - { name, duration, file_size }
         * @returns {object}
         */
        createRecordingFromFile: async function(deviceId, data = {}) {
            return await window.apiFetch(`/camera/${deviceId}/recordings/from-file`, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        /**
         * Chạy AI detection trên file media
         * @param {string} filePath - Đường dẫn file
         * @param {number} [coopId] - ID chuồng
         * @param {number} [deviceId] - ID camera
         * @returns {object} Kết quả detection
         */
        detectDisease: async function(filePath, coopId, deviceId) {
            const body = { file_path: filePath };
            if (coopId) body.coop_id = coopId;
            if (deviceId) body.device_id = deviceId;
            return await window.apiFetch('/ai/detect', {
                method: 'POST',
                body: JSON.stringify(body)
            });
        },

        /**
         * Lấy kết quả AI detection
         * @param {object} [options] - { coop_id, device_id, limit }
         * @returns {Array} Danh sách kết quả
         */
        getDetections: async function(options = {}) {
            const params = new URLSearchParams();
            if (options.coop_id) params.set('coop_id', options.coop_id);
            if (options.device_id) params.set('device_id', options.device_id);
            if (options.limit) params.set('limit', options.limit);
            const qs = params.toString();
            return await window.apiFetch('/ai/detections' + (qs ? '?' + qs : ''));
        },

        /**
         * Đăng ký nhận kết quả detection real-time qua WebSocket
         * @param {number} deviceId - Camera device ID
         * @param {function} callback - Callback với dữ liệu detection
         * @returns {function|null} - Hàm unsubscribe hoặc null
         */
        subscribeDetection: function(deviceId, callback) {
            if (window.wsManager && window.wsManager.connected) {
                return window.wsManager.subscribeCamera(deviceId, callback);
            } else {
                // Fallback: poll every 10 seconds (matching backend interval)
                const interval = setInterval(() => {
                    window.cameraAPI.getCameraDetection(deviceId).then(data => callback(data)).catch(console.error);
                }, 10000);
                return () => clearInterval(interval);
            }
        },

        /**
         * Đăng ký nhận trạng thái camera real-time qua WebSocket
         * @param {number} deviceId - Camera device ID
         * @param {function} callback - Callback với dữ liệu status
         * @returns {function|null} - Hàm unsubscribe hoặc null
         */
        subscribeCameraStatus: function(deviceId, callback) {
            if (window.wsManager && window.wsManager.connected) {
                return window.wsManager.subscribeCameraStatus(deviceId, callback);
            } else {
                return null;
            }
        },

        /**
         * Lấy detection mới nhất cho camera (REST fallback)
         * @param {number} deviceId - Camera device ID
         * @returns {object} Detection data
         */
        getCameraDetection: async function(deviceId) {
            return await window.apiFetch(`/ai/detections?device_id=${deviceId}&limit=1`);
        },

    };


    // ============================================================
    // 9. ALERTS API (WebSocket + Fallback)
    // ============================================================

    window.alertsAPI = {
        /**
         * Đăng ký nhận cảnh báo mới qua WebSocket
         * @param {function} callback - Callback với dữ liệu cảnh báo mới
         * @returns {function|null} - Hàm unsubscribe hoặc null
         */
        subscribeNewAlerts: function(callback) {
            if (window.wsManager && window.wsManager.connected) {
                window.wsManager.subscribe(window.WS_EVENTS.ALERT_NEW, callback);
                return () => window.wsManager.unsubscribe(window.WS_EVENTS.ALERT_NEW, callback);
            } else {
                // Fallback: poll every 30 seconds
                const interval = setInterval(() => {
                    window.alertsAPI.getAll().then(data => callback(data));
                }, 30000);
                return () => clearInterval(interval);
            }
        },

        /**
         * Lấy danh sách cảnh báo (REST fallback)
         * @param {object} filters - { is_resolved, level, coop_id }
         * @returns {array}
         */
        getAll: async function(filters = {}) {
            const queryString = new URLSearchParams(filters).toString();
            const endpoint = queryString ? `/alerts?${queryString}` : '/alerts';
            return await window.apiFetch(endpoint);
        },

        /**
         * Đánh dấu cảnh báo đã xử lý
         * @param {number} id 
         * @returns {object}
         */
        resolve: async function(id) {
            return await window.apiFetch(`/alerts/${id}/resolve`, {
                method: 'PUT'
            });
        }
    };


    // ============================================================
    // 10. UTILITY FUNCTIONS
    // ============================================================

    /**
     * Kiểm tra và chuyển hướng nếu chưa đăng nhập
     */
    window.requireAuth = function() {
        if (!window.isAuthenticated()) {
            window.location.href = '/login';
            return false;
        }
        return true;
    };

    /**
     * Hiển thị toast notification
     * @param {string} message 
     * @param {string} type - 'success', 'error', 'warning', 'info'
     */
    window.showToast = function(message, type = 'info') {
        // Tạo toast element
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.textContent = message;
        
        // Style inline (có thể custom trong CSS)
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 9999;
            animation: slideIn 0.3s ease;
            background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : '#3b82f6'};
        `;
        
        document.body.appendChild(toast);
        
        // Auto remove sau 3s
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    /**
     * Format ngày giờ
     * @param {string|Date} date 
     * @returns {string}
     */
    window.formatDateTime = function(date) {
        const d = new Date(date);
        return d.toLocaleString('vi-VN', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    // ============================================================
    // 11. WINDOW.API BRIDGE (cho index.html dashboard)
    // ============================================================
    // Ánh xạ các method mà index.html gọi sang các API object đã có

    window.API = {
        getDashboard: async function() {
            return await window.apiFetch('/dashboard/public');
        },

        getFeedItems: async function() {
            return await window.apiFetch('/warehouse/feed');
        },

        updateFeedItem: async function(id, quantityKg) {
            return await window.apiFetch('/warehouse/feed/' + id, {
                method: 'PUT',
                body: JSON.stringify({ quantity_kg: quantityKg })
            });
        },

        getCoops: async function() {
            var raw = await window.apiFetch('/coops/public');
            var list = Array.isArray(raw) ? raw : (raw.value || []);
            var allDevices = [];
            try {
                var devRes = await window.apiFetch('/devices/public/all');
                allDevices = Array.isArray(devRes) ? devRes : (devRes.value || []);
            } catch (e) { /* ignore */ }
            var deviceCounts = {}, onlineCounts = {};
            allDevices.forEach(function(d) {
                if (d.coop_id) {
                    deviceCounts[d.coop_id] = (deviceCounts[d.coop_id] || 0) + 1;
                    if (d.status === 'online') onlineCounts[d.coop_id] = (onlineCounts[d.coop_id] || 0) + 1;
                }
            });
            return list.map(function(c) {
                return {
                    id: c.id,
                    name: c.name,
                    location: c.location || '',
                    chickens: c.current_count || 0,
                    capacity: c.capacity || 0,
                    temp: c.environment ? c.environment.temperature : null,
                    humidity: c.environment ? c.environment.humidity : null,
                    feedLevel: c.environment ? Math.round(c.environment.feed_level) : 50,
                    waterLevel: c.environment ? Math.round(c.environment.water_level) : 50,
                    status: c.status || 'active',
                    alert: c.emergency_alert || false,
                    deviceCount: deviceCounts[c.id] || 0,
                    onlineDeviceCount: onlineCounts[c.id] || 0
                };
            });
        },

        getCoopDevices: async function(coopId) {
            var raw = await window.apiFetch('/coops/public/' + coopId + '/devices');
            return Array.isArray(raw) ? raw : (raw.value || []);
        },

        getUnconnectedDevices: async function() {
            var raw = await window.apiFetch('/devices/public/unconnected/available');
            return Array.isArray(raw) ? raw : (raw.value || []);
        },

        attachToCoop: async function(deviceId, coopId) {
            return await window.apiFetch('/devices/public/attach-to-coop', {
                method: 'POST',
                body: JSON.stringify({ device_id: deviceId, coop_id: coopId })
            });
        },

        removeDeviceFromCoop: async function(id) {
            return await window.apiFetch('/devices/public/remove-from-coop/' + id, {
                method: 'DELETE'
            });
        },

        getAllDevices: async function() {
            var raw = await window.apiFetch('/devices/public/all');
            return Array.isArray(raw) ? raw : (raw.value || []);
        },

        toggleDevice: async function(deviceId) {
            return await window.apiFetch('/devices/public/' + deviceId + '/toggle', {
                method: 'POST'
            });
        },

        deleteDevice: async function(deviceId) {
            return await window.apiFetch('/devices/public/' + deviceId, {
                method: 'DELETE'
            });
        },

        getItems: async function(type) {
            try {
                return await window.apiFetch('/warehouse/feed?type=' + (type || 'all'));
            } catch (e) {
                console.warn('getItems not available:', e);
                return { items: [] };
            }
        },

        getFeedConsumptionByCoops: async function(period) {
            try {
                return await window.apiFetch('/warehouse/consumption/feed/by-coop?period=' + (period || 'day'));
            } catch (e) {
                console.warn('getFeedConsumptionByCoops not available:', e);
                return { daily: [] };
            }
        },

        getMedicineConsumptionByCoops: async function(period) {
            try {
                return await window.apiFetch('/warehouse/consumption/medicine/by-coop?period=' + (period || 'day'));
            } catch (e) {
                console.warn('getMedicineConsumptionByCoops not available:', e);
                return { daily: [] };
            }
        },

        getVideoPaths: async function() {
            return await window.apiFetch('/camera/video-paths');
        }
    };

    console.log('✓ api.js loaded - API helper ready');

})();