#!/usr/bin/env python3
"""Create a Core signer wallet, or import its public descriptor in a later run."""
import json
import re
import subprocess
import sys


class RpcError(Exception):
    pass


def rpc(cli, method, *args, wallet=None, sensitive=False):
    command = [cli] + ([f"-rpcwallet={wallet}"] if wallet is not None else [])
    try:
        result = subprocess.run(
            command + ["-stdin", method],
            input="".join(f"{arg}\n" for arg in args),
            text=True, capture_output=True, check=False,
        )
    except OSError:
        raise RpcError("Cannot run bitcoin-cli.") from None
    if result.returncode:
        message = f"{method} failed." if sensitive else result.stderr.strip()
        raise RpcError(message or f"{method} failed.")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RpcError(f"{method} returned an unexpected response.") from None


def key_pattern(xpub):
    # Core parses the policy; this only locates an exact extended key token.
    return re.compile(r"(?<=[(,])(?:\[[^\[\]]*\])?" + re.escape(xpub) + r"(?=[/,)}])")


def verify_signer(cli, wallet, xpub, states):
    keys = rpc(cli, "gethdkeys", '{"active_only":false}', wallet=wallet)
    owned = [key for key in keys if key["xpub"] == xpub and key.get("has_private")]
    if len(owned) != 1:
        raise RpcError("Core does not report the expected private signer key.")
    stored = {item["desc"]: item["active"] for item in owned[0]["descriptors"]}
    if any(desc not in stored or stored[desc] != active for desc, active in states.items()):
        raise RpcError("Core did not store the expected signing descriptors.")


def import_signing_descriptor(cli, wallet, public, private_body, *, active=False,
                              internal=False, previous=None):
    info = rpc(cli, "getdescriptorinfo", private_body, sensitive=True)
    if not info.get("hasprivatekeys") or info["descriptor"] != public:
        raise RpcError("Signing key substitution changed the public descriptor.")
    entry = dict(desc=private_body + "#" + info["checksum"],
                 timestamp="now", active=active, internal=internal)
    # Preserve an existing address cursor when repairing an inactive import.
    for field in ("timestamp", "range", "next_index"):
        if previous and field in previous:
            entry[field] = previous[field]
    result = rpc(cli, "importdescriptors", json.dumps([entry]),
                 wallet=wallet, sensitive=True)
    if len(result) != 1 or not result[0].get("success"):
        raise RpcError("Descriptor import failed. Private material was not printed.")


def create_signer(cli, qr_bin, coin_type):
    wallet = input("Wallet name [core-descriptor-signer]: ").strip() or "core-descriptor-signer"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", wallet) or wallet in {".", ".."}:
        raise RpcError("Use a wallet name with letters, numbers, dots, underscores or hyphens.")
    choice = input("Account: 1 = BIP87, 2 = BIP48 native P2WSH [1]: ").strip() or "1"
    paths = {"1": f"m/87h/{coin_type}h/0h", "2": f"m/48h/{coin_type}h/0h/2h"}
    if choice not in paths:
        raise RpcError("Choose account 1 or 2.")
    rpc(cli, "createwallet", wallet, "false", "true")
    root = rpc(cli, "addhdkey", wallet=wallet)["xpub"]
    account = rpc(cli, "derivehdkey", paths[choice],
                  json.dumps({"hdkey": root, "private": True}),
                  wallet=wallet, sensitive=True)
    public_key = account["origin"] + account["xpub"]
    public = rpc(cli, "getdescriptorinfo", f"unused({public_key})")["descriptor"]
    # Core stores the account so step 2 needs only the wallet, not a session file.
    import_signing_descriptor(cli, wallet, public,
                              f"unused({account['origin']}{account['xprv']})")
    verify_signer(cli, wallet, account["xpub"], {public: False})
    del account
    print(f"\nWallet created: {wallet}\nPublic signer key:\n{public_key}")
    subprocess.run([qr_bin, "--ascii", public_key], check=True)
    print("Back up the wallet. Run sh tails.sh import whenever your descriptor is ready.")


def select_wallet(cli):
    wallets = rpc(cli, "listwalletdir")["wallets"]
    if not wallets:
        raise RpcError("No wallets found. Run sh tails.sh create first.")
    for number, item in enumerate(wallets, 1):
        print(f"  {number}. {item['name']}")
    choice = input("Select wallet number: ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(wallets):
        raise RpcError("Select a wallet number from the list.")
    wallet = wallets[int(choice) - 1]["name"]
    if wallet not in rpc(cli, "listwallets"):
        rpc(cli, "loadwallet", wallet)
    info = rpc(cli, "getwalletinfo", wallet=wallet)
    if not info.get("descriptors") or not info.get("private_keys_enabled"):
        raise RpcError("Select a private-key descriptor wallet.")
    return wallet


def show_wallet_public_keys(cli, wallet):
    keys = rpc(cli, "gethdkeys", wallet=wallet)
    expressions = {
        match.group(0)
        for key in keys if key.get("has_private")
        for desc in key.get("descriptors", [])
        for match in key_pattern(key["xpub"]).finditer(desc["desc"])
    }
    accounts = {key for key in expressions if key.startswith("[")} or expressions
    print("\nPublic signer key(s):\n" + "\n".join(sorted(accounts)))


def import_public_descriptor(cli, wallet, raw):
    info = rpc(cli, "getdescriptorinfo", raw, sensitive=True)
    if info.get("hasprivatekeys"):
        raise RpcError("Paste a public descriptor only.")
    branches = info.get("multipath_expansion") or [info["descriptor"]]
    bodies = [desc.split("#", 1)[0] for desc in branches]
    keys = rpc(cli, "gethdkeys", wallet=wallet)
    owned = [key["xpub"] for key in keys if key.get("has_private") and all(
        key_pattern(key["xpub"]).search(body) for body in bodies
    )]
    if not owned:
        raise RpcError("This wallet does not own a signer key in every descriptor branch.")
    xpub = owned[0]
    pattern = key_pattern(xpub)
    active = len(branches) <= 2 and info.get("isrange", False) and all(
        body.startswith(("pkh(", "wpkh(", "sh(", "wsh(", "tr(")) for body in bodies
    )
    existing = {item["desc"]: item for item in
                rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]}
    states = {desc: bool(active or existing.get(desc, {}).get("active")) for desc in branches}
    pending = [desc for desc in branches
               if desc not in existing or existing[desc]["active"] != states[desc]]
    if pending:
        private_keys = rpc(cli, "gethdkeys", '{"private":true}',
                           wallet=wallet, sensitive=True)
        try:
            private = next(key["xprv"] for key in private_keys
                           if key["xpub"] == xpub and key.get("has_private"))
            for index, (desc, body) in enumerate(zip(branches, bodies)):
                if desc in pending:
                    private_body = pattern.sub(
                        lambda match: match.group(0).replace(xpub, private, 1), body
                    )
                    old = existing.get(desc, {})
                    import_signing_descriptor(
                        cli, wallet, desc, private_body, active=states[desc],
                        internal=old.get("internal", len(branches) == 2 and index == 1),
                        previous=old,
                    )
        finally:
            # Python strings cannot be zeroized; never print or persist these.
            del private_keys
    verify_signer(cli, wallet, xpub, states)
    print("Descriptor imported. Signer ready.")


def main():
    if len(sys.argv) != 4 or sys.argv[3] not in {"create", "import"}:
        raise RpcError("Run sh tails.sh create or sh tails.sh import.")
    cli, qr_bin, step = sys.argv[1:]
    if rpc(cli, "getnetworkinfo")["version"] // 10000 != 32:
        raise RpcError("Bitcoin Core 32.x is required.")
    chain = rpc(cli, "getblockchaininfo")["chain"]
    if chain not in {"main", "test", "testnet4", "signet", "regtest"}:
        raise RpcError("Unsupported Bitcoin network.")
    print(f"Network: {chain}\n")
    if step == "create":
        create_signer(cli, qr_bin, int(chain != "main"))
    else:
        wallet = select_wallet(cli)
        show_wallet_public_keys(cli, wallet)
        while True:
            try:
                import_public_descriptor(cli, wallet, input("Public descriptor: ").strip())
                break
            except RpcError as error:
                print(f"Descriptor rejected: {error}\nTry again, or press Ctrl-C to import later.")


if __name__ == "__main__":
    try:
        main()
    except (RpcError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Keep the wallet and rerun the step when ready.", file=sys.stderr)
        sys.exit(1)
