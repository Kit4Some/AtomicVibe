import { useCallback, useEffect, useRef, useState } from "react";

export type WsStatus = "connecting" | "connected" | "disconnected" | "error";

interface UseWebSocketOptions {
  onMessage?: (data: string) => void;
  reconnect?: boolean;
  maxRetries?: number;
}

export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {}
) {
  const { onMessage, reconnect = true, maxRetries = 10 } = options;
  const [status, setStatus] = useState<WsStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!url) return;
    setStatus("connecting");

    let fullUrl: string;
    if (url.startsWith("ws")) {
      fullUrl = url;
    } else if (window.electronAPI) {
      // In Electron (file:// protocol), use absolute WS URL to backend
      fullUrl = `ws://127.0.0.1:18080${url}`;
    } else {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      fullUrl = `${protocol}//${window.location.host}${url}`;
    }

    const ws = new WebSocket(fullUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      onMessageRef.current?.(event.data);
    };

    ws.onclose = () => {
      setStatus("disconnected");
      wsRef.current = null;
      if (reconnect && retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current += 1;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };
  }, [url, reconnect, maxRetries]);

  const sendMessage = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const disconnect = useCallback(() => {
    retriesRef.current = maxRetries; // prevent reconnect
    wsRef.current?.close();
  }, [maxRetries]);

  useEffect(() => {
    connect();
    return () => {
      retriesRef.current = maxRetries;
      wsRef.current?.close();
    };
  }, [connect, maxRetries]);

  return { status, sendMessage, disconnect, reconnect: connect };
}
