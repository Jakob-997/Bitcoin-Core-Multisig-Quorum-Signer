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
    print("Choose the Core signer account type to give Liana:")
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
    name = input("Signer wallet name [core-liana-signer]: ").strip()
    name = name or "core-liana-signer"
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
        fail("Internal error: unsupported signer account type.")

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
    return re.compile(
        rf"{re.escape(origin)}{re.escape(account_xpub)}(?=/)"
    )

def validate_public_descriptor(bitcoin_cli, raw, coin_type, origin, account_xpub):
    info = rpc(bitcoin_cli, "getdescriptorinfo", raw)
    if not isinstance(info, dict):
        fail("Unexpected response from getdescriptorinfo.")
    if info.get("hasprivatekeys"):
        raise DescriptorError(
            "Paste a public Liana descriptor only; private keys are not accepted."
        )
    if not info.get("isrange") or not info.get("issolvable"):
        raise DescriptorError("Descriptor must be ranged and solvable.")

    canonical = info.get("descriptor")
    if not isinstance(canonical, str) or not canonical:
        fail("Bitcoin Core did not return a canonical public descriptor.")

    body = descriptor_body(canonical)
    if not body.startswith("wsh("):
        raise DescriptorError(
            "This Liana signer currently supports P2WSH Miniscript descriptors "
            "only. Taproot tr(...) descriptors are intentionally not supported yet."
        )
    if "older(" not in body:
        raise DescriptorError(
            "Descriptor does not contain an older() recovery timelock."
        )

    pattern = local_key_pattern(origin, account_xpub)
    matches = list(pattern.finditer(body))
    if not matches:
        raise DescriptorError(
            "The descriptor does not contain this Core signer's selected account key."
        )

    # If the same account xpub appears anywhere outside the exact expected origin,
    # fail rather than guessing which occurrence belongs to this signer.
    if body.count(account_xpub) != len(matches):
        raise DescriptorError(
            "This signer's account xpub appears with an unexpected or ambiguous origin."
        )

    return info, body, pattern, len(matches)


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
    public_info,
    public_body,
    pattern,
    expected_occurrences,
    account_xpub,
    xprv,
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
        fail("Bitcoin Core did not recognize the private Liana signing descriptor.")

    if private_info.get("descriptor") != public_info.get("descriptor"):
        fail("Private-key substitution changed the public descriptor.")
    if (
        private_info.get("multipath_expansion")
        != public_info.get("multipath_expansion")
    ):
        fail("Private-key substitution changed the multipath descriptor expansion.")

    checksum = private_info.get("checksum")
    if not isinstance(checksum, str) or not checksum:
        fail("Bitcoin Core did not return a descriptor checksum.")

    private_descriptor = f"{private_body}#{checksum}"
    request = json.dumps(
        [{"desc": private_descriptor, "active": True, "timestamp": "now"}],
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


def verify_signer(bitcoin_cli, wallet, account_xpub):
    options = json.dumps({"active_only": True}, separators=(",", ":"))
    keys = rpc(bitcoin_cli, "gethdkeys", options, wallet=wallet)
    if not isinstance(keys, list):
        fail("Unexpected response from gethdkeys.")

    own = [item for item in keys if item.get("xpub") == account_xpub]
    if len(own) != 1 or own[0].get("has_private") is not True:
        fail("Bitcoin Core does not report this account xpub as signable.")

    descriptors = own[0].get("descriptors")
    if not isinstance(descriptors, list) or not any(
        isinstance(item, dict) and item.get("active") is True
        for item in descriptors
    ):
        fail("The Liana signing descriptor is not active.")


def main():
    if len(sys.argv) != 3:
        fail("Run this utility through tails.sh.")

    bitcoin_cli = sys.argv[1]
    qr_bin = sys.argv[2]

    print("Bitcoin Core - Liana Timelock Signer")
    print()

    version, chain, coin_type = core_info(bitcoin_cli)
    print(f"Bitcoin Core: {version}")
    print(f"Network: {chain}")
    print()

    account_type = get_account_type()
    wallet = get_wallet_name()
    create_blank_wallet(bitcoin_cli, wallet)
    root_xpub, path, origin, account_xpub, account_label = add_root_and_derive_public(
        bitcoin_cli, wallet, coin_type, account_type
    )
    key_expression = origin + account_xpub

    print()
    print(f"{account_label} signer key:")
    print(key_expression)
    print()
    print("This is public information. Add it to the Liana wallet policy.")
    print("Liana may reuse this xpub in multiple spending paths with different suffixes.")
    print("Verify that the scanned QR text exactly matches the text above.")
    show_qr(qr_bin, key_expression)

    print()
    print("Build/export the complete PUBLIC Liana P2WSH descriptor in Liana.")
    print("Paste it here when ready. A checksum is optional.")
    print()
    print(
        "This tool does not interpret the Liana policy itself. "
        "Bitcoin Core parses the Miniscript descriptor, and you must independently "
        "verify the policy, timelocks, keys, and addresses in Liana."
    )
    print()

    while True:
        raw = input("Public Liana descriptor: ").strip()
        if not raw:
            print("Descriptor cannot be blank.")
            continue
        try:
            public_info, public_body, pattern, occurrences = (
                validate_public_descriptor(
                    bitcoin_cli, raw, coin_type, origin, account_xpub
                )
            )
            break
        except (DescriptorError, RpcError) as exc:
            print(f"Descriptor rejected: {exc}")
            print(
                "Try again, or press Ctrl-C to stop without importing a descriptor."
            )
            print()

    xprv = derive_private_account(
        bitcoin_cli, wallet, root_xpub, path, origin, account_xpub
    )
    try:
        import_signing_descriptor(
            bitcoin_cli,
            wallet,
            public_info,
            public_body,
            pattern,
            occurrences,
            account_xpub,
            xprv,
        )
    finally:
        # Python strings cannot be reliably zeroized. Keep the private value's
        # lifetime as short as practical and never print, persist, or pass it in argv.
        del xprv

    verify_signer(bitcoin_cli, wallet, account_xpub)

    print()
    print("Liana signer ready.")
    print(f"Wallet: {wallet}")
    print(f"Signer path: {path}")
    print(
        "Bitcoin Core reports the local account key as private and active "
        "in the imported Liana descriptor."
    )
    print(
        "Back up the wallet before funding the Liana policy, "
        "then test with disposable funds."
    )


if __name__ == "__main__":
    try:
        main()
    except RpcError as exc:
        fail(str(exc))
