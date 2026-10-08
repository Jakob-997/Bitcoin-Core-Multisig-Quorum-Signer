# Standalone project provenance

**Repository:** https://github.com/Jakob-997/Bitcoin-Core-Multisig-Quorum-Signer  
**Migration date:** 2026-10-04

## Original source

Imported from [Jakob-997/Core-Helper, utilities/core-multisig-signer/](https://github.com/Jakob-997/Core-Helper/tree/ecce55d21de90df059f6bf49dab6847badf721b7/utilities/core-multisig-signer) at commit:

```text
ecce55d21de90df059f6bf49dab6847badf721b7
```

The standalone repository has since intentionally diverged from that snapshot.

## Canonical Bitcoin Core Feature Overlay

Canonical repository:

https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay

Overlay revision reviewed for this update:

```text
5011c687c4c10ce9f70bef4dfbac9dfe89825406
```

The three-layer architecture remains:

- `generator.py` — minimal Core-facing feature logic;
- `tails.sh` — environment/isolation/runtime enforcement;
- human/audit documents — preparation, policy verification, backup, recovery, review record.

## Current executable identities

```text
generator.py: 4d490875b15460edbad4f4d833c351227848af20
tails.sh:     08d29a5ca29b7d3b48f43aaa1a21bde19e367d4e
```

The generator is no longer byte-identical to the original Core-Helper snapshot. It was deliberately simplified from a custom multisig-policy parser into a descriptor-agnostic signer that delegates descriptor parsing to Bitcoin Core.

The launcher retains the existing Core v32.0rc2 pin:

```text
Bitcoin Core source commit:
bc795e60dbb2c6e9c9556949731912429290626a

Linux x86_64 archive SHA-256:
0255103718033e6aee15fa944717fc277e047b845bff1e7408af0ea732d8d0c1
```

See [AUDIT.md](AUDIT.md) for current review status and test limitations.
