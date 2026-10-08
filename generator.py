#!/usr/bin/env python3
import json
import re
import subprocess
import sys

TEST_CHAINS = {"test", "testnet4", "signet", "regtest"}
ACCOUNT = 0
HARDENED = r"(?:h|H|')"

BIP87_ORIGIN_RE = re.compile(
    rf"^\[([0-9a-fA-F]{{8}})/87{HARDENED}/([01]){HARDENED}/0{HARDENED}\]$"
)
BIP48_ORIGIN_RE = re.compile(
    rf"^\[([0-9a-fA-F]{{8}})/48{HARDENED}/([01]){HARDENED}/0{HARDENED}/2{HARDENED}\]$"
)


class RpcError(Exception):
    pass


class DescriptorError(Exception):
    pass


def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def rpc(bitcoin_cli, method, *args, wallet=None, sensitive=False):
    cmd = [bitcoin_cli]
    if wallet is not None:
        cmd.append(f"-rpcwallet={wallet}")
    cmd.extend(["-stdin", method])
    stdin = "".join(f"{arg}\n" for arg in args)

    try:
        result = subprocess.run(
            cmd,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        raise RpcError("bitcoin-cli was not found.")

    if result.returncode != 0:
        if sensitive:
            raise RpcError(
                f"{method} failed. Sensitive descriptor material was not printed."
            )
        message = result.stderr.strip() or result.stdout.strip() or f"{method} failed."
        raise RpcError(message)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        if sensitive:
            raise RpcError(
                f"{method} returned an unexpected response. Sensitive material was not printed."
            )
        raise RpcError(f"Unexpected non-JSON response from {method}.")


def core_info(bitcoin_cli):
    network = rpc(bitcoin_cli, "getnetworkinfo")
    version = network.get("version")
    if not isinstance(version, int) or version // 10000 != 32:
        fail(
            "This utility requires Bitcoin Core 32.x. "
            f"Detected: {network.get('subversion', version)}"
        )

    chain = rpc(bitcoin_cli, "getblockchaininfo").get("chain")
    if chain == "main":
        return network.get("subversion", str(version)), chain, 0
    if chain in TEST_CHAINS:
        return network.get("subversion", str(version)), chain, 1
    fail(f"Unsupported Bitcoin network: {chain}")


def get_account_type():
    print("Choose the Core signer account to export:")
    print("  1. BIP87 multisig account      m/87h/coin_typeh/0h")
    print("  2. BIP48 native-P2WSH account m/48h/coin_typeh/0h/2h")
    print()
    choice = input("Signer account type [1]: ").strip() or "1"
    if choice == "1":
        return "bip87"
    if choice == "2":
        return "bip48"
    fail("Choose 1 for BIP87 or 2 for BIP48 native-P2WSH.")


def get_wallet_name():
    name = input("Signer wallet name [core-descriptor-signer]: ").strip()
    name = name or "core-descriptor-signer"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name) or name in {".", ".."}:
        fail("Use a simple wallet name containing only letters, numbers, '.', '_', or '-'.")
    return name


def create_blank_wallet(bitcoin_cli, wallet):
    created = rpc(bitcoin_cli, "createwallet", wallet, "false", "true")
    if not isinstance(created, dict) or created.get("name") != wallet:
        fail("Unexpected response from createwallet.")

    info = rpc(bitcoin_cli, "getwalletinfo", wallet=wallet)
    if not (
        info.get("descriptors")
        and info.get("private_keys_enabled")
        and info.get("blank")
    ):
        fail("Bitcoin Core did not create the expected blank private-key descriptor wallet.")


def add_root_and_derive_public(bitcoin_cli, wallet, coin_type, account_type):
    added = rpc(bitcoin_cli, "addhdkey", wallet=wallet)
    root_xpub = added.get("xpub") if isinstance(added, dict) else None
    if not isinstance(root_xpub, str) or not root_xpub:
        fail("Unexpected response from addhdkey.")

    if account_type == "bip87":
        path = f"m/87h/{coin_type}h/{ACCOUNT}h"
        origin_re = BIP87_ORIGIN_RE
        label = "BIP87"
    elif account_type == "bip48":
        path = f"m/48h/{coin_type}h/{ACCOUNT}h/2h"
        origin_re = BIP48_ORIGIN_RE
        label = "BIP48 native-P2WSH"
    else:
        fail("Internal error: unsupported account type.")

    options = json.dumps(
        {"hdkey": root_xpub, "private": False},
        separators=(",", ":"),
    )
    derived = rpc(bitcoin_cli, "derivehdkey", path, options, wallet=wallet)

    if not isinstance(derived, dict) or "xprv" in derived:
        fail("Unexpected response from derivehdkey.")

    origin = derived.get("origin")
    account_xpub = derived.get("xpub")
    if not isinstance(origin, str) or not isinstance(account_xpub, str):
        fail("derivehdkey did not return the expected public key data.")

    match = origin_re.fullmatch(origin)
    if not match or int(match.group(2)) != coin_type:
        fail(f"Bitcoin Core returned an unexpected {label} key origin.")

    expected_prefix = "xpub" if coin_type == 0 else "tpub"
    if not account_xpub.startswith(expected_prefix):
        fail("Bitcoin Core returned an extended public key for the wrong network.")

    return root_xpub, path, origin, account_xpub, label


def show_qr(qr_bin, text):
    print()
    print("QR code:")
    result = subprocess.run([qr_bin, "--ascii", text], check=False)
    if result.returncode != 0:
        fail("The qr command failed.")


def descriptor_body(raw):
    if raw.count("#") > 1:
        raise DescriptorError("Descriptor contains more than one checksum separator.")
    return raw.split("#", 1)[0]


def local_key_pattern(origin, account_xpub):
    # getdescriptorinfo canonicalizes descriptor syntax. Match only this signer's
    # exact origin+xpub identity and require a descriptor-key boundary after it.
    if origin is None:
        # Core already parsed these key expressions. Preserve whichever valid
        # origin the coordinator supplied, and bind ownership to the exact xpub.
        return re.compile(r"(?<=[(,])(?:\[[^\[\]]*\])?" + re.escape(account_xpub) + r"(?=[/,)}])")
    identity = re.escape(origin + account_xpub)
    return re.compile(identity + r"(?=[/,)}])")


def validate_public_descriptor(bitcoin_cli, raw, origin, account_xpub):
    # Even a rejected paste may contain private keys; never echo Core's error.
    info = rpc(bitcoin_cli, "getdescriptorinfo", raw, sensitive=True)
    if not isinstance(info, dict):
        fail("Unexpected response from getdescriptorinfo.")

    if info.get("hasprivatekeys"):
        raise DescriptorError(
            "Paste a public descriptor only; private keys are not accepted."
        )

    canonical = info.get("multipath_expansion", [info.get("descriptor")])
    if not isinstance(canonical, list) or not canonical or not all(
        isinstance(desc, str) and desc for desc in canonical
    ):
        fail("Bitcoin Core did not return a canonical public descriptor.")

    pattern = local_key_pattern(origin, account_xpub)
    bodies = [descriptor_body(desc) for desc in canonical]
    occurrences = [len(list(pattern.finditer(body))) for body in bodies]

    if not all(occurrences):
        raise DescriptorError(
            "The descriptor does not contain this Core signer's exact account key."
        )

    # If the xpub appears anywhere else, do not guess whether it is the same signer
    # under a different or malformed origin.
    if any(body.count(account_xpub) != count for body, count in zip(bodies, occurrences)):
        raise DescriptorError(
            "This signer's account xpub appears with an unexpected or ambiguous origin."
        )

    return canonical, bodies, pattern, occurrences


def derive_private_account(
    bitcoin_cli, wallet, root_xpub, path, origin, account_xpub
):
    options = json.dumps(
        {"hdkey": root_xpub, "private": True},
        separators=(",", ":"),
    )
    derived = rpc(
        bitcoin_cli,
        "derivehdkey",
        path,
        options,
        wallet=wallet,
        sensitive=True,
    )
    if not isinstance(derived, dict):
        fail("Unexpected response from private derivehdkey.")

    if derived.get("origin") != origin or derived.get("xpub") != account_xpub:
        fail("Private derivation did not match the previously exported signer key.")

    xprv = derived.get("xprv")
    if not isinstance(xprv, str) or not xprv:
        fail("Bitcoin Core did not return the expected private account key.")
    return xprv


def import_signing_descriptor(
    bitcoin_cli,
    wallet,
    public_descriptor,
    public_body,
    pattern,
    expected_occurrences,
    account_xpub,
    xprv,
    internal=False,
):
    def replace_key(match):
        return match.group(0).replace(account_xpub, xprv, 1)

    private_body, replaced = pattern.subn(replace_key, public_body)
    if replaced != expected_occurrences or replaced < 1:
        fail("Internal error while substituting the local signing key.")

    if account_xpub in private_body:
        fail("Unexpected local account xpub remained after private substitution.")

    private_info = rpc(
        bitcoin_cli,
        "getdescriptorinfo",
        private_body,
        sensitive=True,
    )
    if not isinstance(private_info, dict) or not private_info.get("hasprivatekeys"):
        fail("Bitcoin Core did not recognize the private signing descriptor.")

    if private_info.get("descriptor") != public_descriptor:
        fail("Private-key substitution changed the public descriptor.")
    if private_info.get("multipath_expansion"):
        fail("Private-key substitution introduced a multipath expansion.")

    checksum = private_info.get("checksum")
    if not isinstance(checksum, str) or not checksum:
        fail("Bitcoin Core did not return a descriptor checksum.")

    private_descriptor = f"{private_body}#{checksum}"

    # Signing does not require address generation. Some valid descriptors cannot
    # be active (e.g. combo), so do not impose that restriction on the policy.
    request = json.dumps(
        [{"desc": private_descriptor, "active": False, "internal": internal, "timestamp": "now"}],
        separators=(",", ":"),
    )
    result = rpc(
        bitcoin_cli,
        "importdescriptors",
        request,
        wallet=wallet,
        sensitive=True,
    )

    if (
        not isinstance(result, list)
        or len(result) != 1
        or not isinstance(result[0], dict)
    ):
        fail("Unexpected response from importdescriptors.")
    if not result[0].get("success"):
        code = result[0].get("error", {}).get("code")
        suffix = f" (code {code})" if code is not None else ""
        fail(
            f"importdescriptors failed{suffix}. "
            "Sensitive descriptor material was not printed."
        )


def verify_signer(bitcoin_cli, wallet, account_xpub, public_descriptors, active_states=None):
    options = json.dumps({"active_only": False}, separators=(",", ":"))
    keys = rpc(bitcoin_cli, "gethdkeys", options, wallet=wallet)
    if not isinstance(keys, list):
        fail("Unexpected response from gethdkeys.")

    own = [item for item in keys if item.get("xpub") == account_xpub]
    if len(own) != 1 or own[0].get("has_private") is not True:
        fail("Bitcoin Core does not report this account xpub as signable.")

    descriptors = own[0].get("descriptors")
    if not isinstance(descriptors, list):
        fail("Bitcoin Core did not report descriptors for the local account key.")

    for public_descriptor in public_descriptors:
        matching = [
            item for item in descriptors
            if isinstance(item, dict) and item.get("desc") == public_descriptor
        ]
        expected_active = active_states.get(public_descriptor, False) if active_states else False
        if len(matching) != 1 or matching[0].get("active") is not expected_active:
            fail("Bitcoin Core did not report the expected signing descriptor and active state.")


def create_signer(bitcoin_cli, qr_bin, coin_type):
    account_type = get_account_type()
    wallet = get_wallet_name()
    create_blank_wallet(bitcoin_cli, wallet)
    root, path, origin, xpub, label = add_root_and_derive_public(
        bitcoin_cli, wallet, coin_type, account_type
    )
    # Store the account in Core itself, ready for a later, independent import.
    public = rpc(bitcoin_cli, "getdescriptorinfo", f"unused({origin}{xpub})")["descriptor"]
    private = derive_private_account(bitcoin_cli, wallet, root, path, origin, xpub)
    try:
        import_signing_descriptor(
            bitcoin_cli, wallet, public, descriptor_body(public),
            local_key_pattern(origin, xpub), 1, xpub, private,
        )
    finally:
        del private
    verify_signer(bitcoin_cli, wallet, xpub, [public])
    print(f"\nWallet created: {wallet}")
    print(f"{label} signer key:")
    print(origin + xpub)
    show_qr(qr_bin, origin + xpub)
    print("Step 1 complete. Back up this wallet before closing or shutting down.")
    print("Later, run sh tails.sh import and select this wallet to import your public descriptor.")


def select_wallet(bitcoin_cli):
    wallets = rpc(bitcoin_cli, "listwalletdir")["wallets"]
    if not wallets:
        fail("No wallets found. Run sh tails.sh create first or restore a wallet into the wallet directory.")
    for index, item in enumerate(wallets, 1):
        print(f"  {index}. {item['name']}")
    choice = input("Select wallet number: ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(wallets):
        fail("Select a wallet number from the list.")
    wallet = wallets[int(choice) - 1]["name"]
    if wallet not in rpc(bitcoin_cli, "listwallets"):
        rpc(bitcoin_cli, "loadwallet", wallet)
    info = rpc(bitcoin_cli, "getwalletinfo", wallet=wallet)
    if not info.get("descriptors") or not info.get("private_keys_enabled"):
        fail("Select a private-key descriptor wallet.")
    return wallet


def import_public_descriptor(bitcoin_cli, wallet, raw):
    info = rpc(bitcoin_cli, "getdescriptorinfo", raw, sensitive=True)
    if info.get("hasprivatekeys"):
        raise DescriptorError("Paste a public descriptor only; private keys are not accepted.")
    branches = info.get("multipath_expansion", [info.get("descriptor")])
    keys = rpc(bitcoin_cli, "gethdkeys", wallet=wallet)
    owned = [key["xpub"] for key in keys if key.get("has_private") is True and all(
        isinstance(desc, str) and local_key_pattern(None, key["xpub"]).search(descriptor_body(desc))
        for desc in branches
    )]
    if not owned:
        raise DescriptorError("The selected wallet does not own a descriptor extended key in every branch.")
    xpub = owned[0]
    descs, bodies, pattern, counts = validate_public_descriptor(bitcoin_cli, raw, None, xpub)
    print(f"Wallet {wallet} owns a matching descriptor key. Importing the public policy.")
    existing = {item["desc"]: item["active"] for item in rpc(
        bitcoin_cli, "listdescriptors", wallet=wallet
    )["descriptors"]}
    active_states = {desc: existing.get(desc, False) for desc in descs}
    if any(desc not in existing for desc in descs):
        # Core exports wallet-owned keys; no seed/session file or policy parser.
        private_keys = rpc(bitcoin_cli, "gethdkeys", '{"private":true}', wallet=wallet, sensitive=True)
        matches = []
        try:
            matches = [key for key in private_keys if key.get("xpub") == xpub and key.get("has_private") is True]
            if len(matches) != 1 or not isinstance(matches[0].get("xprv"), str):
                fail("Core did not return the selected wallet's matching private key.")
            for index, (desc, body, count) in enumerate(zip(descs, bodies, counts)):
                if desc not in existing:
                    import_signing_descriptor(
                        bitcoin_cli, wallet, desc, body, pattern, count, xpub, matches[0]["xprv"],
                        internal=len(descs) == 2 and index == 1,
                    )
        finally:
            # Python strings cannot be reliably zeroized; do not persist/print them.
            del private_keys, matches
    verify_signer(bitcoin_cli, wallet, xpub, descs, active_states)
    print("Signer ready. Core reports the imported policy and its wallet-owned private key.")


def main():
    if len(sys.argv) != 4 or sys.argv[3] not in {"create", "import"}:
        fail("Run sh tails.sh create or sh tails.sh import.")
    bitcoin_cli, qr_bin, step = sys.argv[1:]
    version, chain, coin_type = core_info(bitcoin_cli)
    print(f"Bitcoin Core: {version}\nNetwork: {chain}\n")
    if step == "create":
        create_signer(bitcoin_cli, qr_bin, coin_type)
        return
    wallet = select_wallet(bitcoin_cli)
    while True:
        raw = input("Public descriptor: ").strip()
        if not raw:
            print("Descriptor cannot be blank.")
            continue
        try:
            import_public_descriptor(bitcoin_cli, wallet, raw)
            break
        except (DescriptorError, RpcError) as exc:
            print(f"Descriptor rejected: {exc}")
            print("Try again, or press Ctrl-C and run sh tails.sh import later.")


if __name__ == "__main__":
    try:
        main()
    except RpcError as exc:
        fail(str(exc))
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Keep the wallet output; rerun the appropriate step when ready.", file=sys.stderr)
        raise SystemExit(1)
