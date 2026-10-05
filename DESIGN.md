# Bitcoin Core Descriptor Signer Design

This utility follows the Bitcoin Core Feature Overlay architecture: small Core-facing logic, a separate Tails launcher, and separate human/audit procedure.

## Core principle

**Bitcoin Core validates the descriptor policy. The helper validates only the local signer boundary.**

The previous design parsed `wsh(sortedmulti(...))` itself and imposed policy-specific derivation rules. That became unnecessary once the signer needed to work with richer descriptors such as Liana Miniscript.

Removing the policy parser reduces custom security-critical code.

## Local signer construction

Bitcoin Core creates the root with `addhdkey` and derives one selected account:

```text
BIP87:
m/87h/coin_typeh/0h

BIP48 native-P2WSH:
m/48h/coin_typeh/0h/2h
```

The account selection is explicit before the public key is exported.

## Public descriptor handling

The complete PUBLIC descriptor is passed directly to Core `getdescriptorinfo`.

The helper requires only:

- Core accepts the descriptor;
- Core reports no private keys in the supplied descriptor;
- the canonical descriptor contains this signer's exact `[origin]xpub` identity.

The helper deliberately does not inspect:

- outer descriptor type;
- multisig threshold;
- Miniscript structure;
- timelock values;
- other cosigner paths;
- Taproot script trees;
- whether the policy is sensible.

Those are policy/coordinator concerns and must be independently verified by the user.

## Exact-key binding

After Core canonicalizes the descriptor, the helper searches for the exact local identity:

```text
[exact-origin]exact-account-xpub
```

If the same account xpub appears anywhere with another/ambiguous origin, the helper aborts rather than guessing.

The exact identity may occur more than once; every exact occurrence is replaced. This supports policies such as Liana where the same account key can participate in multiple branches.

## Private substitution invariant

Only after public validation does Core derive the matching account xprv.

The helper substitutes only the exact local identity, preserving all descriptor syntax and child-derivation suffixes.

The private descriptor then goes back to Core `getdescriptorinfo`.

Import is allowed only if:

- Core reports private keys are present;
- Core's canonical public `descriptor` is exactly unchanged;
- Core's `multipath_expansion` is exactly unchanged.

This is the primary safety invariant.

## Import and verification

Ranged descriptors are imported active. Fixed descriptors are imported inactive but remain available for signing.

After import, `gethdkeys` must report:

- the local account xpub;
- `has_private=true`;
- the exact imported public descriptor;
- the expected active state.

## Trust boundary

Bitcoin Core owns:

- random key generation;
- BIP32 derivation;
- descriptor parsing;
- Miniscript parsing;
- descriptor canonicalization;
- wallet storage;
- PSBT signing.

The helper owns:

- choosing the local account convention;
- binding the descriptor to the exact local key;
- private substitution;
- invariant checks;
- launcher/environment orchestration.

## Accepted limitations

- A Core-valid descriptor can still represent a dangerous or unintended wallet policy.
- This helper does not validate thresholds, timelocks, recovery semantics, or coordinator behavior.
- Python strings containing private descriptor material cannot be reliably zeroized.
- Wallet encryption is not implemented.
- Physical/firmware compromise is outside the helper's ability to detect.
- Exact support depends on the pinned Core version's descriptor implementation.

## Maintenance rule

1. Prefer Core validation over custom policy parsing.
2. Re-review every generator change.
3. Keep OS behavior in `tails.sh`.
4. Keep policy-verification procedures in human documentation.
5. Retest every Core-version change.
