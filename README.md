# Bitcoin Core Multisig Quorum Signer

**Create one Bitcoin Core signer for a multisig quorum, with support for BIP87 and BIP48 native-P2WSH cosigners.**

Built using the [Bitcoin Core Feature Overlay](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay) at revision `632648b88cdb867ab6372e2850e8a53d00f58552`: minimal Core-facing logic, a separate Tails launcher, and separate human/audit documentation.

The utility creates one blank Core signer wallet, exports its public BIP87 account key as text + QR, then imports the completed multisig policy so the wallet can sign PSBTs as one member of the quorum.

## Get the project

```sh
git clone https://github.com/Jakob-997/Bitcoin-Core-Multisig-Quorum-Signer.git
```

The project files live at the repository root. If using GitHub's ZIP download, extract it and rename the folder to `Bitcoin-Core-Multisig-Quorum-Signer` to match the layout below.

## Quick start

> **For a real signer:** use dedicated hardware that is physically air-gapped where practical. The launcher's software networking shutdown is defense in depth.

```text
1. Verify Tails and Bitcoin Core v32.0rc2.
2. Put the Bitcoin-Core-Multisig-Quorum-Signer folder next to:
   bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz
3. Read PRE-CREATION-GUIDE.txt.
4. In Tails, make tails.sh executable and choose "Run as a Program".
5. Add the displayed BIP87 key to your multisig quorum.
6. Paste the completed public quorum descriptor into the signer.
7. Follow POST-CREATION-GUIDE.txt to back up, restore, verify, and test it.
```

Expected layout:

```text
your-folder/
├── bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz
└── Bitcoin-Core-Multisig-Quorum-Signer/
    ├── tails.sh
    ├── generator.py
    ├── PRE-CREATION-GUIDE.txt
    ├── POST-CREATION-GUIDE.txt
    ├── DESIGN.md
    ├── AUDITING.md
    ├── AUDIT.md
    ├── README.md
    └── UPSTREAM.md
```

Use **Bitcoin Core v32.0rc2 exactly**. Another release must be tested and reviewed before changing the pin.

## Design at a glance

- Bitcoin Core generates, derives, validates, and stores the keys.
- This Core signer uses BIP87 account 0.
- Other quorum members may use BIP87 or BIP48 native-P2WSH (`m/48h/coin_typeh/accounth/2h`) account keys.
- The quorum is native SegWit `wsh(sortedmulti())`.
- Only this signer's account key becomes private inside its imported multisig descriptor.
- The public signer key is displayed with Tails' installed `qr` command.
- The helper contains no custom cryptography.

## Three layers

| Layer | File | Responsibility |
| --- | --- | --- |
| Generator | [generator.py](generator.py) | Core RPC flow and signer construction |
| Tails launcher | [tails.sh](tails.sh) | Network shutdown, pinned Core verification/extraction, isolated runtime |
| Human procedure | [PRE-CREATION-GUIDE.txt](PRE-CREATION-GUIDE.txt) / [POST-CREATION-GUIDE.txt](POST-CREATION-GUIDE.txt) | Preparation, backup, restore, verification, test spend |

The generator is the primary executable review target. Tails/environment changes belong in the launcher; operating procedure changes belong in the guides.

## Signer key

The public key shown to the coordinator is:

```text
[fingerprint/87h/0h/0h]xpub...
```

Supported test networks use coin type 1.

The completed descriptor must have the form:

```text
wsh(sortedmulti(M,[origin]xpub/<0;1>/*,...))
```

Accepted signer origins are:

```text
BIP87: [fingerprint/87h/coin_typeh/accounth]xpub/<0;1>/*
BIP48: [fingerprint/48h/coin_typeh/accounth/2h]xpub/<0;1>/*
```

For BIP48, only script type `2h` is accepted because this utility creates native P2WSH `wsh(...)` multisig. The nested-SegWit BIP48 `1h` branch corresponds to `sh(wsh(...))` and is intentionally rejected.

## Provenance

Migrated from `Jakob-997/Core-Helper` at commit `ecce55d21de90df059f6bf49dab6847badf721b7`, directory `utilities/core-multisig-signer/`. See [UPSTREAM.md](UPSTREAM.md) for the immutable source link, canonical overlay revision, and preserved executable identities. The existing [audit record](AUDIT.md) and its testing limitations are retained unchanged.

The internal default wallet name and launcher runtime prefix remain `core-multisig-signer`; the output directory remains `signer-wallets/`. Renaming the repository does not change signer construction or wallet behavior.

## Read more

- [DESIGN.md](DESIGN.md) — architecture, trust model, descriptor construction, private-key boundary
- [AUDITING.md](AUDITING.md) — review method inherited from Bitcoin Core Feature Overlay
- [AUDIT.md](AUDIT.md) — exact reviewed executable revisions, findings, limitations
- [PRE-CREATION-GUIDE.txt](PRE-CREATION-GUIDE.txt) — preparation checklist
- [POST-CREATION-GUIDE.txt](POST-CREATION-GUIDE.txt) — backup, restore, address verification, PSBT test

**This utility has received AI-assisted review but no independent professional security audit.**
