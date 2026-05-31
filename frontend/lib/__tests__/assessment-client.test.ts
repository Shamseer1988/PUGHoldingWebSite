/**
 * Vitest coverage for the HR Phase 2 candidate-facing assessment
 * helpers in ``lib/public-api-client.ts``.
 *
 * We mock ``fetch`` directly — the helpers are thin wrappers that
 * mostly care about getting the URL, method, headers and body right,
 * so a stubbed fetch lets us verify the contract end-to-end without
 * spinning up the backend.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  fetchAssessment,
  PublicApiError,
  submitAssessment,
  verifyAssessment,
} from "@/lib/public-api-client";


function mockFetchOnce(body: unknown, init: { status?: number } = {}) {
  const status = init.status ?? 200;
  return vi.spyOn(global, "fetch").mockResolvedValueOnce(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}


describe("verifyAssessment", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("POSTs to the token-scoped URL with the identity value", async () => {
    const fetchSpy = mockFetchOnce({
      session_token: "abc.def.ghi",
      matched_field: "email",
      opened_at: "2026-05-30T22:00:00Z",
      submit_deadline: null,
    });

    const result = await verifyAssessment("tok-xyz", "alice@example.com");

    const [calledUrl, calledInit] = fetchSpy.mock.calls[0]!;
    expect(String(calledUrl)).toContain("/assessments/tok-xyz/verify");
    const init = calledInit as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({ identity_value: "alice@example.com" }),
    );
    expect(result.session_token).toBe("abc.def.ghi");
    expect(result.matched_field).toBe("email");
  });

  test("URL-encodes the token so a slash-bearing token can't escape the path", async () => {
    const fetchSpy = mockFetchOnce({
      session_token: "x",
      matched_field: "mobile",
      opened_at: "2026-05-30T22:00:00Z",
      submit_deadline: null,
    });
    await verifyAssessment("tok/with/slashes", "+97455551234");
    const [calledUrl] = fetchSpy.mock.calls[0]!;
    expect(String(calledUrl)).toContain("/assessments/tok%2Fwith%2Fslashes/verify");
  });

  test("throws PublicApiError on 401, surfacing the detail message", async () => {
    mockFetchOnce({ detail: "Identity check failed. Please try again." }, { status: 401 });
    await expect(
      verifyAssessment("tok-bad", "wrong@example.com"),
    ).rejects.toMatchObject({
      message: "Identity check failed. Please try again.",
      status: 401,
    });
  });
});


describe("fetchAssessment", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("sends the bearer token and returns the form bundle", async () => {
    const bundle = {
      title: "Smoke",
      instructions: null,
      time_limit_minutes: 15,
      questions: [],
      candidate_name: "Alice",
      candidate_email: "alice@example.com",
      submit_deadline: null,
    };
    const fetchSpy = mockFetchOnce(bundle);
    const data = await fetchAssessment("sess.tok.123");
    const [calledUrl, calledInit] = fetchSpy.mock.calls[0]!;
    expect(String(calledUrl)).toContain("/assessments/me");
    const init = calledInit as RequestInit;
    expect(init.method).toBe("GET");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer sess.tok.123");
    expect(data.title).toBe("Smoke");
  });

  test("401 surfaces as PublicApiError with the detail string", async () => {
    mockFetchOnce({ detail: "Session does not match this invite." }, { status: 401 });
    await expect(fetchAssessment("stale.tok")).rejects.toBeInstanceOf(
      PublicApiError,
    );
  });
});


describe("submitAssessment", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("POSTs answers wrapped in an envelope", async () => {
    const ack = {
      score: 2,
      max_score: 3,
      passed: false,
      submitted_at: "2026-05-30T22:05:00Z",
    };
    const fetchSpy = mockFetchOnce(ack);
    const answers = [
      { question_id: 1, selected_choice_ids: [10, 11] },
      { question_id: 2, selected_choice_ids: [] },
    ];
    const result = await submitAssessment("sess.tok.123", answers);
    const [calledUrl, calledInit] = fetchSpy.mock.calls[0]!;
    expect(String(calledUrl)).toContain("/assessments/me/submit");
    const init = calledInit as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ answers }));
    expect(result.score).toBe(2);
    expect(result.passed).toBe(false);
  });

  test("409 (resubmit) surfaces with the message intact", async () => {
    mockFetchOnce({ detail: "Already submitted." }, { status: 409 });
    await expect(
      submitAssessment("sess.tok.123", []),
    ).rejects.toMatchObject({ message: "Already submitted.", status: 409 });
  });
});
