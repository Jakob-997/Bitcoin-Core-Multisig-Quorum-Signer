# Bitcoin Core Descriptor Signer Design

This follows the Feature Overlay's three layers: generator.py for Core RPC logic, tails.sh for OS/runtime enforcement, and guides for human verification and backup.

## Step 1: create and export

Create a new blank private descriptor wallet, use `addhdkey` for a root, and `derivehdkey` for a BIP87 or BIP48 native-P2WSH account. Derive the private account through Core and import it as `unused([origin]xprv)`. Verify through `gethdkeys` that Core stores the account privately with the exact public descriptor, then display the public `[origin]xpub` and QR. The step returns successfully without requiring a public wallet policy.

The private account lives in Core's wallet, so no custom recovery/session format is needed. Creating a signer refuses an existing wallet name. Backups and persistent wallet storage are required before shutting down Tails.

## Step 2: select and import

Select a wallet returned by `listwalletdir`, load it if necessary, and require a private-key descriptor wallet. Parse the complete public descriptor through `getdescriptorinfo`; reject private input. Use Core's full `multipath_expansion` or single `descriptor`.

Require one exact descriptor extended public key to appear in every branch and have `has_private=true` in the selected wallet's `gethdkeys` inventory. Only after that public ownership check, request the private inventory from Core, and select the matching xprv. No wallet or key is created by this step. When several owned keys qualify, one is used; this helper adds one local signer, not all possible local signatures.

For each missing public branch, replace every exact occurrence of the chosen xpub, preserving any Core-canonical origin and child suffix. Core must recognize private keys and canonicalize the substituted branch back to exactly the original public descriptor, without introducing multipath expansion. Only then import it. Origin annotations do not establish ownership; the exact xpub and private/public equality do. Human origin and policy verification remain necessary.

Ranged pkh, wpkh, sh, wsh, and tr policies with at most two branches are activated for address generation. This classification affects activation only; other valid descriptor shapes remain accepted for signing. Exactly two multipath branches use Core's second-branch internal convention. Existing inactive address-capable branches are reimported with the same private key and preserved timestamp, range and next index. Existing active branches are skipped. Finally, gethdkeys verifies private ownership, all public branches and expected activation state.

## Interruption

Core persists the wallet and account between steps. Step 2 can be interrupted and run again with the selected wallet and same public descriptor. Imports are not transactional across branches: completed branches stay in Core and are verified/skipped on retry. No separate checkpoint controls the policy; the user supplies the policy for each run. Do not fund a partial import before whole-policy verification.

Step 1 interrupted before account storage/export is not claimed complete. Preserve that wallet for inspection; step 1 does not overwrite it. Recovery cannot reconstruct lost private material.

## Runtime lifecycle

With no argument, the launcher displays the two operations and reads the literal word create or import, retrying invalid choices. EOF exits before any OS/network action. Explicit create/import command arguments bypass the prompt.

The launcher verifies the pinned v32.0rc2 archive, starts one offline foreground Core child using fresh runtime state, and selects the persistent wallet directory. It waits for its own child's clean shutdown without terminating unrelated Core processes. Successful step completion and clean shutdown permit deletion of the fresh extraction. Failure/interruption retains the extraction and wallet output; failed shutdown retains runtime too. The source project and original archive remain available.

## Scope and trust

Core owns randomness, BIP32, descriptors, Miniscript, wallet storage, and signing. The helper owns the RPC sequence, wallet selection, exact xpub substitution, public-policy equality, verified postconditions, and runtime isolation. There is no multisig/policy whitelist or custom cryptography.

Core parser and wallet-import restrictions still apply. Ownership lookup requires an HD xpub stored privately in the wallet; arbitrary fixed hex public keys or unstored descendants are not discovered. Ownership of one key does not imply enough signatures to spend every policy path. Thresholds, cosigners, timelocks, recovery semantics, and transaction details remain human/coordinator checks.

Private inventory from Core is briefly held in Python memory and passed over stdin, never intentionally persisted or printed by the helper. Python strings cannot be reliably zeroized. Wallet encryption and physical/firmware compromise are outside this implementation. Pin changes require retesting the exact Core build. Keep Core logic small, OS changes in the launcher, and procedures in the guides.

Expert shortcuts: the menu labels are (c)reate and (i)mport. Type c or C for create, or i or I for import. Full words still work. The same letters can be supplied as launcher arguments (for example, sh tails.sh c).
