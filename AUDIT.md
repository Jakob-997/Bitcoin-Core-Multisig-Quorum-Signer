# Audit Record

**Bitcoin Core Feature Overlay revision:** `632648b88cdb867ab6372e2850e8a53d00f58552`  
**Generator blob:** `d204101565532767463ff31e51158f934e3d8e6e`  
**Tails launcher blob:** `10a80630066599b429a3bafa2914bad2d6cb2d32`  
**Bitcoin Core version reviewed:** `v32.0rc2`  
**Bitcoin Core commit:** `bc795e60dbb2c6e9c9556949731912429290626a`  
**Review date:** 2026-10-04

This is an AI-assisted source/security review record, not an independent professional security audit. Review method: [AUDITING.md](AUDITING.md).

## Current design

The signer is descriptor-agnostic.

Bitcoin Core `getdescriptorinfo` is the policy parser. The helper no longer contains a custom `wsh(sortedmulti())` or Miniscript/Liana parser.

The local Core signer may export one of:

```text
BIP87:
m/87h/coin_typeh/0h

BIP48 native-P2WSH:
m/48h/coin_typeh/0h/2h
```

## Construction reviewed

1. Create a blank private-key-enabled descriptor wallet.
2. Core generates/stores a fresh HD root using `addhdkey`.
3. Core derives the selected local account with `derivehdkey`.
4. Export only the public `[origin]xpub` identity.
5. Pass the complete PUBLIC descriptor to Core `getdescriptorinfo`.
6. Reject supplied descriptors containing private keys.
7. Require the canonical public descriptor to contain this exact local `[origin]xpub`.
8. If the same xpub appears with another/ambiguous origin, abort.
9. Core derives the matching local account xprv internally.
10. Replace every exact occurrence of the local identity with the xprv, preserving descriptor syntax and child suffixes.
11. Pass the private form back to Core `getdescriptorinfo`.
12. Require identical canonical public `descriptor` and identical `multipath_expansion`.
13. Import the descriptor through stdin.
14. Use `gethdkeys` to require the local account xpub is private/signable and attached to the exact imported public descriptor.

## Security properties reviewed

- No custom cryptographic primitives are implemented.
- No custom wallet-policy or Miniscript parser is implemented.
- Bitcoin Core generates and derives the local signing key.
- Bitcoin Core parses and canonicalizes the descriptor.
- Sensitive RPC material is passed through `bitcoin-cli -stdin`, not argv.
- The xprv/private descriptor are not intentionally printed, persisted by the helper, copied to clipboard, or QR encoded.
- Private-RPC errors suppress potentially sensitive response text.
- Substitution is bound to the exact local origin+xpub identity, not a bare global xpub replacement.
- Multiple exact occurrences of the same local identity are allowed.
- Public-policy equality is checked after private substitution.
- The launcher disables NetworkManager networking and also starts Core with `-networkactive=0 -listen=0`.
- The pinned Core archive is SHA-256 verified and freshly extracted.
- Temporary HOME/runtime state is under `/dev/shm`.
- Existing `signer-wallets/` output is not reused.

## Why the policy parser was removed

Earlier versions restricted descriptors to `wsh(sortedmulti(...))` and then added BIP48 cosigner exceptions.

That became counterproductive for richer Core-supported descriptors such as Liana Miniscript:

```text
wsh(or_d(pk(...),and_v(v:pkh(...),older(...))))
```

The safer/smaller design is to let Core decide whether descriptor syntax is valid and keep the helper focused only on the local private-key boundary.

**Status:** implemented.

## Descriptor scope

The helper is intended to accept any public descriptor that the pinned Core version accepts **and that contains this local signer account identity**.

A Core-valid descriptor can still encode a dangerous or unintended policy. The helper does not validate:

- threshold correctness;
- cosigner identity beyond the local signer;
- timelock values;
- recovery semantics;
- Taproot script-tree intent;
- whether the coordinator policy matches what the user meant.

Those remain human/coordinator verification responsibilities.

## Testing status

Historical testing before the descriptor-agnostic rewrite included Python syntax checking and a mocked Core RPC flow for the earlier multisig-specific generator.

The current generator rewrite has been source-reviewed here, but has **not yet** been rerun through:

- target-Tails Python execution;
- mocked end-to-end Core RPC flow;
- real Bitcoin Core v32.0rc2 daemon;
- the supplied Liana descriptor pattern;
- Taproot descriptor cases;
- fixed non-ranged descriptor cases;
- real PSBT signing;
- backup/restore.

Do not treat the current revision as production-ready for meaningful funds until those tests are completed.

## Still required before meaningful funds

At minimum test:

1. BIP87 `wsh(sortedmulti())`;
2. BIP48 `wsh(sortedmulti())`;
3. a Liana-style P2WSH Miniscript descriptor with `older()`;
4. a descriptor where the same local account identity appears multiple times;
5. a supported Taproot descriptor, if you intend to use one;
6. backup/restore and address agreement;
7. real disposable-funds PSBT signing for each intended policy path.

## Accepted limitations

- No independent professional audit has been performed.
- Python private strings cannot be reliably zeroized.
- Wallet encryption is not implemented.
- The coordinator/policy-builder is outside this utility's trust boundary.
- Physical/firmware compromise is outside the helper's ability to detect.
- Support is tied to the exact descriptor behavior of the pinned Core release.

## Upstream references

- Bitcoin Core v32.0rc2 source
- Bitcoin Core `doc/descriptors.md`
- Bitcoin Core wallet RPCs: `createwallet`, `addhdkey`, `derivehdkey`, `gethdkeys`, `importdescriptors`
- Bitcoin Core `getdescriptorinfo`
- BIP32
- BIP48
- BIP87
- BIP174
- BIP379 Miniscript descriptors

## Maintenance rule

1. Prefer Core descriptor validation over custom policy parsers.
2. Re-review every generator change.
3. Keep OS behavior in `tails.sh`.
4. Keep human policy-verification requirements in the guides.
5. Retest every Core-version change.
6. Record new executable blob hashes after security-relevant changes.
