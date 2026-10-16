# ADR-0002. Two parties are a propose and its accepts

**Status:** accepted. **Date:** 2026-10-16.

## Context

Two-party signing has an ordering problem: the first party commits before the second
is known, and the second must bind to exactly what the first committed to. Warrant
already has this shape. A `propose` record is identified by its WarrantID before
anyone answers it; an `accept` names that WarrantID in `prior`. Because the WarrantID
covers the whole propose body (terms, evidence, actor, time), an accept cannot be moved
to another offer without its signature failing.

This profile adds no construction of its own. It restricts which warrant stores
count as a contract.

## Decision

- The terms are one JSON blob, `warrant-pdf/0` (title, clauses, named parties,
  attachments by SHA-256).
- Party A files one `propose`. Its subject is the terms blob; its evidence lists the
  terms and every attachment.
- Each counterparty files an `accept` whose `prior` is that propose.
- Every record is filed `under` the profile blob `{"profile":"warrant-pdf/0"}`, so a
  record made for another purpose cannot be reused here.

## Normative

- **WPDF-P1.** A bundle MUST hold exactly one propose and otherwise only accepts; every record MUST be filed under exactly the profile blob; the propose subject MUST name the terms blob, its evidence MUST list the terms and every attachment the terms name, and the bytes of every such attachment MUST be in the bundle.
- **WPDF-P2.** Every accept MUST respond to exactly the propose (its prior is the propose alone), name the same subject, and be filed by an actor other than the proposer.
- **WPDF-P3.** Every party the terms name MUST have filed the propose or an accept, and at least one accept MUST exist.

## Considered

- **One record with two signatures.** Warrant supports co-signatures. They are
  unordered, though: neither signature records that its signer saw the other.
  Two records keep the order and who answered what.
- **Ignore records the profile does not know** (a later `supersede`, a `reject`).
  Refusing is simpler and honest for a demo. Lifecycle after acceptance is outside
  `warrant-pdf/0`.

## Consequences

- An accept binds the propose body and, through the reader's trust config, the
  proposer's key. It does not bind the bytes of the proposer's signature. With
  deterministic Ed25519 that makes no difference. With a randomized scheme, a second
  valid signature by the same key over the same body would be equally accepted.
- A dangling `prior` (an accept of an offer that is not in the bundle) is refused by
  warrant itself, not by this profile.

## Counter-vectors

`test_accept_removed_refuses`, `test_self_accept_refuses`,
`test_self_accept_with_no_named_parties_refuses`, `test_accept_of_an_accept_refuses`,
`test_accept_of_an_offer_not_in_the_bundle_refuses`, `test_accept_naming_another_subject_refuses`,
`test_named_party_replaced_by_a_trusted_stranger_refuses`, `test_offer_without_any_accept_refuses`,
`test_second_propose_refuses`, `test_foreign_record_refuses`, `test_attachment_not_in_evidence_refuses`,
`test_filed_under_another_policy_refuses`, `test_photo_swapped_and_renamed_refuses`.
