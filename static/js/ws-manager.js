/**
 * WebSocket Manager - Real-time communication with Socket.io
 * Features: Auto-reconnect, data caching, fallback to REST API, performance optimized
 */

(function() {
    'use strict';

    class WebSocketManager {
        constructor(url) {
            this.url = url;
            this.socket = null;
            this.connected = false;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = 10;
            this.maxReconnectDelay = 30000; // 30 seconds
            this.callbacks = {};
            this.stateCache = {}; // Cache for data comparison to avoid unnecessary updates
            this.fallbackMode = true; // Start with fallback until connected
            this.eventTypes = [
                'dashboard:overview', 
                'coop:status', 
                'device:status', 
                'environment:update', 
                'coop:update', 
                'device:update', 
                'alert:new',
                'detection_result',    // Camera AI detection results
                'camera_status'        // Camera connection status
            ];
            this.cameraRooms = new Set(); // Track subscribed camera rooms
        }

        /**
         * Initialize WebSocket connection
         */
        connect() {
            if (this.socket) {
                this.socket.close();
            }

            try {
                this.socket = io(this.url, {
                    reconnection: false, // We handle reconnection manually
                    transports: ['websocket'],
                    timeout: 5000
                });

                this.socket.on('connect', () => {
                    console.log('✓ WebSocket connected to', this.url);
                    this.connected = true;
                    this.reconnectAttempts = 0;
                    this.fallbackMode = false;
                    this._emit('ws:connected', null);
                    
                    // Re-join camera rooms on reconnect
                    this.cameraRooms.forEach(deviceId => {
                        this.socket.emit('subscribe_camera', { device_id: deviceId });
                    });
                });

                this.socket.on('disconnect', (reason) => {
                    console.log('WebSocket disconnected:', reason);
                    this.connected = false;
                    this.fallbackMode = true;
                    this._emit('ws:disconnected', reason);
                    this._scheduleReconnect();
                });

                this.socket.on('connect_error', (error) => {
                    console.error('WebSocket connection error:', error.message);
                    this.connected = false;
                    this.fallbackMode = true;
                    this._scheduleReconnect();
                });

                // Register handlers for all event types
                this.eventTypes.forEach(event => {
                    this.socket.on(event, (data) => {
                        this._handleIncomingEvent(event, data);
                    });
                });

            } catch (error) {
                console.error('Failed to initialize WebSocket:', error);
                this.fallbackMode = true;
                this._scheduleReconnect();
            }
        }

        /**
         * Handle incoming WebSocket events with data comparison
         */
        _handleIncomingEvent(event, data) {
            // Compare with cached data to avoid unnecessary updates
            const cachedData = this.stateCache[event];
            if (this._isEqual(cachedData, data)) {
                return; // No change, skip update
            }

            // Update cache and emit event
            this.stateCache[event] = JSON.parse(JSON.stringify(data)); // Deep copy
            this._emit(event, data);
        }

        /**
         * Deep comparison of objects to check for changes
         */
        _isEqual(a, b) {
            if (a === b) return true;
            if (a == null || b == null) return false;
            if (typeof a !== typeof b) return false;

            if (typeof a === 'object') {
                const aKeys = Object.keys(a);
                const bKeys = Object.keys(b);
                if (aKeys.length !== bKeys.length) return false;
                
                return aKeys.every(key => this._isEqual(a[key], b[key]));
            }

            return false;
        }

        /**
         * Schedule reconnection with exponential backoff
         */
        _scheduleReconnect() {
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                console.log('Max reconnect attempts reached, staying in fallback mode');
                return;
            }

            const delay = Math.min(
                1000 * Math.pow(2, this.reconnectAttempts),
                this.maxReconnectDelay
            );
            
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
            this.reconnectAttempts++;

            setTimeout(() => {
                if (!this.connected) {
                    this.connect();
                }
            }, delay);
        }

        /**
         * Subscribe to an event
         * @param {string} event - Event name
         * @param {function} callback - Callback function
         */
        subscribe(event, callback) {
            if (!this.callbacks[event]) {
                this.callbacks[event] = [];
            }

            // Avoid duplicate callbacks
            if (!this.callbacks[event].includes(callback)) {
                this.callbacks[event].push(callback);
            }

            // If we have cached data for this event, trigger callback immediately
            if (this.stateCache[event] && this.connected) {
                callback(this.stateCache[event]);
            }
        }

        /**
         * Unsubscribe from an event
         * @param {string} event - Event name
         * @param {function} callback - Callback function to remove
         */
        unsubscribe(event, callback) {
            if (!this.callbacks[event]) return;

            if (callback) {
                this.callbacks[event] = this.callbacks[event].filter(cb => cb !== callback);
            } else {
                delete this.callbacks[event];
            }
        }

        /**
         * Subscribe to camera detection results
         * Joins the Socket.IO room for the specific camera
         * @param {number} deviceId - Camera device ID
         * @param {function} callback - Callback function with detection data
         */
        subscribeCamera(deviceId, callback) {
            const event = 'detection_result';
            const room = `camera_${deviceId}`;
            
            // Subscribe to the event
            this.subscribe(event, (data) => {
                // Filter by device_id
                if (data && data.device_id === deviceId) {
                    callback(data);
                }
            });

            // Join the camera room if connected
            if (this.connected && this.socket) {
                this.socket.emit('subscribe_camera', { device_id: deviceId });
                this.cameraRooms.add(deviceId);
            }

            // Return unsubscribe function
            return () => this.unsubscribeCamera(deviceId, callback);
        }

        /**
         * Unsubscribe from camera detection results
         * Leaves the Socket.IO room for the specific camera
         * @param {number} deviceId - Camera device ID
         * @param {function} callback - Callback function to remove
         */
        unsubscribeCamera(deviceId, callback) {
            const event = 'detection_result';
            this.unsubscribe(event, callback);

            // Leave the camera room if connected
            if (this.connected && this.socket) {
                this.socket.emit('unsubscribe_camera', { device_id: deviceId });
                this.cameraRooms.delete(deviceId);
            }
        }

        /**
         * Subscribe to camera status changes
         * @param {number} deviceId - Camera device ID
         * @param {function} callback - Callback function with status data
         */
        subscribeCameraStatus(deviceId, callback) {
            const event = 'camera_status';
            this.subscribe(event, (data) => {
                if (data && data.device_id === deviceId) {
                    callback(data);
                }
            });
            return () => this.unsubscribe(event, callback);
        }

        /**
         * Emit event to all subscribers
         */
        _emit(event, data) {
            const callbacks = this.callbacks[event] || [];
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in callback for event ${event}:`, error);
                }
            });
        }

        /**
         * Fallback to REST API when WebSocket is disconnected
         * @param {string} endpoint - API endpoint to fetch
         * @returns {Promise} - API response
         */
        async fallbackFetch(endpoint) {
            if (window.apiFetch) {
                return await window.apiFetch(endpoint);
            }
            throw new Error('apiFetch not available for fallback');
        }

        /**
         * Get current connection status
         */
        getStatus() {
            return {
                connected: this.connected,
                fallbackMode: this.fallbackMode,
                reconnectAttempts: this.reconnectAttempts
            };
        }

        /**
         * Disconnect WebSocket
         */
        disconnect() {
            if (this.socket) {
                this.socket.close();
                this.socket = null;
            }
            this.connected = false;
            this.fallbackMode = true;
        }
    }

    // Initialize WebSocket manager when DOM is loaded
    document.addEventListener('DOMContentLoaded', () => {
        // Create global instance
        window.wsManager = new WebSocketManager('ws://localhost:5000');
        
        // Connect automatically
        window.wsManager.connect();

        // Make event types available globally
        window.WS_EVENTS = {
            DASHBOARD_OVERVIEW: 'dashboard:overview',
            COOP_STATUS: 'coop:status',
            COOP_DELETED: 'coop:deleted',
            DEVICE_STATUS: 'device:status',
            ENVIRONMENT_UPDATE: 'environment:update',
            COOP_UPDATE: 'coop:update',
            DEVICE_UPDATE: 'device:update',
            ALERT_NEW: 'alert:new',
            WS_CONNECTED: 'ws:connected',
            WS_DISCONNECTED: 'ws:disconnected'
        };

        console.log('✓ WebSocket Manager initialized');
    });

})();
