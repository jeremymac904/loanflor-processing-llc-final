// Dev helper: print a fresh synthetic submission (new submissionId) as JSON for manual API tests.
//   node server/make_synthetic.mjs > /tmp/sub.json
import { syntheticSubmission } from './synthetic.js';

const s = syntheticSubmission();
s.borrower.name = process.argv[2] || 'Devon Synthetic-Retry';
process.stdout.write(JSON.stringify(s));
