/** Relative store paths mapped to original bytes or hexadecimal byte strings. */
export type StoreFiles = Readonly<Record<string, Uint8Array | string>>;
/** The existing closed CLI report. `ok` means zero errors; inspect warnings. */
export interface VerificationReport {
    report: "warrant.verify-report@v0";
    grade: "base" | "settlement";
    ok: boolean;
    records: number;
    errors: number;
    warnings: number;
    findings: {
        level: "ERR" | "WARN";
        subject: string;
        message: string;
    }[];
}
/** A fresh ski evaluation, separate from a verification report. */
export interface CheckResult {
    verdict: "pass" | "fail";
    result: string;
    atp_spent: number;
}
/** Explicit external trust selects settlement grade; omission selects base. */
export interface VerifyOptions {
    trust?: string;
    /**
     * WRT-018: a record whose own actor has no signature by a key bound in `trust`
     * is an ERR. Co-signatures are unaffected. Requires `trust`; throws without it.
     */
    requireBound?: boolean;
}
/** WASM limits apply in every host, including Node and Deno. No time limit here. */
export declare const LIMITS: Readonly<{
    bytes: number;
    files: number;
    atpPerCheck: number;
    wasmStackBytes: number;
    wasmMemoryBytes: number;
}>;
/** Encode original bytes without parsing or normalizing their contents. */
export declare function toHex(bytes: Uint8Array): string;
/** Verify raw store bytes. Throws on admission refusal or unfinished execution. */
export declare function verifyStore(files: StoreFiles, options?: VerifyOptions): VerificationReport;
/** Compute a body ID; this alone does not verify the record or its signature. */
export declare function recordId(bytes: Uint8Array): string;
/** Re-execute ski@v1 from supplied blobs. Never executes a cmd@v1 reason. */
export declare function runCheck(files: StoreFiles, check: string): CheckResult;
