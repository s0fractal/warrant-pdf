# ADR-0004. One marked bundle, every entry named by its hash

**Status:** accepted. **Date:** 2026-10-16.

## Context

The bundle has to be found without a full PDF parser, and found unambiguously. An
incremental update can append objects to any PDF. A verifier that takes "the first"
or "the last" bundle would let an appended one replace or shadow the original.

## Decision

- The bundle is one JSON byte string:
  `{"bundle":"warrant-pdf/0","records":{WarrantID: record},"blobs":{sha256: base64}}`.
- It is the stream of a standard embedded file (`warrant-bundle.json`, visible in a
  viewer's attachments panel). The stream is preceded by one comment line at a line
  start: `%WARRANT-PDF-BUNDLE/0 len=N sha256=H`.
- Entry names are content hashes. Blob names are checked against SHA-256 here.
  Record names are checked against the WarrantID that the reader's warrant computes
  (`warrant canon`).

## Normative

- **WPDF-E1.** A verifier MUST find exactly one bundle marker at a line start, MUST read exactly the declared length after it, and MUST refuse unless the SHA-256 of those bytes equals the declared digest.
- **WPDF-E2.** Every bundle entry MUST be named by the hash of its content — a blob by its SHA-256, a record by its WarrantID as computed by the reader's warrant — and a mismatch MUST refuse.
- **WPDF-E3.** A bundle saved on its own (the `warrant-bundle.json` attachment) MUST verify by the same rules, with no page comparison.
- **WPDF-E4.** The bundle MUST be UTF-8 JSON without `NaN` or `Infinity`, at most 8 MiB and 2,048 entries — the input limits of warrant's browser verifier — so that every implementation of this profile admits the same bundles; anything else MUST refuse.

## Considered

- **Bytes after `%%EOF`** (the choice in Pakto's article). Viewers ignore them, and
  they need no PDF knowledge to find. They are also invisible to a reader looking for
  attachments, and they did not survive a qpdf re-save in any of the four modes
  measured (below). A standard embedded file did survive, and anyone can open it.
- **Parse `/EmbeddedFiles` properly.** That needs a full PDF parser in every
  verifier, which is a larger attack surface than one marker line.

## Consequences

- **Measured: every qpdf re-save drops the marker.** qpdf 12.4.2 in four modes
  (default, `--qdf`, `--object-streams=generate`, `--recompress-flate`) rewrote
  the file without the comment line. Verification of each copy refused with
  `BUNDLE_MISSING`, and in each copy the `warrant-bundle.json` attachment survived
  (`pdfdetach -list`), byte-identical to the original bundle, and verified. Hence
  WPDF-E3: the attachment, saved from any viewer, is itself verifiable. One tool was
  measured, once ([record](../measurements/2026-10-16-resave.md)); this is not a CI
  check and says nothing about other tools.
- A second marker, even one carrying a valid bundle, refuses as `BUNDLE_AMBIGUOUS`.
- The limits are those of `@s0fractal/warrant` 0.10.0 and 0.11.0 (8 MiB of store input, 2,048
  files). The encoded bundle is larger than the store it decodes to, so a bundle
  under 8 MiB always fits. Python's `json` accepts `NaN`, while `JSON.parse` does not;
  WPDF-E4 makes both implementations refuse it. The Python implementation found this
  divergence before the JavaScript one was written.

## Counter-vectors

`test_no_marker_refuses`, `test_second_bundle_appended_refuses`, `test_bundle_byte_flipped_refuses`,
`test_blob_bytes_changed_under_old_name_refuses`, `test_record_under_wrong_name_refuses`,
`test_photo_swapped_and_renamed_refuses`, `test_attachment_saved_from_a_viewer_verifies`,
`test_bare_bundle_gets_the_same_checks`, `test_nan_in_bundle_refuses`,
`test_more_entries_than_the_browser_verifier_admits_refuses`, `test_oversized_bundle_is_refused_before_reading`.
