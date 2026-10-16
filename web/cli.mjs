// node web/cli.mjs FILE TRUST.json [--strict-display | --no-strict-display]
// Prints one JSON outcome. Used by the parity hook in tests/test_counter_vectors.py.
import { readFileSync } from "node:fs";
import { verifyStore, recordId } from "./vendor/warrant-0.11.0/mod.js";
import { verify, Refusal } from "./profile.mjs";

const [file, trustPath, ...rest] = process.argv.slice(2);
const trust = trustPath === "-" ? null : readFileSync(trustPath, "utf8");
try {
  // Pass the option only when asked, so the profile's own default is what runs otherwise.
  const options = rest.includes("--strict-display") ? { strictDisplay: true }
    : rest.includes("--no-strict-display") ? { strictDisplay: false } : undefined;
  const r = await verify(new Uint8Array(readFileSync(file)), trust, { verifyStore, recordId }, options);
  console.log(JSON.stringify({ outcome: "VERIFIED", ...r }));
} catch (e) {
  if (!(e instanceof Refusal)) throw e;
  console.log(JSON.stringify({ outcome: "REFUSED", code: e.code, detail: e.detail }));
}
