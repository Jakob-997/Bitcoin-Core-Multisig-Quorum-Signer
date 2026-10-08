# Bitcoin Core Descriptor Signer

Create an offline signer, then import its public descriptor in a separate run.

Built using the [Bitcoin Core Feature Overlay](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay), reviewed against revision `5011c687c4c10ce9f70bef4dfbac9dfe89825406`. The repository slug is retained for continuity.

## Two independent steps

Verify Tails and the pinned Bitcoin Core v32.0rc2 archive. Put the archive beside this project folder, read PRE-CREATION-GUIDE.txt, and run:

```sh
sh tails.sh
```

At the prompt, type `create` to create a wallet and export its public key. Type `import` to select an existing wallet and import a public descriptor. Invalid choices are retried; blank input never creates a wallet.

Choose a new wallet name and BIP87 (`m/87h/coin_typeh/0h`) or BIP48 native-P2WSH (`m/48h/coin_typeh/0h/2h`). Core generates the root and derives the account. The account's private key is stored in Core using an `unused()` descriptor; the public `[origin]xpub` is displayed as text and QR. Step 1 then finishes without asking for a wallet policy.

Back up the wallet and keep `descriptor-signer-wallets/` on secure persistent/offline media before shutting down Tails. An ordinary temporary Tails home does not survive shutdown. Add the displayed public key to your coordinator's policy whenever ready.

Later, run `sh tails.sh` again and type `import`. You can also skip the prompt using `sh tails.sh create` or `sh tails.sh import`.

Select an existing wallet from the list. The import step displays its public account key again, including its origin, before asking you to paste the complete PUBLIC descriptor. Core must report that this wallet holds the private key for an exact descriptor xpub in every expanded branch. An unrelated or watch-only wallet is rejected. The helper substitutes that wallet-owned private key only in memory, proves that Core's canonical public policy is unchanged, imports the missing branches, and verifies the result.

The steps depend on Core's wallet files, not a separate session/checkpoint file. A restored private descriptor wallet with a matching stored HD account key can also be selected. Step 2 never creates a wallet or generates a replacement key. A key represented only as a derived fixed hex public key, or an account xpub not stored in the selected wallet, is outside this helper's ownership lookup.

## Interruptions and repeated import

Press Ctrl-C or close the terminal if step 2 must stop. Keep the wallet output, rerun `sh tails.sh import`, select the same wallet, and paste the same descriptor. Branches already present are verified and skipped; missing branches are imported. Repeated import preserves the existing branches' range, next index, timestamps, and active state. A partially imported wallet must not be funded until the whole policy passes verification.

Step 1 refuses an existing wallet name; use a new name for a new signer. Each successful step shuts down its own Core process cleanly and removes its fresh temporary extraction. Failure or interruption retains the extraction and wallet output; failed shutdown retains runtime state too. The project and original archive are preserved. Close conflicting Core instances before running the launcher.

## Descriptor acceptance and security

There is no policy-shape whitelist: Core parses multisig, Miniscript, Taproot, combo, fixed, and multipath forms. The descriptor must be public, contain an exact HD xpub privately held by the selected wallet, preserve its public policy after substitution, and pass Core wallet import. Parser acceptance alone does not guarantee import; for example, a cosigner's hardened derivation may need unavailable private keys.

Core expands multipath descriptors. Every branch is checked and imported separately; for exactly two branches, the second is internal, matching Core's convention. Newly imported descriptors are inactive for signing, avoiding address-generation restrictions such as ranged `combo()`. Existing branches retain their active state. Use the coordinator to generate addresses. New ranged imports use Core's default keypool range; extend it through Core if needed.

Origin annotations and child suffixes from the public policy are preserved exactly after Core canonicalization. Ownership is bound to the exact xpub, rather than requiring a particular origin annotation or policy shape. Independently check fingerprints, origins, thresholds, timelocks, recovery paths, and addresses before funding. Successful import does not prove policy intent.

Sensitive RPC input uses stdin, and potentially sensitive errors are redacted. Private keys are not intentionally printed, QR encoded, or written by the helper. Python strings cannot be reliably zeroized, and Core's private-key inventory is briefly held in memory during import. Wallet encryption is not implemented.

## Tests and review

Run `python3 -m unittest discover -s tests -v`. Launcher tests require a POSIX environment and use isolated command doubles. For real-Core tests, set `CORE_TEST_CLI` to an executable wrapper selecting a fresh offline v32.0rc2 regtest node with an empty wallet directory. Tests create disposable wallets.

See [DESIGN.md](DESIGN.md), [AUDITING.md](AUDITING.md), and [AUDIT.md](AUDIT.md) for design and test evidence. The generator owns Core RPC logic, tails.sh owns OS/runtime behavior, and the guides own human verification/backup procedures. AI-assisted review only; no independent professional security audit has been performed.

Expert shortcuts: the menu labels are (c)reate and (i)mport. Type c or C for create, or i or I for import. Full words still work. The same letters can be supplied as launcher arguments (for example, sh tails.sh c).
