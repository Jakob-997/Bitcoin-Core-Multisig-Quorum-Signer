# Provenance

Originally imported from [Core-Helper](https://github.com/Jakob-997/Core-Helper/tree/ecce55d21de90df059f6bf49dab6847badf721b7/utilities/core-multisig-signer) at `ecce55d21de90df059f6bf49dab6847badf721b7`.
The workflow uses the [Bitcoin Core Feature Overlay](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay) pattern, previously reviewed at `5011c687c4c10ce9f70bef4dfbac9dfe89825406`.

The helper delegates keys, derivation, policy parsing, storage, and signing to Core. Python supplies the two setup actions; the launcher supplies the offline runtime.

Pinned build: Bitcoin Core v32.0rc2, source `bc795e60dbb2c6e9c9556949731912429290626a`.

Linux x86_64 archive SHA-256:
```text
0255103718033e6aee15fa944717fc277e047b845bff1e7408af0ea732d8d0c1
```

Historical design and audit notes in Git history describe earlier implementations. They are not an audit of this simplified version. No independent professional security audit has been performed.
