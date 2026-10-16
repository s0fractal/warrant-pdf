# Comparison with Pakto

Pakto is a mobile app for two-party document signing by D. Diikun. It is described
in a preprint, *CA-less Mutual Co-Signing of Documents over a Unidirectional Visual
Channel with Transported Hardware Attestation* (2026, CC BY 4.0,
doi:[10.5281/zenodo.22055260](https://doi.org/10.5281/zenodo.22055260)), and in an
article on DOU (topic 61338). The preprint notes that aspects of its construction are
the subject of a pending patent application by its author.

**What this repository does with that.** It cites Pakto and compares with it. It does
not implement Pakto's constructions: not the two-stage anchor `h2 = H(h1 ‖ id_B)`, not
the signature chaining over `pk_A ‖ σ_A`, not the attestation transport, not the
fountain-coded optical channel. Where the two designs reach the same property,
warrant-pdf uses warrant's own, earlier mechanism: a `propose` record and an `accept`
that names its WarrantID. Hash-linking records in this way is general practice. This
document makes no legal claim of any kind.

## Property by property

| Property (preprint terms) | Pakto | warrant-pdf / warrant | Note |
|---|---|---|---|
| Anchor binding: content fixed before the counterparty is known | `h1` over a TLV-encoded field vector, injective | propose WarrantID = SHA-256(RFC 8785 body); terms and attachments are blobs named by SHA-256 | same property |
| Counterparty bound without re-signing by A | `h2` from `h1` and B's identity fields | accept names the propose's WarrantID in `prior`; B's identity is the accept's `actor` | same property |
| Inseparability of B's signature | `m_B` contains `pk_A` and the bytes of `σ_A` | accept binds A's body; A's key is bound through the reader's trust config | Pakto is stronger *by its game definition*: it binds the signature bytes. With deterministic Ed25519 the difference is nil. With randomized ECDSA, warrant would accept another valid signature by the same key over the same body ([ADR-0002](adr/0002-two-parties-are-propose-and-accept.md)) |
| Post-signing tamper evidence | composite `finalHash`, 39 fields | every record, blob and name is checked (WPDF-E1, E2) | same property |
| Anchor detached from display bytes | yes (§5.6) | yes ([ADR-0001](adr/0001-the-anchor-is-the-record.md), credited) | warrant-pdf also re-renders and reports MATCH/DIFFERS (WPDF-D1) |
| Key provenance | hardware attestation token, manufacturer root pinned in the verifier | none. Keys are bound by the reader's trust config | **gap in warrant**: no attestation evidence kind |
| Signature scheme | ECDSA P-256 in Secure Enclave / StrongBox, biometric gate | Ed25519, software keys | **gap in warrant**: secure elements cannot sign Ed25519 |
| Key lifecycle | not described | pre-rotation, conflict scoping, no revocation (warrant WRT-015/016/017) | warrant has more |
| Independent verification | two implementations by the author (Dart, Python) | warrant: Python, Go, Rust, WASM, 144 conformance vectors; warrant-pdf calls whichever the reader chooses | both are single-author ecosystems; neither has an external audit |
| Transport | animated QR with fountain code; NFC, BLE | out of scope (it is a file) | product layer |
| Where the bundle lives | bytes after `%%EOF`, between text markers (article) | a standard embedded file + one marker line | measured: qpdf 12.4.2 drops both the trailing bytes and our marker line; the embedded file survives ([measurement](measurements/2026-10-16-resave.md)) |

## The honest summary

The evidence core of a self-contained two-party signed PDF fits a profile over
warrant. The profile adds five ADRs and under 500 lines of Python, and needs no new
cryptography. Pakto's own contribution lies outside that core:
- hardware-backed keys and attestation;
- the offline optical channel;
- the mobile product;
- a formal treatment with game-based reductions, which warrant's documentation lacks.

To carry Pakto-grade key provenance, warrant would need two additions:
1. an ECDSA P-256 signature suite with strict DER, low-S and an on-curve check;
2. an attestation evidence kind.

Neither exists today.
