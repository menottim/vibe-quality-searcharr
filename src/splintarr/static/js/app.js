/**
 * Splintarr Dashboard JavaScript
 *
 * Provides client-side interactivity for the dashboard
 */

// Utility function for making API calls
async function apiCall(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {}),
        },
    };

    try {
        const response = await fetch(url, mergedOptions);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Request failed');
        }

        return { success: true, data };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// Show toast notification
function showNotification(message, type = 'error') {
    const existing = document.getElementById('toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.setAttribute('role', 'alert');
    toast.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;padding:0.75rem 1rem;border-radius:0.25rem;font-size:0.875rem;max-width:400px;box-shadow:0 4px 12px rgba(0,0,0,0.4);transition:opacity 0.3s;';

    if (type === 'error') {
        toast.style.background = 'rgba(255,85,85,0.15)';
        toast.style.border = '1px solid #ff5555';
        toast.style.color = '#ff5555';
    } else if (type === 'success') {
        toast.style.background = 'rgba(72,199,116,0.15)';
        toast.style.border = '1px solid #48c774';
        toast.style.color = '#48c774';
    } else {
        toast.style.background = 'rgba(212,160,23,0.15)';
        toast.style.border = '1px solid #D4A017';
        toast.style.color = '#D4A017';
    }

    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 5000);
}

// Confirm dialog
function confirmAction(message) {
    return window.confirm(message);
}

// Format datetime
function formatDateTime(dateString) {
    if (!dateString) return 'Never';

    const date = new Date(dateString);
    return date.toLocaleString();
}

// Format time ago
function formatTimeAgo(dateString) {
    if (!dateString) return 'Never';

    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + ' minutes ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + ' hours ago';
    if (seconds < 604800) return Math.floor(seconds / 86400) + ' days ago';

    return date.toLocaleDateString();
}

// Auto-refresh functionality
class AutoRefresh {
    constructor(callback, interval = 30000) {
        this.callback = callback;
        this.interval = interval;
        this.timerId = null;
    }

    start() {
        if (this.timerId) return;
        this.timerId = setInterval(this.callback, this.interval);
    }

    stop() {
        if (this.timerId) {
            clearInterval(this.timerId);
            this.timerId = null;
        }
    }

    restart() {
        this.stop();
        this.start();
    }
}

// Form validation helpers
function validatePassword(password) {
    const errors = [];

    if (password.length < 12) {
        errors.push('Password must be at least 12 characters long');
    }

    if (!/[a-z]/.test(password)) {
        errors.push('Password must contain at least one lowercase letter');
    }

    if (!/[A-Z]/.test(password)) {
        errors.push('Password must contain at least one uppercase letter');
    }

    if (!/\d/.test(password)) {
        errors.push('Password must contain at least one digit');
    }

    if (!/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/'`~;]/.test(password)) {
        errors.push('Password must contain at least one special character');
    }

    return errors;
}

function validateUsername(username) {
    const errors = [];

    if (username.length < 3 || username.length > 32) {
        errors.push('Username must be 3-32 characters long');
    }

    if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(username)) {
        errors.push('Username must start with a letter and contain only alphanumeric characters and underscore');
    }

    return errors;
}

// Sanitize a string for safe insertion into innerHTML
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// WebSocket real-time connection
var SplintarrWS = (function() {
    var socket = null;
    var handlers = {};
    var reconnectAttempts = 0;
    var MAX_RECONNECT = 3;
    var reconnectTimer = null;
    var fallbackActive = false;
    var _onConnected = null;
    var _onFallback = null;

    function connect() {
        if (socket && socket.readyState <= 1) return;
        var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(protocol + '//' + location.host + '/ws/live');

        socket.onopen = function() {
            reconnectAttempts = 0;
            fallbackActive = false;
            if (_onConnected) _onConnected();
        };

        socket.onmessage = function(event) {
            var msg;
            try { msg = JSON.parse(event.data); } catch (e) { return; }
            if (msg.type === 'auth.expired') {
                fetch('/api/auth/refresh', { method: 'POST' }).then(function() {
                    connect();
                }).catch(function() {
                    fallbackActive = true;
                    if (_onFallback) _onFallback();
                });
                return;
            }
            var fns = handlers[msg.type] || [];
            for (var i = 0; i < fns.length; i++) {
                try { fns[i](msg.data, msg.timestamp); } catch (e) { /* handler error */ }
            }
        };

        socket.onclose = function() {
            socket = null;
            reconnectAttempts++;
            if (reconnectAttempts <= MAX_RECONNECT) {
                var delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 30000);
                reconnectTimer = setTimeout(connect, delay);
            } else {
                fallbackActive = true;
                if (_onFallback) _onFallback();
                reconnectTimer = setTimeout(function() {
                    reconnectAttempts = 0;
                    connect();
                }, 60000);
            }
        };

        socket.onerror = function() {
            // onclose will fire after onerror
        };
    }

    function on(type, fn) {
        if (!handlers[type]) handlers[type] = [];
        handlers[type].push(fn);
    }

    function close() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (socket) socket.close();
        socket = null;
    }

    return {
        connect: connect,
        on: on,
        close: close,
        get connected() { return socket !== null && socket.readyState === 1; },
        get usingFallback() { return fallbackActive; },
        set onConnected(fn) { _onConnected = fn; },
        set onFallback(fn) { _onFallback = fn; },
    };
})();

// Export functions for use in templates
window.Splintarr = {
    ws: SplintarrWS,
    apiCall,
    showNotification,
    formatDateTime,
    formatTimeAgo,
    validatePassword,
    validateUsername,
    escapeHtml,
    AutoRefresh,
};

// Dashboard initialized
