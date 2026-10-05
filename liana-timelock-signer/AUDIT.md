# Audit Record

**Bitcoin Core Feature Overlay revision:** `632648b88cdb867ab6372e2850e8a53d00f58552`  
**Generator blob:** `8c14cd6c53c7a6c6df2277a7b04dbee6557aed91`  
**Tails launcher blob:** `2af915af039a6d89e2aeb032acd97b1e2d0beadd`  
**Bitcoin Core version:** `v32.0rc2`  
**Bitcoin Core commit:** `bc795e60dbb2c6e9c9556949731912429290626a`  
**Review date:** 2026-10-04

This is an AI-assisted source/design review record, not an independent professional security audit. Review method: [AUDITING.md](AUDITING.md).

## Scope reviewed

The review covered:

- selectable BIP87 or BIP48 local account derivation;
- public descriptor handoff to Core;
- rejection of private, unranged, unsolvable, non-wsh and non-timelocked descriptors;
- exact local signer identity matching;
- multiple legitimate occurrences of the local account xpub;
- account-xprv substitution without a bare-xpub global replace;
- Core canonical public-policy equality before import;
- stdin handling of sensitive descriptor material;
- post-import local-key activity checks;
- inherited Tails launcher isolation and Core archive pin.

## Exact supported descriptor class

Version 1 supports a public, ranged, solvable:

```text
wsh(<Miniscript containing at least one older(...)>)
```

where the selected local Core signer appears at least once using either:

```text
m/87h/coin_typeh/0h
```

or:

```text
m/48h/coin_typeh/0h/2h
```

Taproot `tr(...)` is explicitly unsupported.

## Concrete compatibility target

A real Liana descriptor supplied during development used:

- BIP48 primary signer: `m/48'/0'/0'/2'`
- BIP87 recovery signer: `m/87'/0'/0'`
- `older(52596)` recovery delay
- top-level `wsh(or_d(...))`

The implementation was adjusted so either account convention can be selected for the local Core signer while Core remains responsible for parsing the Miniscript policy.

## Core dependency reviewed

Bitcoin Core v32.0rc2 `doc/descriptors.md` states that output descriptors support Miniscript expressions in `wsh` and `tr`.

The overlay relies on Core `getdescriptorinfo` rather than implementing Miniscript parsing.

## Security invariants

- The supplied descriptor must contain no private keys.
- The selected local account xpub must only appear with the exact expected origin.
- Every exact occurrence of the local identity is substituted; derivation suffixes remain unchanged.
- The private form must canonicalize back to the identical public descriptor.
- The multipath expansion must remain identical.
- Sensitive RPC material uses stdin rather than argv.
- The private descriptor/xprv are not intentionally printed or persisted by the helper.

## Testing status

Source/design review performed.

Not yet completed in this review session:

- Python execution against target Tails;
- mocked end-to-end Core RPC flow for both account choices;
- real Bitcoin Core v32.0rc2 daemon test;
- import of the exact real Liana descriptor using its matching local key;
- primary-path PSBT signing;
- timelocked recovery-path PSBT signing;
- backup/restore end-to-end test.

Do not treat this as production-ready for meaningful funds until those tests are completed.

## Upstream references

- Bitcoin Core v32.0rc2 `doc/descriptors.md`
- Bitcoin Core `getdescriptorinfo`
- Bitcoin Core `importdescriptors`
- Bitcoin Core `addhdkey` / `derivehdkey` / `gethdkeys`
- BIP32
- BIP48
- BIP87
- BIP379 Miniscript descriptors
- Liana project documentation/source

## Maintenance rule

Any expansion beyond the exact P2WSH scope above, especially Taproot support, requires explicit re-review and retesting.
