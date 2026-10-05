# Bitcoin Core Liana Timelock Signer Design

This directory is an isolated Bitcoin Core Feature Overlay for Liana-style timelocked Miniscript policies.

It intentionally does not modify the ordinary `wsh(sortedmulti())` quorum signer.

## Why a separate generator

The ordinary quorum signer has a deliberately narrow policy validator: `wsh(sortedmulti(...))` plus constrained key origins.

Liana policies are materially different. They can contain:

- Miniscript combinators;
- `older()` relative timelocks;
- primary and recovery spending paths;
- the same signer reused across spending paths;
- mixed derivation conventions such as BIP48 and BIP87 in one descriptor;
- Taproot policies in newer Liana versions.

Combining both policy classes into one parser would enlarge the security-critical code and make the plain multisig path harder to audit. Therefore Liana uses a separate generator and launcher.

## Bitcoin Core as parser

Bitcoin Core v32.0rc2 documents support for Miniscript expressions inside `wsh()` and `tr()` descriptors.

This overlay delegates descriptor parsing and canonicalization to Core through `getdescriptorinfo`. It does not implement Miniscript.

Version 1 intentionally supports only top-level `wsh(...)`.

## Local signer construction

Bitcoin Core performs key generation and BIP32 derivation.

The user chooses exactly one local account type:

```text
BIP87:
m/87h/coin_typeh/0h

BIP48 native-P2WSH:
m/48h/coin_typeh/0h/2h
```

Only the selected account identity is considered local signer material.

## Example compatibility target

A valid Liana descriptor can mix both conventions, for example:

```text
wsh(or_d(
  pk([fingerprint/48h/0h/0h/2h]xpub/<0;1>/*),
  and_v(
    v:pkh([fingerprint/87h/0h/0h]xpub/<0;1>/*),
    older(52596)
  )
))
```

The overlay does not care whether the selected Core signer appears in `pk()`, `pkh()`, a multisig fragment, or another Miniscript branch. Core parses that policy.

## Public descriptor validation

The pasted descriptor is first sent to Bitcoin Core `getdescriptorinfo`.

The overlay requires:

- no private keys in the supplied descriptor;
- ranged;
- solvable;
- canonical top-level `wsh(...)`;
- at least one `older(...)`;
- at least one occurrence of this signer's exact selected account identity.

The same local account xpub may occur multiple times with different unhardened suffixes.

If the same account xpub appears anywhere with an unexpected/ambiguous origin, the overlay aborts instead of guessing.

## Private substitution

Only after public validation does Core derive the selected account xprv.

The helper replaces every exact occurrence of:

```text
[exact selected origin]xpub
```

with the same origin plus the local xprv.

Derivation suffixes remain untouched.

The helper never performs a bare-xpub global replacement.

The resulting private descriptor is sent to Core `getdescriptorinfo` over stdin.

Before import, the overlay requires:

- Core reports private keys are present;
- Core's canonical public `descriptor` exactly equals the original public descriptor;
- Core's `multipath_expansion` exactly equals the original public multipath expansion.

Only then is the descriptor imported.

## Post-import verification

`gethdkeys active_only=true` must report the selected local account xpub as private and participating in an active descriptor.

The helper does not require a single descriptor occurrence because Liana may reuse the local account in multiple paths.

## Trust boundary

Liana owns policy construction and human interpretation.

Bitcoin Core owns:

- random root generation;
- BIP32 derivation;
- descriptor/Miniscript parsing;
- canonicalization;
- wallet storage;
- PSBT signing.

The overlay orchestrates these operations and checks invariants.

## Explicit non-goals

Version 1 does not:

- interpret Miniscript semantics itself;
- judge whether timelock values are safe or intended;
- support Taproot `tr(...)` Liana descriptors;
- create the Liana coordinator wallet;
- verify Liana's UI or policy editor;
- replace independent address/policy verification.

## Auditability rule

Any expansion beyond this exact P2WSH scope, especially Taproot support, requires explicit re-review and retesting.
