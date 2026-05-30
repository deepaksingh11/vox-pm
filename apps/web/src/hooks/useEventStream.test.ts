import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEventStream } from "./useEventStream";

// Minimal WebSocket double: records instances, lets the test drive lifecycle callbacks.
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
}

describe("useEventStream reconnect", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("does not call onReconnect on the first successful open", () => {
    const onEvent = vi.fn();
    const onReconnect = vi.fn();
    renderHook(() => useEventStream("sid", onEvent, onReconnect));

    expect(MockWebSocket.instances).toHaveLength(1);
    MockWebSocket.instances[0].onopen?.();
    expect(onReconnect).not.toHaveBeenCalled();
  });

  it("reconnects after a close and fires onReconnect on the reconnected open", () => {
    const onEvent = vi.fn();
    const onReconnect = vi.fn();
    renderHook(() => useEventStream("sid", onEvent, onReconnect));

    const first = MockWebSocket.instances[0];
    first.onopen?.();

    // Close while active → a reconnect is scheduled, not immediate.
    first.onclose?.();
    expect(MockWebSocket.instances).toHaveLength(1);

    // First-attempt backoff is <= 1000*2^0 + 500 = 1500ms.
    vi.advanceTimersByTime(1600);
    expect(MockWebSocket.instances).toHaveLength(2);

    // The reconnected socket opening counts as a reconnect.
    MockWebSocket.instances[1].onopen?.();
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  it("backoff grows with consecutive failures", () => {
    renderHook(() => useEventStream("sid", vi.fn()));
    const first = MockWebSocket.instances[0];
    first.onopen?.();

    first.onclose?.();
    vi.advanceTimersByTime(1600); // attempt 1 fires
    expect(MockWebSocket.instances).toHaveLength(2);

    // Second consecutive close (no successful open) → attempt 2, delay ~2000-2500ms.
    MockWebSocket.instances[1].onclose?.();
    vi.advanceTimersByTime(1600); // not enough for attempt 2
    expect(MockWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1000); // now past attempt-2 delay
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it("routes incoming messages to onEvent", () => {
    const onEvent = vi.fn();
    renderHook(() => useEventStream("sid", onEvent));
    const ws = MockWebSocket.instances[0];
    ws.onopen?.();
    ws.onmessage?.({ data: JSON.stringify({ type: "task.created", ts: "t", data: {} }) });
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: "task.created" }),
    );
  });

  it("ignores malformed frames without throwing", () => {
    const onEvent = vi.fn();
    renderHook(() => useEventStream("sid", onEvent));
    const ws = MockWebSocket.instances[0];
    ws.onopen?.();
    expect(() => ws.onmessage?.({ data: "not json" })).not.toThrow();
    expect(onEvent).not.toHaveBeenCalled();
  });
});
