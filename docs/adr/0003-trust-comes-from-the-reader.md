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
- The reader runs a warrant verifier of their own choosing (`--warrant CMD`) at
  settlement grade. warrant-pdf does not re-implement canonical form, WarrantIDs,
  signatures or key state. It calls the verifier and reads its JSON report.
- The bundle contains no trust config, and nothing in it is read as one.

## Normative

- **WPDF-T1.** Verification MUST require a trust config supplied by the reader; keys are bound to actors only through it, and nothing in the document is read as trust.
- **WPDF-T2.** The reader's warrant verifier MUST run at settlement grade, and any finding other than the warning `unadopted root` MUST refuse.

## Considered

- **Embed the verifier (Python or WASM) in the PDF.** It is useful as an archival
  copy. It is not a trust root: whoever ships the verifier chooses the verdict. A
  later ADR may admit an embedded copy that is run only when its digest matches one
  the reader already pins.
- **Hardware attestation as the key root** (as in Pakto). That is a real root: the
  manufacturer's, pinned out of band. It is out of scope for `warrant-pdf/0`. Warrant
  has neither ECDSA P-256 nor an attestation evidence kind; both are named gaps.

## Consequences

- `unadopted root` is expected: a two-party contract has no genesis record. Any
  other warning, including warrant's prose-only `reject` warning, refuses. Fail
  closed beats a list of tolerated warnings that grows silently.
- **Warrant's `ok: true` is not "signed by the named actor".** When an accept for
  `bob@demo.test` is signed with a key the reader's trust config does not bind to Bob,
  warrant 0.10.0 at settlement grade reports `ok: true, errors: 0` and the warning
  `signature unbound: key … claims actor bob@demo.test`. That is warrant's specified
  behaviour (SPEC §5.1: "Bound/unbound is a report unless a v0.3 policy explicitly
  makes bound signatures required"). A consumer that reads only `ok` accepts Mallory's
  signature as Bob's. WPDF-T2 refuses on that warning. Found while writing this
  profile; see the WPDF-T2 contract history.
- The reader has to obtain keys somewhere. This repository does not solve key
  distribution; it refuses to pretend the document can.

## Counter-vectors

`test_without_reader_trust_refuses`, `test_counterparty_not_in_reader_trust_refuses`,
`test_accept_signed_by_another_key_for_the_same_actor_refuses`.
