/**
 * SSE-frame parser (Phase C-5).
 *
 * ``parseSseFrame`` is a pure decoder over the wire format the
 * ``/public/ai-assistant/ask-stream`` endpoint emits. Encoding it
 * here means the streaming hook in ``ask-pug-ai-button.tsx`` can
 * be tested end-to-end by stubbing only ``fetch`` — the parsing
 * logic is exercised standalone below.
 */
import { describe, expect, test } from "vitest";

import { parseSseFrame } from "@/lib/public-api-client";

describe("parseSseFrame", () => {
  test("decodes a delta frame with the data: prefix", () => {
    const parsed = parseSseFrame('data: {"type":"delta","text":"Hello"}');
    expect(parsed).toEqual({ type: "delta", text: "Hello" });
  });

  test("decodes a delta frame without the data: prefix", () => {
    const parsed = parseSseFrame('{"type":"delta","text":"Hello"}');
    expect(parsed).toEqual({ type: "delta", text: "Hello" });
  });

  test("decodes a done frame and normalises defaults", () => {
    const parsed = parseSseFrame(
      'data: {"type":"done","mode":"live","session_id":"abc","model_name":"gpt-4","was_fallback":false}'
    );
    expect(parsed).toEqual({
      type: "done",
      mode: "live",
      session_id: "abc",
      model_name: "gpt-4",
      was_fallback: false,
    });
  });

  test("fills in nulls when done payload omits optional fields", () => {
    const parsed = parseSseFrame('data: {"type":"done","mode":"mock"}');
    expect(parsed).toEqual({
      type: "done",
      mode: "mock",
      session_id: null,
      model_name: null,
      was_fallback: false,
    });
  });

  test("returns null for an unknown event type", () => {
    expect(parseSseFrame('data: {"type":"surprise"}')).toBeNull();
  });

  test("returns null for malformed JSON instead of crashing", () => {
    expect(parseSseFrame("data: { not json")).toBeNull();
  });

  test("returns null for an empty frame", () => {
    expect(parseSseFrame("")).toBeNull();
    expect(parseSseFrame("data: ")).toBeNull();
  });

  test("rejects a delta missing the text field", () => {
    expect(parseSseFrame('data: {"type":"delta"}')).toBeNull();
    expect(parseSseFrame('data: {"type":"delta","text":42}')).toBeNull();
  });
});
