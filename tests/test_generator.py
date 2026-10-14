import contextlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generator as g


class WorkflowTests(unittest.TestCase):
    key = "[12345678/87h/1h/0h]tpubLOCAL"
    xpub = "tpubLOCAL"
    secret = "tprvSECRET"

    def setUp(self):
        self.stored = {}
        self.calls = []
        self.owns_key = True
        self.policy = f"wpkh({self.key}/<0;1>/*)"
        self.branches = [f"wpkh({self.key}/{i}/*)#sum" for i in range(2)]
        self.interrupt = False
        self.patch = patch.object(g, "rpc", side_effect=self.rpc)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def rpc(self, cli, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        if method == "createwallet":
            self.assertEqual(args, ("signer", "false", "true"))
            return {"name": "signer"}
        if method == "addhdkey":
            return {"xpub": "tpubROOT"}
        if method == "derivehdkey":
            return {"origin": self.key.split("]")[0] + "]",
                    "xpub": self.xpub, "xprv": self.secret}
        if method == "getdescriptorinfo":
            body = args[0].split("#")[0]
            private = self.secret in body or "xprv" in body
            public_body = body.replace(self.secret, self.xpub)
            info = {"descriptor": public_body + "#sum", "checksum": "sum",
                    "hasprivatekeys": private, "isrange": "*" in body}
            if body == self.policy:
                info["multipath_expansion"] = self.branches
            return info
        if method == "importdescriptors":
            entry = json.loads(args[0])[0]
            entry["desc"] = entry["desc"].replace(self.secret, self.xpub)
            self.stored[entry["desc"]] = entry
            if self.interrupt:
                self.interrupt = False
                raise KeyboardInterrupt
            return [{"success": True}]
        if method == "listdescriptors":
            return {"descriptors": list(self.stored.values())}
        if method == "gethdkeys":
            key = {"xpub": self.xpub, "has_private": self.owns_key,
                   "descriptors": list(self.stored.values())}
            if args and json.loads(args[0]).get("private"):
                key["xprv"] = self.secret
            return [key]
        if method == "listwalletdir":
            return {"wallets": [{"name": "signer"}]}
        if method == "listwallets":
            return []
        if method == "loadwallet":
            return {"name": args[0]}
        if method == "getwalletinfo":
            return {"descriptors": True, "private_keys_enabled": True}
        if method == "getnetworkinfo":
            return {"version": 320000}
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        raise AssertionError(method)

    def test_create_then_later_load_and_import(self):
        output = io.StringIO()
        with patch("builtins.input", side_effect=["signer", "1"]) as prompts, \
                patch.object(g.subprocess, "run") as qr, contextlib.redirect_stdout(output):
            g.create_signer("cli", "qr", 1)
        self.assertEqual(prompts.call_count, 2)
        self.assertEqual(list(self.stored), [f"unused({self.key})#sum"])
        self.assertIn(self.key, output.getvalue())
        self.assertNotIn(self.secret, output.getvalue())
        self.assertEqual(qr.call_args.args[0], ["qr", "--ascii", self.key])
        with patch("builtins.input", return_value="1"), contextlib.redirect_stdout(output):
            wallet = g.select_wallet("cli")
            g.show_wallet_public_keys("cli", wallet)
            g.import_public_descriptor("cli", wallet, self.policy)
        self.assertTrue(any(method == "loadwallet" for method, _, _ in self.calls))
        self.assertEqual([self.stored[d]["internal"] for d in self.branches], [False, True])
        self.assertTrue(all(self.stored[d]["active"] for d in self.branches))
        self.assertEqual(sum(method == "createwallet" for method, _, _ in self.calls), 1)

    def test_private_or_unowned_policy_never_exports_secrets(self):
        for raw, owns in [(self.policy.replace(self.xpub, self.secret), True),
                          (self.policy, False), ("wpkh(tpubOTHER/0/*)", True),
                          (f"wpkh({self.key}EXTRA/0/*)", True)]:
            with self.subTest(raw=raw):
                self.calls.clear()
                self.owns_key = owns
                with self.assertRaises(g.RpcError):
                    g.import_public_descriptor("cli", "wrong", raw)
                self.assertFalse(any(method == "importdescriptors" or
                    (method == "gethdkeys" and args) for method, args, _ in self.calls))

    def test_every_branch_requires_ownership(self):
        self.branches[1] = "wpkh(tpubOTHER/1/*)#sum"
        with self.assertRaises(g.RpcError):
            g.import_public_descriptor("cli", "wallet", self.policy)
        self.assertFalse(self.stored)

    def test_interrupted_import_resumes_and_repeat_preserves_cursor(self):
        self.interrupt = True
        with self.assertRaises(KeyboardInterrupt):
            g.import_public_descriptor("cli", "wallet", self.policy)
        first = self.stored[self.branches[0]]
        first.update(range=[0, 20], next_index=7, timestamp=123)
        with contextlib.redirect_stdout(io.StringIO()):
            g.import_public_descriptor("cli", "wallet", self.policy)
        self.assertIs(self.stored[self.branches[0]], first)
        before = dict(self.stored)
        self.calls.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            g.import_public_descriptor("cli", "wallet", self.policy)
        self.assertEqual(self.stored, before)
        self.assertFalse(any(method == "importdescriptors" for method, _, _ in self.calls))

    def test_repair_inactive_policy_preserves_metadata(self):
        for index, desc in enumerate(self.branches):
            self.stored[desc] = dict(desc=desc, active=False, internal=index == 1,
                                     timestamp=123, range=[0, 20], next_index=7)
        with contextlib.redirect_stdout(io.StringIO()):
            g.import_public_descriptor("cli", "wallet", self.policy)
        for desc in self.branches:
            self.assertTrue(self.stored[desc]["active"])
            self.assertEqual(self.stored[desc]["next_index"], 7)
            self.assertEqual(self.stored[desc]["range"], [0, 20])
            self.assertEqual(self.stored[desc]["timestamp"], 123)

    def test_substitution_mismatch_and_failed_import(self):
        for info in [{"descriptor": "changed", "hasprivatekeys": True},
                     {"descriptor": "public", "hasprivatekeys": False}]:
            with patch.object(g, "rpc", return_value=info) as rpc:
                with self.assertRaises(g.RpcError):
                    g.import_signing_descriptor("cli", "wallet", "public", self.secret)
                self.assertEqual(rpc.call_count, 1)
        with patch.object(g, "rpc", side_effect=[
                {"descriptor": "public", "hasprivatekeys": True, "checksum": "sum"},
                [{"success": False, "error": {"message": self.secret}}]]):
            with self.assertRaises(g.RpcError) as error:
                g.import_signing_descriptor("cli", "wallet", "public", self.secret)
            self.assertNotIn(self.secret, str(error.exception))

    def test_supported_address_policy_activation(self):
        for raw, expected in [(f"combo({self.key}/0/*)", False),
                              (f"pk({self.key}/0/*)", False),
                              (f"pkh({self.key}/0/0)", False),
                              (f"wsh(sortedmulti(1,{self.key}/0/*))", True)]:
            self.stored.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                g.import_public_descriptor("cli", "wallet", raw)
            self.assertEqual(next(iter(self.stored.values()))["active"], expected)

    def test_verification_rejects_missing_or_watch_only_key(self):
        with self.assertRaises(g.RpcError):
            g.verify_signer("cli", "wallet", self.xpub, {"missing": False})
        self.owns_key = False
        with self.assertRaises(g.RpcError):
            g.verify_signer("cli", "wallet", self.xpub, {})

    def test_import_entry_point_never_creates_wallet(self):
        desc = f"unused({self.key})#sum"
        self.stored[desc] = {"desc": desc, "active": False}
        with patch.object(sys, "argv", ["generator.py", "cli", "qr", "import"]), \
                patch("builtins.input", side_effect=["1", self.policy]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            g.main()
        self.assertIn(self.key, output.getvalue())
        self.assertFalse(any(method in {"createwallet", "addhdkey", "derivehdkey"}
                             for method, _, _ in self.calls))

    def test_account_paths_and_invalid_names(self):
        for coin, choice, expected in [(0, "1", "m/87h/0h/0h"),
                                       (1, "2", "m/48h/1h/0h/2h")]:
            self.calls.clear()
            with patch("builtins.input", side_effect=["signer", choice]), \
                    patch.object(g.subprocess, "run"), contextlib.redirect_stdout(io.StringIO()):
                g.create_signer("cli", "qr", coin)
            path = next(args[0] for method, args, _ in self.calls if method == "derivehdkey")
            self.assertEqual(path, expected)
        self.calls.clear()
        with patch("builtins.input", return_value="../wallet"), self.assertRaises(g.RpcError):
            g.create_signer("cli", "qr", 1)
        self.assertFalse(self.calls)


class RpcTests(unittest.TestCase):
    def test_secret_stdin_and_redacted_errors(self):
        for code, stdout, stderr in [(1, "SECRET", "SECRET"), (0, "SECRET", "")]:
            result = type("Result", (), dict(returncode=code, stdout=stdout, stderr=stderr))
            with patch.object(g.subprocess, "run", return_value=result) as run:
                with self.assertRaises(g.RpcError) as error:
                    g.rpc("cli", "getdescriptorinfo", "SECRET", wallet="wallet", sensitive=True)
                self.assertNotIn("SECRET", str(error.exception))
                self.assertNotIn("SECRET", run.call_args.args[0])
                self.assertEqual(run.call_args.kwargs["input"], "SECRET\n")


@unittest.skipUnless(os.environ.get("CORE_TEST_CLI"), "Set CORE_TEST_CLI to an isolated regtest CLI")
class CoreIntegrationTests(unittest.TestCase):
    def test_create_reload_import_and_addresses(self):
        import uuid
        cli = os.environ["CORE_TEST_CLI"]
        self.assertEqual(g.rpc(cli, "getblockchaininfo")["chain"], "regtest")
        for choice in ["1", "2"]:
            wallet = "simplified-" + uuid.uuid4().hex
            with patch("builtins.input", side_effect=[wallet, choice]), \
                    patch.object(g.subprocess, "run", wraps=g.subprocess.run) as run, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                # Only replace QR output; the RPC subprocesses still use real Core.
                original = run._mock_wraps
                run.side_effect = lambda command, **kw: (
                    None if command[0] == "test-qr" else original(command, **kw))
                g.create_signer(cli, "test-qr", 1)
            public = next(line for line in output.getvalue().splitlines() if line.startswith("["))
            g.rpc(cli, "unloadwallet", wallet)
            g.rpc(cli, "loadwallet", wallet)
            raw = f"wpkh({public}/<0;1>/*)"
            g.import_public_descriptor(cli, wallet, raw)
            branches = g.rpc(cli, "getdescriptorinfo", raw)["multipath_expansion"]
            self.assertEqual([g.rpc(cli, "getnewaddress", "", "bech32", wallet=wallet)],
                             g.rpc(cli, "deriveaddresses", branches[0], "[0,0]"))
            self.assertEqual([g.rpc(cli, "getrawchangeaddress", "bech32", wallet=wallet)],
                             g.rpc(cli, "deriveaddresses", branches[1], "[0,0]"))
            before = g.rpc(cli, "listdescriptors", wallet=wallet)
            g.import_public_descriptor(cli, wallet, raw)
            self.assertEqual(g.rpc(cli, "listdescriptors", wallet=wallet), before)


if __name__ == "__main__":
    unittest.main()
