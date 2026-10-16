// Runs one verification off the page's thread. The page terminates this worker
// on timeout, as @s0fractal/warrant recommends for untrusted input.
import { verifyStore, recordId } from "./vendor/warrant-0.10.0/mod.js";
import { verify, Refusal } from "./profile.mjs";

self.onmessage = async ({ data }) => {
  try {
    const r = await verify(new Uint8Array(data.file), data.trust, { verifyStore, recordId },
      data.strict ? { strictDisplay: true } : undefined);
    self.postMessage({ outcome: "VERIFIED", ...r });
  } catch (e) {
    self.postMessage(e instanceof Refusal
      ? { outcome: "REFUSED", code: e.code, detail: e.detail }
      : { outcome: "ERROR", detail: String(e && e.message || e) });
  }
};
