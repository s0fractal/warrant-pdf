# ADR-0006. Two implementations, one verdict

**Status:** accepted. **Date:** 2026-10-16.

## Context

A reader without Python should still be able to check a contract: in a browser,
offline, with nothing uploaded. warrant publishes its Rust core compiled to
WebAssembly as `@s0fractal/warrant` (npm, JSR). A browser verifier therefore means a
second implementation of this profile, in JavaScript, calling a different warrant
implementation (Rust, where the Python side calls Python).

Two implementations are only worth having if they agree, and if a test shows they
can be made to disagree.

## Decision

- `web/profile.mjs` implements every rule of `warrant_pdf/` in the same order. It
  receives warrant as `{ verifyStore, recordId }` and re-implements none of it.
- Every call to `verify` in the counter-vector suite runs both implementations. The
  outcomes must be equal: refusal code, or display, signers, the full signed text and
  the reported grade. `WPDF_REQUIRE_JS=1` (set by local CI and CI) makes a missing
  `node` an error, not a skip.
- The browser runs a vendored copy of `@s0fractal/warrant` 0.10.0. It is pinned by
  the npm registry's sha512 integrity and by SHA-256 per file, and its embedded WASM
  is checked against the package's `build.json`. CI compares the copy with the
  tarball npm serves.
- Each JS rule has its own mutant, and a mutant counts only when a witness of the
  same statement fails (through the parity check).

## Normative

- **WPDF-I1.** The Python and JavaScript implementations MUST produce the same outcome — the refusal code, or the display result, signers, signed text and grade — for every input in the counter-vector suite.
- **WPDF-I2.** The browser verifier MUST run the vendored `@s0fractal/warrant` 0.10.0 only if every vendored file matches the pinned manifest and the embedded WASM matches the package's `build.json`.

## Considered

- **Load the package from a CDN at view time.** The reader would then run whatever
  the CDN serves that day. Vendoring with a pinned integrity makes the verifier part
  of the reviewed tree.
- **Generate the JS from the Python.** No suitable tool exists, and a translator
  would be a third thing to trust. Two hand-written implementations plus a
  differential suite is the arrangement warrant itself uses.

## Consequences

- The differential runs Python warrant against Rust warrant on every counter-vector.
  A divergence between warrant's own implementations would surface here too.
- The page needs a web server (module workers do not load from `file://`):
  `python3 -m http.server`, or any static host.
- Porting found four divergences before the JS existed (WPDF-D3, WPDF-E4, WPDF-T2).
  Adding the parity hook found that it masked the display default (WPDF-A1 history).

## Counter-vectors

Every test in `tests/test_counter_vectors.py` (through the parity hook);
`test_both_implementations_ran_and_agree_on_the_demo`, `test_vendored_verifier_matches_its_pin`,
`test_tampered_vendored_verifier_is_refused`.
