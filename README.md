# Bitcoin Core Descriptor Signer

Two independent steps on offline Tails. Wallets stay in `descriptor-signer-wallets/` inside this project.

## 1. Create the wallet

```sh
sh tails.sh create
```

Choose a wallet name and BIP87 or BIP48 account. Core creates and stores the signing key. Copy the public `[origin]xpub` from the text or QR into your coordinator.

Back up the wallet on secure persistent/offline storage before shutting down Tails. You can stop here for as long as you need.

## 2. Import the descriptor

```sh
sh tails.sh import
```

Select the existing wallet and paste the coordinator's public descriptor. The helper checks that the wallet owns a signer key, imports the policy, and verifies it. Import never creates a wallet or replacement key.

You can also run `sh tails.sh` for a create/import menu; `c` and `i` are shortcuts.

## Setup and recovery

Put the verified `bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz` archive beside this project folder. The launcher checks the pinned hash, disables networking, and runs Core in a temporary datadir. Python 3, `qr`, and `nmcli` are required.

Both steps use Core's wallet files; no session file is needed. Restore a wallet into `descriptor-signer-wallets/` to import later. If import is interrupted, repeat it with the same wallet and descriptor. Existing branches keep their address indexes, ranges, and timestamps. Supported ranged policies enable receive/change addresses; other policies remain available for signing.

Verify the policy and addresses independently before funding, and test signing and backup restoration with disposable funds. Wallets are unencrypted; private keys briefly enter Python memory during import and cannot be reliably zeroized. Sensitive RPC input goes through stdin and sensitive errors are redacted.

Run tests with `python3 -m unittest discover -s tests -v`. Real-Core integration tests require `CORE_TEST_CLI`, an executable wrapper pointing to an isolated Core 32.x regtest node.

See [UPSTREAM.md](UPSTREAM.md) for provenance and the pinned Core build.
