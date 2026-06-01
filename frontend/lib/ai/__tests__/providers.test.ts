import { describe, expect, it } from "vitest";

import {
  AI_PROVIDERS,
  baseUrlPlaceholder,
  providerKeyHint,
  providerLabel,
  providerRequiresApiKey,
  providerUsesAzureFields,
  providerUsesBaseUrl,
} from "@/lib/ai/providers";

describe("AI provider helpers", () => {
  it("exposes the three supported providers", () => {
    expect(AI_PROVIDERS).toEqual(["azure", "openai_compatible", "ollama"]);
  });

  it("labels each provider and falls back to azure for null", () => {
    expect(providerLabel("azure")).toMatch(/Azure/);
    expect(providerLabel("ollama")).toMatch(/Ollama/);
    expect(providerLabel(null)).toMatch(/Azure/);
    // Unknown values pass through rather than crashing.
    expect(providerLabel("mystery")).toBe("mystery");
  });

  it("shows Azure-specific fields only for azure (incl. null default)", () => {
    expect(providerUsesAzureFields("azure")).toBe(true);
    expect(providerUsesAzureFields(null)).toBe(true);
    expect(providerUsesAzureFields("openai_compatible")).toBe(false);
    expect(providerUsesAzureFields("ollama")).toBe(false);
  });

  it("uses a base URL for openai_compatible and ollama only", () => {
    expect(providerUsesBaseUrl("openai_compatible")).toBe(true);
    expect(providerUsesBaseUrl("ollama")).toBe(true);
    expect(providerUsesBaseUrl("azure")).toBe(false);
    expect(providerUsesBaseUrl(null)).toBe(false);
  });

  it("only hard-requires an API key for azure", () => {
    expect(providerRequiresApiKey("azure")).toBe(true);
    expect(providerRequiresApiKey(null)).toBe(true);
    expect(providerRequiresApiKey("openai_compatible")).toBe(false);
    expect(providerRequiresApiKey("ollama")).toBe(false);
  });

  it("gives an ollama-flavoured base URL placeholder", () => {
    expect(baseUrlPlaceholder("ollama")).toMatch(/11434/);
    expect(baseUrlPlaceholder("openai_compatible")).toMatch(/\/v1/);
  });

  it("explains the API-key expectation per provider", () => {
    expect(providerKeyHint("azure")).toMatch(/AZURE_OPENAI_API_KEY/);
    expect(providerKeyHint("ollama")).toMatch(/no API key/i);
    expect(providerKeyHint("openai_compatible")).toMatch(/AI_API_KEY/);
  });
});
