import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { useSessionSocket } from "./ws";

class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  close() {
    this.onclose?.();
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useSessionSocket", () => {
  test("delivers parsed messages", () => {
    const onMessage = vi.fn();
    renderHook(() => useSessionSocket(7, onMessage));
    act(() => FakeSocket.instances[0].onmessage?.({ data: '{"type":"clock","sim_time":"2019-01-03T00:00:00Z","status":"running"}' }));
    expect(onMessage).toHaveBeenCalledWith({ type: "clock", sim_time: "2019-01-03T00:00:00Z", status: "running" });
  });

  test("socket reconnects with backoff", () => {
    const { result } = renderHook(() => useSessionSocket(7, () => {}));
    act(() => FakeSocket.instances[0].onopen?.());
    expect(result.current.status).toBe("open");

    act(() => FakeSocket.instances[0].onclose?.());
    expect(result.current.status).toBe("closed");
    act(() => vi.advanceTimersByTime(999));
    expect(FakeSocket.instances).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(FakeSocket.instances).toHaveLength(2);

    act(() => FakeSocket.instances[1].onclose?.());
    act(() => vi.advanceTimersByTime(1999));
    expect(FakeSocket.instances).toHaveLength(2);
    act(() => vi.advanceTimersByTime(1));
    expect(FakeSocket.instances).toHaveLength(3);
  });

  test("stops reconnecting after unmount", () => {
    const { unmount } = renderHook(() => useSessionSocket(7, () => {}));
    unmount();
    act(() => vi.advanceTimersByTime(60_000));
    expect(FakeSocket.instances).toHaveLength(1);
  });
});
