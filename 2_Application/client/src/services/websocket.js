import { io } from 'socket.io-client';

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
  }

  static getInstance() {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  connect(onConnect) {
    if (this.socket?.connected) return;

    // Use the configured backend, else the same origin (so the Vite /socket.io
    // proxy is used in dev and deploys aren't pinned to localhost). Let
    // Socket.IO negotiate transports (polling → websocket) — forcing
    // 'websocket' only can fail against the threading-mode dev server.
    const WS_URL = import.meta.env.VITE_API_URL || window.location.origin;
    this.socket = io(WS_URL, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    });

    this.socket.on('connect', () => { if (onConnect) onConnect(); });
    this.socket.on('disconnect', () => {});
    this.socket.on('error', e => console.error('WS error:', e));

    const events = ['telemetry', 'activeUsers', 'issue', 'resolution', 'health', 'scenario_changed', 'scenario_status'];
    events.forEach(evt => {
      this.socket.on(evt, data => {
        (this.listeners.get(evt) || []).forEach(cb => cb(data));
      });
    });
  }

  on(event, callback) {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (!this.listeners.has(event)) return;
    const list = this.listeners.get(event);
    const i = list.indexOf(callback);
    if (i > -1) list.splice(i, 1);
  }

  subscribeToRegion(region) {
    if (this.socket?.connected) this.socket.emit('subscribe', { region });
  }

  disconnect() {
    if (this.socket) { this.socket.disconnect(); this.socket = null; }
  }
}

export { WebSocketService };
