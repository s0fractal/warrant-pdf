# ADR-0005. The page is checked, not signed

**Status:** accepted. **Date:** 2026-10-16.

## Context

ADR-0001 leaves the page unsigned. A reader still looks at the page. An edited page
over an intact bundle ("The price is 900 EUR" over a signed 100) has to be caught
somewhere.

## Decision

- The page is a deterministic function of the bundle: `canonical_text` gives the
  lines, `render` the bytes. Text outside printable ASCII is shown as `?` on the
  page. The verifier prints the exact UTF-8 text.
- The verifier renders the bundle again and compares the whole file with the
  result: `MATCH` or `DIFFERS`. It always prints the signed text.
- By default `DIFFERS` is a warning (exit 2), because a legitimate re-export also
  differs. `--strict-display` makes it a refusal.
- The demo is built from fixed test keys and a fixed time, and the committed files
  are checked to reproduce byte for byte.

## Normative

- **WPDF-D1.** A verifier MUST re-render the bundle with the profile's renderer, MUST report whether the file equals that rendering, and MUST print the signed text; under `--strict-display` a difference MUST refuse.
- **WPDF-D2.** The demo build MUST reproduce `demo/contract.pdf` and `demo/trust.json` byte for byte.

## Considered

- **Compare extracted text instead of bytes.** This would tolerate some re-exports.
  It would also make the result depend on a text extractor. Byte equality is a narrow,
  exact predicate, and its name says what it checks.

## Consequences

- `MATCH` means "this file is exactly what warrant-pdf/0 would render", not "a
  human read it". `DIFFERS` does not mean forged; it means "read the printed text,
  not the page".
- Changing the renderer changes the profile. A new renderer is a new profile
  version, because old files would stop matching.

## Counter-vectors

`test_demo_verifies_and_page_matches`, `test_visible_text_edited_is_reported`,
`test_demo_rebuilds_byte_for_byte`.
