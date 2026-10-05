# Bitcoin Core Liana Timelock Signer

Use Bitcoin Core as one signer in a **Liana P2WSH timelocked Miniscript wallet**.

This is an isolated [Bitcoin Core Feature Overlay](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay) path. It is intentionally separate from the repository's ordinary `wsh(sortedmulti())` quorum signer so each policy class stays small and auditable.

## Supported scope

Version 1 accepts public Liana descriptors that are:

- top-level `wsh(...)`;
- ranged and solvable according to Bitcoin Core;
- Miniscript policies containing at least one `older(...)` recovery timelock;
- using this Core signer as either a BIP87 account key or a BIP48 native-P2WSH account key.

Taproot `tr(...)` Liana descriptors are intentionally rejected for now.

Bitcoin Core v32.0rc2 parses the Miniscript descriptor. This helper does **not** implement a Miniscript parser.

## Choose the Core signer key type

At setup, choose one:

```text
1. BIP87
   m/87h/coin_typeh/0h

2. BIP48 native-P2WSH
   m/48h/coin_typeh/0h/2h
```

Your example Liana descriptor uses both conventions in one policy:

```text
wsh(or_d(
  pk([BIP48 origin]xpub/<0;1>/*),
  and_v(
    v:pkh([BIP87 origin]xpub/<0;1>/*),
    older(...)
  )
))
```

So if Core is the recovery signer, choose BIP87. If Core is the immediate-spend signer, choose BIP48.

Liana may reuse the same account xpub in multiple spending paths with different unhardened suffixes. The helper supports that and replaces only exact occurrences of this signer's selected account identity.

## Quick start

Expected layout:

```text
Bitcoin-Core-Multisig-Quorum-Signer/
├── bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz
└── liana-timelock-signer/
    ├── tails.sh
    ├── generator.py
    ├── PRE-CREATION-GUIDE.txt
    ├── POST-CREATION-GUIDE.txt
    ├── DESIGN.md
    ├── AUDITING.md
    ├── AUDIT.md
    └── README.md
```

Then in Tails:

```sh
chmod +x liana-timelock-signer/tails.sh
./liana-timelock-signer/tails.sh
```

The flow:

1. Choose BIP87 or BIP48 for this Core signer.
2. Core generates a fresh signer root.
3. Core derives the selected account.
4. The public signer expression is shown as text + QR.
5. Add that key to the Liana policy.
6. Export the complete PUBLIC Liana descriptor.
7. Paste it into this signer.
8. Core parses/canonicalizes the descriptor.
9. The helper substitutes only this signer's exact account identity with its xprv in memory.
10. Core must canonicalize the private form back to the identical public descriptor before import.
11. Back up, restore, verify addresses, and test with disposable funds.

## Important limitation

This tool verifies only a narrow structural contract:

- P2WSH;
- ranged/solvable according to Core;
- at least one `older()`;
- this signer appears with the expected selected account identity;
- private substitution does not change the public descriptor.

It does **not** determine whether the Liana policy is sensible, whether the timelock values are what you intended, or whether the recovery paths are safe. Verify those independently in Liana.

See [DESIGN.md](DESIGN.md) and [AUDIT.md](AUDIT.md).
