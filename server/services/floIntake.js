// Authenticated Flo intake connector.
//
// The website backend is the only thing that talks to Flo. The browser never
// sees FLO_INTAKE_URL or FLO_INTAKE_TOKEN, and Ashley's Hermes gateway is never
// exposed to the public internet: FLO_INTAKE_URL points at the private intake
// endpoint (`scripts/flo/intake_server.py` on Ashley's machine, reached over a
// private network / tunnel). See FLO_INTAKE_INTEGRATION.md.

const DEFAULT_TIMEOUT_MS = 15_000;

export function intakeConfigured(env = process.env) {
  return Boolean(env.FLO_INTAKE_URL && env.FLO_INTAKE_TOKEN);
}

/**
 * Deliver one normalized submission payload. Resolves to
 *   { ok: true, result }                 delivered (201 created, or 200 already known → idempotent success)
 *   { ok: false, retryable, error }      keep the record as pending_delivery when retryable
 */
export async function deliverToFlo(payload, { env = process.env, fetchImpl = globalThis.fetch, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  if (!intakeConfigured(env)) {
    return { ok: false, retryable: true, error: 'FLO_INTAKE_URL / FLO_INTAKE_TOKEN not configured' };
  }
  const url = `${env.FLO_INTAKE_URL.replace(/\/+$/, '')}/intake/loan-submissions`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${env.FLO_INTAKE_TOKEN}`,
        'Idempotency-Key': payload.submissionId,
        'X-LoanFlow-Source': payload.source,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const text = await response.text();
    let body = {};
    try {
      body = text ? JSON.parse(text) : {};
    } catch {
      body = {};
    }
    if (response.status === 201 || response.status === 200 || response.status === 409) {
      return { ok: true, result: { status: response.status, workspaceId: body.workspaceId || null, duplicate: response.status !== 201 } };
    }
    // 4xx other than 409 = our payload is wrong; do not retry forever, keep for a human.
    const retryable = response.status >= 500 || response.status === 429 || response.status === 408;
    return { ok: false, retryable, error: `Flo intake responded ${response.status}` };
  } catch (error) {
    return { ok: false, retryable: true, error: error.name === 'AbortError' ? 'Flo intake timed out' : `Flo intake unreachable (${error.code || error.name})` };
  } finally {
    clearTimeout(timer);
  }
}
