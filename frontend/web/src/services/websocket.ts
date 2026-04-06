export type SyncMessageType =
  | "schedule_updated"
  | "habit_checked_in"
  | "medicine_logged"
  | "journal_created"
  | "block_completed"
  | "pong";

export type SyncMessage = {
  type: SyncMessageType;
  data?: Record<string, unknown>;
  event_type?: string;
  event_id?: string;
  timestamp?: string;
};

type RealtimeClientOptions = {
  token: string;
  onMessage?: (message: SyncMessage) => void;
};

export class RealtimeWebSocketClient {
  private ws: WebSocket | null = null;
  private readonly token: string;
  private readonly onMessage?: (message: SyncMessage) => void;
  private reconnectAttempts = 0;
  private reconnectTimeout: number | null = null;
  private heartbeatInterval: number | null = null;
  private pongTimeout: number | null = null;
  private awaitingPong = false;
  private manuallyClosed = false;

  constructor(options: RealtimeClientOptions) {
    this.token = options.token;
    this.onMessage = options.onMessage;
  }

  connect() {
    this.manuallyClosed = false;
    this.openSocket();
  }

  disconnect() {
    this.manuallyClosed = true;
    this.stopHeartbeat();
    this.clearReconnectTimeout();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private openSocket() {
    const url = this.buildWebSocketURL(this.token);
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as SyncMessage;
        if (parsed.type === "pong") {
          this.awaitingPong = false;
          this.clearPongTimeout();
          return;
        }
        this.onMessage?.(parsed);
      } catch {
        // Ignore malformed payloads.
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      if (!this.manuallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
      }
    };
  }

  private scheduleReconnect() {
    this.clearReconnectTimeout();
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30_000);
    this.reconnectAttempts += 1;

    this.reconnectTimeout = window.setTimeout(() => {
      this.openSocket();
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = window.setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        return;
      }

      this.awaitingPong = true;
      this.ws.send(JSON.stringify({ type: "ping" }));

      this.clearPongTimeout();
      this.pongTimeout = window.setTimeout(() => {
        if (!this.awaitingPong) {
          return;
        }
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.close();
        }
      }, 10_000);
    }, 30_000);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval !== null) {
      window.clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    this.clearPongTimeout();
    this.awaitingPong = false;
  }

  private clearReconnectTimeout() {
    if (this.reconnectTimeout !== null) {
      window.clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  private clearPongTimeout() {
    if (this.pongTimeout !== null) {
      window.clearTimeout(this.pongTimeout);
      this.pongTimeout = null;
    }
  }

  private buildWebSocketURL(token: string): string {
    const customBase = import.meta.env.VITE_WS_BASE_URL as string | undefined;
    if (customBase) {
      const trimmed = customBase.replace(/\/$/, "");
      return `${trimmed}/ws/v1/sync?token=${encodeURIComponent(token)}`;
    }

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.host}/ws/v1/sync?token=${encodeURIComponent(token)}`;
  }
}
