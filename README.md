# warrant-pdf

A contract PDF that anyone can check offline, built as a thin profile over
[warrant](https://github.com/s0fractal/warrant) decision records.

Party A proposes; party B accepts after seeing the terms and attachments. Both
are ordinary warrant records. The PDF carries them, with the terms and the
attachments, as one embedded file (`warrant-bundle.json`), and shows a page
rendered from them. The verifier never runs code from the document, and it takes
trust only from the reader.

**Status:** demo, `warrant-pdf/0`. Test keys only. No external review yet.

## Try it (60 seconds)

```sh
pip install warrant-verify==0.10.0        # the reader's verifier; warrant-pdf calls it
python3 -m warrant_pdf verify demo/contract.pdf --trust demo/trust.json
```

Or in a browser, offline, with nothing uploaded. The verifier there is warrant's
Rust core compiled to WebAssembly, vendored and pinned
([ADR-0006](docs/adr/0006-two-implementations-one-verdict.md)):

```sh
python3 -m http.server 8765    # then open http://localhost:8765/web/ and drop in
                               # demo/contract.pdf and demo/trust.json
```

```
VERIFIED propose by alice@demo.test, accept by bob@demo.test

WARRANT-PDF/0 CONTRACT
Title: Handover of a bicycle (demo)
1. Alice hands over the bicycle shown in photo.png to Bob on 2026-10-16.
...
```

`demo/trust.json` stands in for *your* trust config: the keys you learned for
Alice and Bob out of band. The demo keys are SHA-256 of public labels
([demo/build_demo.py](demo/build_demo.py)), so the demo rebuilds byte for byte.
They are public and must never be reused.

## What VERIFIED means, exactly

All of the following hold:

1. The file carries exactly one bundle. Its bytes match the declared digest, and
   every entry is named by the hash of its content.
2. Your warrant verifier, at settlement grade and under your trust config,
   reports no finding except the expected `unadopted root`.
3. The bundle holds one propose and accepts that answer it. Every party the terms
   name signed. Every attachment is in the propose's evidence.

Separately, the verifier re-renders the bundle and reports **MATCH** (the file is
exactly that rendering) or **DIFFERS** (exit 2: read the printed text, not the
page). It always prints the signed text.

It does **not** mean:
- that Alice is a particular human (that is your trust config);
- that the photo shows what it claims;
- that the time is true (`ts` is what the signer stated);
- that the page you see is the signed one, unless the result says MATCH.

## How it is built

- **[SPEC.md](SPEC.md)** is generated from the Normative sections of the
  [ADRs](docs/adr/). It is never edited by hand.
- **[contracts/](contracts/)**: one file per normative statement. It quotes the
  statement and names its witness tests and the mutants that must be killed. It
  keeps an append-only history of why the statement reads as it does, with the
  counterexamples that forced it.
- **[tests/test_counter_vectors.py](tests/test_counter_vectors.py)**: each test
  is one attack or accident and the outcome it must produce.
- **Two implementations**: Python ([warrant_pdf/](warrant_pdf/), calling the
  Python warrant CLI) and JavaScript ([web/profile.mjs](web/profile.mjs), calling
  warrant's Rust core in WASM). Every counter-vector runs through both, and the
  outcomes must be identical, down to the signed text.
- **Mutants** ([tools/mutants.json](tools/mutants.json)): each removes or
  weakens one rule, in either implementation. A mutant counts as killed only if
  a witness *of its own statement* fails. Any other failing test does not count.

```sh
sh scripts/local-ci.sh        # demo reproduces, contracts check, tests, mutants
```

## Findings so far

- **Warrant's `ok: true` is not "signed by the named actor".** An accept for Bob
  signed with Mallory's key verifies `ok: true, errors: 0` at settlement grade.
  The only signal is a WARN, `signature unbound` (warrant SPEC §5.1, by design).
  This profile refuses it ([ADR-0003](docs/adr/0003-trust-comes-from-the-reader.md),
  [WPDF-T2](contracts/WPDF-T2.json)).
- **A qpdf re-save drops both the marker line and bytes after `%%EOF`; the
  attachment survives.** Hence the saved attachment is itself verifiable
  ([measurement](docs/measurements/2026-10-16-resave.md), [WPDF-E3](contracts/WPDF-E3.json)).
- **Writing the second implementation broke the first, usefully.** Several gaps
  surfaced before any JavaScript ran:
  - a `ts` that warrant admits crashed the Python verifier;
  - Python admitted bundles the browser verifier cannot;
  - a missing verifier gave a traceback instead of a refusal.

  The parity hook then hid a default from its own mutants. All of these are recorded
  as counterexamples in the [contracts](contracts/).

## Limits

- Ed25519 only. Phone secure elements (Secure Enclave, StrongBox) sign ECDSA
  P-256, which warrant does not yet accept. There is no hardware attestation.
- The page shows printable ASCII. Other characters appear as `?`, and the verifier
  prints the exact text.
- After acceptance there is no lifecycle: a `supersede` or `reject` in the bundle
  refuses.
- The browser page needs a static web server, because module workers do not
  load from `file://`.

See [docs/COMPARISON.md](docs/COMPARISON.md) for how this relates to other
self-contained signed-PDF designs.

License: MIT.
