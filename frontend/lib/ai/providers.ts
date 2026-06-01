// Multi-provider AI helpers shared by the admin AI-settings UI.
//
// Pure functions so the page stays declarative ("which fields does
// this provider need?") and the branching logic is unit-tested in one
// place rather than scattered through JSX.

export type AIProvider = "azure" | "openai_compatible" | "ollama";

export const AI_PROVIDERS: AIProvider[] = [
  "azure",
  "openai_compatible",
  "ollama",
];

const LABELS: Record<AIProvider, string> = {
  azure: "Azure OpenAI",
  openai_compatible: "OpenAI-compatible (vLLM / LM Studio / OpenAI)",
  ollama: "Ollama (local)",
};

/** Human-readable label for a provider value (tolerates unknown / null). */
export function providerLabel(provider: string | null | undefined): string {
  if (!provider) return LABELS.azure;
  return LABELS[provider as AIProvider] ?? provider;
}

/** Azure uses endpoint + deployment + api-version; the others don't. */
export function providerUsesAzureFields(
  provider: string | null | undefined
): boolean {
  return (provider ?? "azure") === "azure";
}

/** openai_compatible + ollama are driven by a base URL + model id. */
export function providerUsesBaseUrl(
  provider: string | null | undefined
): boolean {
  const p = provider ?? "azure";
  return p === "openai_compatible" || p === "ollama";
}

/**
 * Whether a missing API key should be surfaced as a hard error.
 * Only Azure hard-requires a key; OpenAI-compatible servers and Ollama
 * commonly run keyless, so the UI shows an informational note instead.
 */
export function providerRequiresApiKey(
  provider: string | null | undefined
): boolean {
  return (provider ?? "azure") === "azure";
}

/** Placeholder shown in the base-URL input for each provider. */
export function baseUrlPlaceholder(
  provider: string | null | undefined
): string {
  if ((provider ?? "azure") === "ollama") {
    return "http://localhost:11434/v1 (default)";
  }
  return "http://localhost:8000/v1";
}

/** Short hint about the API-key expectation for a provider. */
export function providerKeyHint(provider: string | null | undefined): string {
  const p = provider ?? "azure";
  if (p === "azure") {
    return "Set AZURE_OPENAI_API_KEY in .env — required for live mode.";
  }
  if (p === "ollama") {
    return "Ollama needs no API key — just make sure the daemon is reachable.";
  }
  return "Set AI_API_KEY in .env only if your server requires authentication.";
}
