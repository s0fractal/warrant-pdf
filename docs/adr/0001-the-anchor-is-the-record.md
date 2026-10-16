# ADR-0001. The anchor is the signed record, not the PDF bytes

**Status:** accepted. **Date:** 2026-10-16.

## Context

A PDF is not a deterministic container. Two tools that show the same text write
different bytes (object order, compression, metadata, fonts), and any re-save changes
them again. A signature over the file's bytes therefore breaks on a harmless re-export
and says nothing about what a reader sees.

The same conclusion, reached independently and stated well, is in D. Diikun's Pakto
preprint (§5.6 and the C2PA comparison in §2, doi:10.5281/zenodo.22055260): the
cryptographic anchor is canonical content plus evidence hashes; the display file is
excluded so it can be regenerated without breaking a signature.

## Decision

The anchor is a set of warrant records and blobs (a warrant store) carried inside
the PDF. A record's identity is its WarrantID, SHA-256 over the RFC 8785 form of its
body; the contract terms and every attachment are blobs named by their SHA-256. The
pages are a rendering of that set (ADR-0005). They are checked, but they are not what
was signed.

## Normative

- **WPDF-A1.** Verification MUST NOT depend on the bytes of the rendered pages: a file whose pages differ from the canonical rendering still verifies when its bundle does, and the difference is reported, not hidden.

## Considered

- **Sign the PDF bytes.** Breaks on every re-save; binds layout, not meaning.
- **Sign the extracted page text.** Text extraction differs between tools; the
  reader would be trusting an extractor.

## Consequences

- A page can be edited without breaking a signature. ADR-0005 makes that visible
  instead of impossible: the verifier compares the file with a fresh rendering and
  prints the signed text.
- Anything that is not in a record or a blob is not signed: fonts, layout, colours.

## Counter-vectors

`test_re_rendered_elsewhere_still_verifies`, `test_visible_text_edited_is_reported`.
