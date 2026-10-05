# Bitcoin Core Descriptor Signer

**Create an offline Bitcoin Core signer and attach it to any public descriptor that Bitcoin Core itself accepts.**

Built using the [Bitcoin Core Feature Overlay](https://github.com/Jakob-997/Bitcoin-Core-Feature-Overlay) at revision `632648b88cdb867ab6372e2850e8a53d00f58552`.

The helper no longer tries to understand or whitelist wallet-policy shapes such as `wsh(sortedmulti(...))`, Liana Miniscript, or Taproot. Bitcoin Core is the descriptor parser. The helper's job is only to create one local signer key, bind that exact key to the supplied public descriptor, substitute its xprv in memory, and prove that substitution did not change the public descriptor.

## Get the project

```sh
git clone https://github.com/Jakob-997/Bitcoin-Core-Multisig-Quorum-Signer.git
```

The repository slug is retained for continuity; the project itself is now the more general **Bitcoin Core Descriptor Signer**.

## Quick start

> For meaningful funds, use dedicated physically air-gapped hardware where practical. Software networking shutdown is defense in depth.

```text
1. Verify Tails and Bitcoin Core v32.0rc2.
2. Put this project folder next to:
   bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz
3. Read PRE-CREATION-GUIDE.txt.
4. Run tails.sh.
5. Choose the account convention this Core signer should export.
6. Add the displayed public key to your wallet policy/coordinator.
7. Paste the complete PUBLIC descriptor back into the signer.
8. Back up, restore, independently verify the policy/addresses, and test with disposable funds.
```

## Local signer account

Choose one:

```text
BIP87:
m/87h/coin_typeh/0h

BIP48 native-P2WSH:
m/48h/coin_typeh/0h/2h
```

This choice controls only **this Core signer's key**. Other keys and the descriptor policy are not restricted by this helper.

For your Liana example, the recovery signer uses BIP87 and the immediate-spend signer uses BIP48, so choose whichever role this Core signer is taking.

## Descriptor acceptance

The signer accepts any **public descriptor that Bitcoin Core v32.0rc2 accepts** and that contains this signer's exact account identity.

Examples can include:

- `wsh(sortedmulti(...))`;
- Miniscript such as Liana `wsh(or_d(...older(...)))`;
- Taproot `tr(...)`, if Core accepts the descriptor and the local account key is represented in a compatible descriptor-key position;
- other Core-supported descriptor forms.

The helper does not interpret the policy. It does not check whether thresholds, timelocks, recovery paths, or other cosigner keys are what you intended.

## Security invariant

Before import:

1. Core parses/canonicalizes the public descriptor.
2. The exact local `[origin]xpub` identity must appear.
3. Only exact occurrences of that identity are replaced with the matching xprv.
4. Core parses the private form.
5. Core's canonical public descriptor and multipath expansion must be **identical** to the originals.
6. Only then is the private descriptor imported.

Sensitive descriptor material is sent to `bitcoin-cli` through stdin, not argv.

## Three layers

| Layer | File | Responsibility |
| --- | --- | --- |
| Generator | [generator.py](generator.py) | Core RPC flow, local signer binding, descriptor invariant |
| Tails launcher | [tails.sh](tails.sh) | Network shutdown, pinned Core extraction, isolated runtime |
| Human procedure | pre/post guides | Policy verification, backup, recovery, test signing |

See [DESIGN.md](DESIGN.md) and [AUDIT.md](AUDIT.md).

**AI-assisted review only; no independent professional security audit has been performed.**
