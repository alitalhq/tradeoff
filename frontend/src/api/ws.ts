import { useEffect, useRef, useState } from "react";
import { devUserId } from "./client";
import type { WsSchema } from "./ws-types";

export type ServerMessage = WsSchema;
export type SocketStatus = "connecting" | "open" | "closed";

const BASE_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;

function socketUrl(sessionId: number): string {
  const { protocol, host } = window.location;
  const scheme = protocol === "https:" ? "wss" : "ws";
  const userId = import.meta.env.DEV ? devUserId() : null;
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return `${scheme}://${host}/ws/sessions/${sessionId}${query}`;
}

/** Subscribe to a session's live messages; reconnects with 1s, 2s, 4s… backoff capped at 30s. */
export function useSessionSocket(
  sessionId: number,
  onMessage: (message: ServerMessage) => void,
): { status: SocketStatus } {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const handler = useRef(onMessage);
  handler.current = onMessage;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let disposed = false;

    const connect = () => {
      setStatus("connecting");
      socket = new WebSocket(socketUrl(sessionId));
      socket.onopen = () => {
        attempt = 0;
        setStatus("open");
      };
      socket.onmessage = (event) => handler.current(JSON.parse(event.data) as ServerMessage);
      socket.onclose = () => {
        if (disposed) return;
        setStatus("closed");
        const delay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
        attempt += 1;
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [sessionId]);

  return { status };
}
