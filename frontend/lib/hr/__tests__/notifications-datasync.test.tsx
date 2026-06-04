/**
 * Realtime -> data-sync wiring (recruitment overhaul, Phase 0).
 *
 * useHrNotifications must turn "data changed" WS events into an
 * onDataChange() call (the HR layout passes the data-sync bump), and must
 * ignore unrelated events. This is the path that carries one operator's
 * status change to another operator's open console.
 */
import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";

vi.mock("@/lib/auth", () => ({
  loadSession: () => ({ accessToken: "test-token" }),
}));
vi.mock("@/lib/env", () => ({
  env: { apiBaseUrl: "http://localhost:8000/api/v1" },
}));

import { useHrNotifications } from "@/lib/hr/notifications";

type MessageHandler = ((e: { data: string }) => void) | null;

class FakeWebSocket {
  static last: FakeWebSocket | null = null;
  onopen: (() => void) | null = null;
  onmessage: MessageHandler = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readonly url: string;
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.last = this;
  }
  close() {
    /* no-op for the test */
  }
}

beforeEach(() => {
  FakeWebSocket.last = null;
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function send(type: string) {
  FakeWebSocket.last?.onmessage?.({ data: JSON.stringify({ type, data: {} }) });
}

describe("useHrNotifications -> onDataChange", () => {
  test("fires onDataChange for candidate.status.changed", () => {
    const onDataChange = vi.fn();
    renderHook(() => useHrNotifications(onDataChange));
    expect(FakeWebSocket.last).not.toBeNull();

    send("candidate.status.changed");
    expect(onDataChange).toHaveBeenCalledTimes(1);
  });

  test("fires for offer.status.changed and candidate.application.new", () => {
    const onDataChange = vi.fn();
    renderHook(() => useHrNotifications(onDataChange));

    send("offer.status.changed");
    send("candidate.application.new");
    expect(onDataChange).toHaveBeenCalledTimes(2);
  });

  test("fires for interview.changed", () => {
    const onDataChange = vi.fn();
    renderHook(() => useHrNotifications(onDataChange));

    send("interview.changed");
    expect(onDataChange).toHaveBeenCalledTimes(1);
  });

  test("ignores unrelated events", () => {
    const onDataChange = vi.fn();
    renderHook(() => useHrNotifications(onDataChange));

    send("system.hello");
    send("some.unknown.event");
    expect(onDataChange).not.toHaveBeenCalled();
  });
});
