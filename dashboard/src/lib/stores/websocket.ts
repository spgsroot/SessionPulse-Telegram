import { writable, type Writable } from 'svelte/store';

export interface WSMessage {
  type: string;
  [key: string]: unknown;
}

export const wsConnected: Writable<boolean> = writable(false);
export const wsMessages: Writable<WSMessage | null> = writable(null);

let ws: WebSocket | null = null;
let reconnectAttempts = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const MAX_RECONNECT = 10;
const RECONNECT_INTERVAL = 3000;

export function connectWS(path: string): void {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/api/v1/ws/${path}`;

  ws = new WebSocket(url);

  ws.onopen = () => {
    wsConnected.set(true);
    reconnectAttempts = 0;
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as WSMessage;
      wsMessages.set(data);
    } catch {
      // ignore parse errors
    }
  };

  ws.onclose = () => {
    wsConnected.set(false);
    if (reconnectAttempts < MAX_RECONNECT) {
      const delay = RECONNECT_INTERVAL * Math.min(reconnectAttempts + 1, 5);
      reconnectTimer = setTimeout(() => {
        reconnectAttempts++;
        connectWS(path);
      }, delay);
    }
  };

  ws.onerror = () => {
    ws?.close();
  };
}

export function disconnectWS(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectAttempts = MAX_RECONNECT;
  ws?.close();
  ws = null;
}
