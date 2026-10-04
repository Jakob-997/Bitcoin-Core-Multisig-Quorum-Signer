# Standalone project provenance

**Project:** Bitcoin Core Multisig Quorum Signer  
**Repository:** https://github.com/Jakob-997/Bitcoin-Core-Multisig-Quorum-Signer  
**Migration date:** 2026-10-04

## Source project

Imported from [Jakob-997/Core-Helper, utilities/core-multisig-signer/](https://github.com/Jakob-997/Core-Helper/tree/ecce55d21de90df059f6bf49dab6847badf721b7/utilities/core-multisig-signer) at commit `ecce55d21de90df059f6bf49dab6847badf721b7`.

This repository starts with a snapshot of that project. Earlier development history remains in Core-Helper at the immutable source link above.

## Canonical Bitcoin Core Feature Overlay

Canonical repository: [Jakob-997/Bitcoin-Core-Feature-Overlay](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay).

Canonical revision retained: [`632648b88cdb867ab6372e2850e8a53d00f58552`](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay/tree/632648b88cdb867ab6372e2850e8a53d00f58552).

The generator, separate Tails launcher, human guides, design document, audit guidance, and audit record preserve the existing three-layer organization. This migration does not adopt a newer overlay revision.

## Preserved executable and audit identities

| Item | Preserved value |
| --- | --- |
| generator.py Git blob | `7bcca4968217d8f338ce563c7156329f6d0d5b8e` |
| tails.sh Git blob | `10a80630066599b429a3bafa2914bad2d6cb2d32` |
| AUDIT.md Git blob | `803e3cff61e0d42f750345a00a7e45069a859680` |
| Bitcoin Core release | `v32.0rc2` |
| Bitcoin Core source commit | `bc795e60dbb2c6e9c9556949731912429290626a` |
| Linux x86_64 archive SHA-256 | `0255103718033e6aee15fa944717fc277e047b845bff1e7408af0ea732d8d0c1` |

`generator.py`, `tails.sh`, `AUDITING.md`, and `AUDIT.md` are unchanged from the source snapshot. The project title, clone instructions, project-folder examples, and provenance are updated for the standalone repository. The post-creation checklist now explicitly names the already-supported BIP48 native-P2WSH cosigner paths alongside BIP87.

The internal default wallet name and runtime prefix remain `core-multisig-signer`, and wallet output remains `signer-wallets/`. These identifiers are intentionally retained to preserve executable behavior and the reviewed blobs.

## Migration verification and limits

Verified all eight source project files are present at the repository root, the four unchanged files match their source bytes, the generator parses as Python, and relative Markdown document links resolve locally. The executable blob identities match the inherited audit record.

This is a repository/documentation migration, not a new security audit. The historical testing claims and limitations in [AUDIT.md](AUDIT.md) remain unchanged. No real Tails/Core daemon, backup/restore, or PSBT end-to-end test was performed for this migration. In particular, the inherited BIP48 mocked-flow retest remains outstanding.

## Future updates

Review upstream overlay changes explicitly before adopting them. Preserve the generator/launcher/procedure boundaries, record exact adopted revisions and executable hashes, and retest and re-review any Core version-pin change as required by [AUDITING.md](AUDITING.md).
