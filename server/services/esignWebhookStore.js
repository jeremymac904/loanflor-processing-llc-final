// Dedup ledger for inbound Documenso webhooks (server/data/esign-webhook-seen.json, git-ignored).
// A webhook is never trusted for anything but "please re-check this envelope" (see esignWebhook.js /
// FLO_ESIGN.md), so all this store needs to prevent is acting on the exact same event twice — it holds no
// borrower data, just event ids and timestamps.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_FILE = path.resolve(HERE, '..', 'data', 'esign-webhook-seen.json');
const PRUNE_AFTER_MS = 7 * 24 * 60 * 60 * 1000;

export function createEsignWebhookStore(file = process.env.ESIGN_WEBHOOK_SEEN_FILE || DEFAULT_FILE) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const read = () => {
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
      return {};
    }
  };
  const write = (data) => {
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(data), { mode: 0o600 });
    fs.renameSync(tmp, file);
  };
  return {
    /** True if this exact event was already processed (dedup key: event type + envelope id + provider event id/timestamp). */
    seen(key) {
      return Boolean(read()[key]);
    },
    markSeen(key) {
      const data = read();
      const now = Date.now();
      data[key] = now;
      for (const [k, at] of Object.entries(data)) {
        if (now - at > PRUNE_AFTER_MS) delete data[k];
      }
      write(data);
    },
  };
}
