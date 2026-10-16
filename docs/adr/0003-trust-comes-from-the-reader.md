# ADR-0003. Trust comes from the reader, never from the document

**Status:** accepted. **Date:** 2026-10-16.

## Context

A self-verifying document that carries its own keys, its own trust list or its own
verifier proves only that it agrees with itself. Anyone can make a fresh, fully
consistent one. This failure was found across every engine of an earlier project by
the same author (black-heart, review of 2026-09-10). It is the reason this repository
exists as a separate, narrow one.

## Decision

- The reader supplies a warrant trust config (warrant SPEC §12) that binds actor
  ids to the public keys the reader has learned out of band.
- The reader runs a warrant verifier of their own choosing (`--warrant CMD`, warrant
  0.11.0 or later) at settlement grade with `--require-bound` (warrant WRT-018). warrant-pdf does not re-implement canonical form, WarrantIDs,
  signatures or key state. It calls the verifier and reads its JSON report.
- The bundle contains no trust config, and nothing in it is read as one.

## Normative

- **WPDF-T1.** Verification MUST require a trust config supplied by the reader; keys are bound to actors only through it, and nothing in the document is read as trust.
- **WPDF-T2.** The reader's warrant verifier MUST run at settlement grade with the required-binding option, so that a record whose own actor has no signature by a key the reader's trust config binds is an error; any `ERR`, and a verifier that produces no report, MUST refuse, while warnings are shown to the reader and do not refuse.

## Considered

- **Embed the verifier (Python or WASM) in the PDF.** It is useful as an archival
  copy. It is not a trust root: whoever ships the verifier chooses the verdict. A
  later ADR may admit an embedded copy that is run only when its digest matches one
  the reader already pins.
- **Hardware attestation as the key root** (as in Pakto). That is a real root: the
  manufacturer's, pinned out of band. It is out of scope for `warrant-pdf/0`. Warrant
  has neither ECDSA P-256 nor an attestation evidence kind; both are named gaps.

## Consequences

- **Why `--require-bound`.** Warrant's `ok: true` is not "signed by the named
  actor". With 0.10.0, an accept for `bob@demo.test` signed with a key the
  reader's trust config does not bind to Bob verified `ok: true, errors: 0` at
  settlement grade, with one warning, `signature unbound: key … claims actor
  bob@demo.test`. That is specified behaviour (SPEC §5.1: bound/unbound is a
  report). The first fix refused on every warning except `unadopted root`. That
  closed the hole but over-refused: anyone holding a copy could append a junk
  co-signature, which warrant excludes as a warning, and the whole contract
  refused. Warrant 0.11.0 added `--require-bound` (WRT-018, proposed from this
  repository): only the record's own actor must be bound, and co-signatures keep
  warrant's report-and-exclude rule. WPDF-T2 now uses it. Warnings no longer
  refuse; they are printed. The WPDF-T2 contract keeps the whole history.
- **What stopped being refused with the warnings.** Each warning warrant emits was
  reviewed when warnings became non-fatal. One had been holding a rule by accident:
  an unresolvable evidence blob is a warning (warrant THREAT-MODEL A5), so a
  contract whose signed photo was swapped verified. WPDF-P1 now requires the
  attachment bytes. The others are harmless here or already refused:
  - the actor's own signature failing becomes an ERR under `--require-bound`;
  - `ts` order, a ski verdict mismatch and a missing policy blob are shown;
  - a prose-only `reject` is a foreign record.
- The reader has to obtain keys somewhere. This repository does not solve key
  distribution; it refuses to pretend the document can.

## Counter-vectors

`test_without_reader_trust_refuses`, `test_counterparty_not_in_reader_trust_refuses`,
`test_accept_signed_by_another_key_for_the_same_actor_refuses`, `test_unavailable_verifier_refuses`,
`test_verification_ran_at_settlement_grade`, `test_appended_junk_cosignature_is_excluded_not_fatal`,
`test_valid_cosignature_by_an_unbound_key_is_shown_not_fatal`.
