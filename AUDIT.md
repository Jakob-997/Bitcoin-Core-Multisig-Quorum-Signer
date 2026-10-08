# Audit Record

Review date: 2026-10-07
Base project: `dab58d8676a5fa29f159eef5f384b400f3030e75`
Feature Overlay reviewed: `5011c687c4c10ce9f70bef4dfbac9dfe89825406`
Generator blob: `3fd857311bbd2df343c7895eb7f2edfdce455eee`
Launcher blob: `08d29a5ca29b7d3b48f43aaa1a21bde19e367d4e`
Core version: v32.0rc2
Core source: `bc795e60dbb2c6e9c9556949731912429290626a`
Linux archive SHA-256: `0255103718033e6aee15fa944717fc277e047b845bff1e7408af0ea732d8d0c1`

This is AI-assisted source/security review, not an independent professional audit. Method: [AUDITING.md](AUDITING.md).

## Current implementation

With no argument, sh tails.sh shows (c)reate and (i)mport, accepting create/c/C or import/i/I and retrying invalid choices. Blank input does not trigger creation. EOF exits before network/runtime actions. The full-word and single-letter command shortcuts remain available.

Two independent operations replace the continuous create/import flow and custom recovery session. `sh tails.sh create` creates a new private descriptor wallet, derives a BIP87 or BIP48 account through Core, stores the private account as `unused([origin]xprv)` in Core, verifies it, and exports the public identity/QR. It finishes without asking for a public policy.

`sh tails.sh import` selects an existing wallet, validates a public descriptor with Core, and requires an exact descriptor xpub that the selected wallet holds privately in every Core-expanded branch. Only after ownership is checked does the generator request Core's private inventory and substitute one matching account key. Every substituted branch must canonicalize to the exact original public descriptor. Origin annotations and child suffixes are preserved; ownership depends on the exact xpub, not a policy shape or particular origin annotation. No wallet or replacement key is created during import.

Core parses the policy; there is no multisig/Miniscript whitelist or custom cryptography. Supported ranged address policies are active; other forms, including combo, remain available for signing. Core wallet-import restrictions still apply. Core's two-branch internal convention and full multipath expansion are preserved. Existing active branches are verified/skipped, preserving range, next index and timestamp; inactive address policies are repaired on reimport; interruption between branches is retried with the same wallet and supplied descriptor.

Sensitive inputs use bitcoin-cli stdin and private/public-descriptor errors are redacted. Private inventory is briefly held in Python memory; it is not intentionally printed, persisted, passed in argv, copied to clipboard, or QR encoded. Python strings cannot be reliably zeroized. Core owns wallet storage.

The launcher hash-verifies the unchanged archive pin, freshly extracts Core, disables NetworkManager networking, and starts one offline foreground child in fresh runtime state with the persistent wallet directory. It stops and waits only for its own child. Each successfully verified step plus clean Core shutdown removes that run's extraction. Failed/interrupted runs retain extraction and wallet output; failed shutdown retains runtime state too. Project and original archive are preserved. Wallet names prevent accidental overwriting; multiple newly named wallets can share the directory.

## Executed verification

- Eight security/boundary tests passed on Windows Python 3.14 and Ubuntu Python 3.12. These cover private/rejected input redaction, stdin-only secrets, public-policy mismatch preventing import, ownership rejection before private export, exact xpub matching, origin preservation, every multipath branch, and verified postconditions.
- Against the hash-verified actual Linux Core v32.0rc2 archive on a fresh offline regtest node: 22 full create/import combinations passed, covering 11 forms for both account types. Forms include wpkh, fixed pkh, ranged pk, combo, Taproot, sortedmulti P2WSH, repeated-key Liana-style Miniscript, two- and three-branch multipath, Taproot multipath with a script tree, and sh(wpkh). The final two-step ownership/import path was exercised, not just the import helper. Wallet unload/reload verification also passed.
- Both account types passed independent create/export, wallet selection after unload, wrong-wallet rejection, interruption after an actual first-branch import, retry importing only the missing branch, and verification-only repeated import. An existing active descriptor with a custom range and next index retained its complete public state.
- Four process-level cases passed: step 1 completed in its own process, Core restarted, step 2 was interrupted before import by actual SIGINT or after a successful first-branch import by a simulated KeyboardInterrupt, Core restarted again, and a new step-2 process completed with the same account key. Repeated import left listdescriptors unchanged. Both interruption points were tested for BIP87 and BIP48.
- POSIX syntax and ten isolated launcher scenarios passed: success, archive failure, extraction failure, an existing wallet directory during creation, startup failure, generator failure, interruption, failed shutdown, independent import, and import with missing wallet directory. Command doubles verify preservation/removal boundaries; these do not operate Tails desktop services.
- Complete patch applies cleanly to the base commit; source archive contains only source, documentation, and tests.

Commands: `python -m unittest discover -s tests -v`; on Ubuntu set CORE_TEST_CLI to a wrapper selecting a fresh offline regtest node for actual-Core cases. `python3 tests/test_launcher.py -v` runs isolated launcher scenarios.

Core contracts reviewed at the pinned commit: src/rpc/output_script.cpp (canonicalization/expansion), src/wallet/rpc/backup.cpp (import restrictions and multipath internal convention), and src/wallet/rpc/wallet.cpp (unused account storage, derivation and private-key inventory).

The final word-menu edit was tested using the bundled POSIX shell on Windows: fifteen cases passed (full words, lower/upper single letters, invalid/blank/numeric choices followed by a valid word, full-word and letter argument shortcuts, EOF, and invalid argument). The full script was executed with command doubles that stopped at the first OS action, so no actual networking changed. Shell syntax passed. The earlier full ten-case launcher/Core tests preceded this menu-only edit; the generator is unchanged. The expanded seventeen-case POSIX launcher suite was not rerun because WSL access was denied in the current environment.

## Remaining target-system checks and limits

Not executed: full Tails GUI/network-isolation workflow, sudden power loss/SIGKILL, actual PSBT signing, independent backup/restore, or every possible Core descriptor. Reload/restart tests are not backup/restore tests. Before meaningful funds, test actual signing for every intended spending/recovery path and independent backup restore/address agreement.

Ownership lookup requires an exact HD xpub stored privately in the selected wallet. Arbitrary fixed hex public keys and unstored descendants are not discovered. Ownership of one key does not prove enough signatures to spend or intended policy correctness. Thresholds, origins, cosigners, timelocks, recovery paths and transaction details remain independent human/coordinator checks.

Wallet output must survive Tails shutdown on secure persistent/offline media. No session file is required. An interrupted step 1 before account storage/export is not claimed complete and is never silently overwritten. Lost private material cannot be recreated. Wallet encryption and physical/firmware compromise are outside this implementation. Retest any Core pin change and record new executable hashes.

## Import public-key display follow-up

The selected wallet's public account key and origin are displayed before the descriptor prompt. The display uses public gethdkeys only, deduplicates repeated account keys, and omits the unused master root when account origins are available. A regression test verifies prompt order, selected-wallet lookup, and exclusion of private and watch-only keys. Windows suite: ten tests passed, four environment-dependent tests skipped. Earlier actual-Core evidence above predates this display-only change.

## Address generation correction

Supported ranged address policies now activate receive/change descriptors. Reimport repairs previous inactive imports while preserving timestamp, range and next index. Other valid forms remain importable for signing. Windows regression tests cover new two-of-two imports, inactive repair, non-address policies and preservation of reimport parameters. Twelve tests passed; five integration/environment tests skipped. A real-Core two-of-two receive/change and retry test was added but could not be executed because WSL access is denied. Earlier real-Core results predate this correction.
