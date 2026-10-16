/**
 * Warrant verification using the Rust core compiled to WebAssembly.
 * No network requests, native executable, filesystem store or install script.
 * Calls are synchronous: use a disposable worker for untrusted stores or a UI.
 *
 * @example
 * ```ts
 * import { verifyStore } from "@s0fractal/warrant";
 * const report = verifyStore(files);
 * console.log(report.ok, report.findings);
 * ```
 * @module
 */
import { initSync, verify_store, record_id, run_check, } from "./generated/warrant_browser.js";
import { binary } from "./generated/bytes.js";
/** WASM limits apply in every host, including Node and Deno. No time limit here. */
export const LIMITS = Object.freeze({
    bytes: 8_388_608,
    files: 2048,
    atpPerCheck: 1_000_000,
    wasmStackBytes: 16_777_216,
    wasmMemoryBytes: 268_435_456,
});
let initialized = false;
let interrupted = false;
function ready() {
    if (!initialized) {
        initSync({ module: Uint8Array.from(atob(binary), (c) => c.charCodeAt(0)) });
        initialized = true;
    }
}
function execute(action) {
    if (interrupted)
        throw new Error("WASM instance interrupted; use a fresh worker");
    ready();
    try {
        return action();
    }
    catch (error) {
        if (error instanceof WebAssembly.RuntimeError)
            interrupted = true;
        throw error instanceof Error ? error : new Error(String(error));
    }
}
/** Encode original bytes without parsing or normalizing their contents. */
export function toHex(bytes) {
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
function transport(files) {
    const entries = Object.entries(files);
    if (entries.length > LIMITS.files)
        throw new Error("Store exceeds 2048 files");
    const out = Object.create(null);
    let total = 0;
    for (const [path, bytes] of entries) {
        total += typeof bytes === "string" ? bytes.length / 2 : bytes.byteLength;
        if (total > LIMITS.bytes)
            throw new Error("Store exceeds 8 MiB");
        out[path] = typeof bytes === "string" ? bytes : toHex(bytes);
    }
    return JSON.stringify(out);
}
/** Verify raw store bytes. Throws on admission refusal or unfinished execution. */
export function verifyStore(files, options = {}) {
    const input = transport(files);
    return JSON.parse(execute(() => verify_store(input, options.trust, options.requireBound === true)));
}
/** Compute a body ID; this alone does not verify the record or its signature. */
export function recordId(bytes) {
    if (bytes.byteLength > LIMITS.bytes)
        throw new Error("Record exceeds 8 MiB");
    return execute(() => record_id(toHex(bytes)));
}
/** Re-execute ski@v1 from supplied blobs. Never executes a cmd@v1 reason. */
export function runCheck(files, check) {
    const input = transport(files);
    return JSON.parse(execute(() => run_check(input, check)));
}
