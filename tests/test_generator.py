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


class BoundaryTests(unittest.TestCase):
    origin = "[12345678/87h/1h/0h]"
    xpub = "tpubLOCAL"

    def validate(self, info):
        with patch.object(g, "rpc", return_value=info):
            return g.validate_public_descriptor("cli", "input", self.origin, self.xpub)

    def test_import_redisplays_selected_account_before_descriptor_prompt(self):
        public = self.origin + self.xpub
        keys = [
            {"xpub": "tpubROOT", "has_private": True, "descriptors": [{"desc": "unused(tpubROOT)#sum"}]},
            {"xpub": self.xpub, "has_private": True, "xprv": "SECRET", "descriptors": [
                {"desc": f"unused({public})#sum"}, {"desc": f"wpkh({public}/0/*)#sum"}]},
            {"xpub": "tpubOTHER", "has_private": False, "descriptors": [{"desc": "unused(tpubOTHER)#sum"}]},
        ]
        output = io.StringIO()
        def input_descriptor(prompt):
            self.assertEqual(prompt, "Public descriptor: ")
            self.assertIn(public, output.getvalue())
            self.assertNotIn("tpubROOT", output.getvalue())
            self.assertNotIn("tpubOTHER", output.getvalue())
            self.assertNotIn("SECRET", output.getvalue())
            self.assertEqual(output.getvalue().count(public), 1)
            return f"wpkh({public}/0/*)"
        with patch.object(sys, "argv", ["generator.py", "cli", "qr", "import"]), \
                patch.object(g, "core_info", return_value=("32", "regtest", 1)), \
                patch.object(g, "select_wallet", return_value="selected-wallet"), \
                patch.object(g, "rpc", return_value=keys) as rpc, \
                patch.object(g, "import_public_descriptor"), \
                patch("builtins.input", side_effect=input_descriptor), contextlib.redirect_stdout(output):
            g.main()
        rpc.assert_called_once_with("cli", "gethdkeys", wallet="selected-wallet")

    def test_address_activation_and_existing_wallet_repair(self):
        for policy, ranged, count, expected in [
            ("wsh(sortedmulti(2,{key}/0/*,tpubOTHER/0/*))", True, 2, True),
            ("combo({key}/0/*)", True, 1, False),
            ("pkh({key}/0/0)", False, 1, False),
            ("pk({key}/0/*)", True, 1, False),
            ("wpkh({key}/0/*)", True, 3, False),
        ]:
            key = self.origin + self.xpub
            descs = [policy.format(key=key).replace("/0/", f"/{i}/") + "#sum" for i in range(count)]
            info = {"descriptor": descs[0], "isrange": ranged, "multipath_expansion": descs}
            for repairing in [False, True]:
                with self.subTest(policy=policy, repairing=repairing):
                    old = [{"desc": d, "active": False, "internal": i == 1,
                            "timestamp": 123, "range": [0, 20], "next_index": 7}
                           for i, d in enumerate(descs)] if repairing else []
                    def rpc(cli, method, *args, **kwargs):
                        if method == "getdescriptorinfo": return info
                        if method == "listdescriptors": return {"descriptors": old}
                        if method == "gethdkeys":
                            return [{"xpub": self.xpub, "has_private": True, "xprv": "secret"}]
                        raise AssertionError(method)
                    with patch.object(g, "rpc", side_effect=rpc), \
                            patch.object(g, "import_signing_descriptor") as imported, \
                            patch.object(g, "verify_signer") as verified, \
                            contextlib.redirect_stdout(io.StringIO()):
                        g.import_public_descriptor("cli", "wallet", "public")
                    self.assertEqual(imported.call_count, count if expected or not repairing else 0)
                    for i, call in enumerate(imported.call_args_list):
                        self.assertEqual(call.kwargs["active"], expected)
                        self.assertEqual(call.kwargs["previous"], old[i] if repairing else None)
                        self.assertEqual(call.kwargs["internal"], i == 1 if repairing else count == 2 and i == 1)
                    self.assertEqual(verified.call_args.args[-1], dict.fromkeys(descs, expected))

    def test_activation_reimport_preserves_address_cursor(self):
        desc = f"wsh(sortedmulti(2,{self.origin}{self.xpub}/0/*,tpubOTHER/0/*))#sum"
        responses = [{"hasprivatekeys": True, "descriptor": desc, "checksum": "sum"}, [{"success": True}]]
        previous = {"timestamp": 123, "range": [0, 20], "next_index": 7}
        with patch.object(g, "rpc", side_effect=responses) as rpc:
            g.import_signing_descriptor("cli", "wallet", desc, g.descriptor_body(desc),
                g.local_key_pattern(self.origin, self.xpub), 1, self.xpub, "secret",
                active=True, previous=previous)
        entry = json.loads(rpc.call_args.args[2])[0]
        self.assertTrue(entry["active"])
        self.assertEqual({field: entry[field] for field in previous}, previous)

    def test_rejects_private_missing_and_ambiguous_keys(self):
        key = self.origin + self.xpub
        for info in [
            {"hasprivatekeys": True},
            {"descriptor": "wpkh(tpubOTHER/0/*)#sum"},
            {"descriptor": f"wsh(multi(1,{key}/0/*,[87654321]{self.xpub}/0/*))#sum"},
            {"descriptor": f"wpkh({key}EXTRA/0/*)#sum"},
        ]:
            with self.subTest(info=info), self.assertRaises(g.DescriptorError):
                self.validate(info)

    def test_every_multipath_branch_must_bind_local_key(self):
        with self.assertRaises(g.DescriptorError):
            self.validate({"multipath_expansion": [
                f"wpkh({self.origin}{self.xpub}/0/*)#sum",
                "wpkh(tpubOTHER/1/*)#sum",
            ]})

    def test_private_substitution_mismatch_never_imports(self):
        desc = f"wpkh({self.origin}{self.xpub}/0/*)#sum"
        for info in [
            {"hasprivatekeys": True, "descriptor": "changed", "checksum": "sum"},
            {"hasprivatekeys": True, "descriptor": desc, "multipath_expansion": [desc]},
            {"hasprivatekeys": False, "descriptor": desc},
        ]:
            with patch.object(g, "rpc", return_value=info) as rpc, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                g.import_signing_descriptor("cli", "wallet", desc, g.descriptor_body(desc),
                    g.local_key_pattern(self.origin, self.xpub), 1, self.xpub, "secret")
            self.assertEqual(rpc.call_count, 1)

    def test_rpc_secrets_stay_in_stdin_and_errors_are_redacted(self):
        for response in [
            type("Result", (), {"returncode": 1, "stdout": "secret", "stderr": "secret"}),
            type("Result", (), {"returncode": 0, "stdout": "secret", "stderr": ""}),
        ]:
            with patch.object(g.subprocess, "run", return_value=response) as run:
                with self.assertRaises(g.RpcError) as error:
                    g.rpc("cli", "getdescriptorinfo", "secret", sensitive=True)
                self.assertNotIn("secret", str(error.exception))
                self.assertNotIn("secret", run.call_args.args[0])
                self.assertEqual(run.call_args.kwargs["input"], "secret\n")

    def test_public_paste_is_treated_as_sensitive(self):
        with patch.object(g, "rpc", side_effect=g.RpcError("rejected")) as rpc:
            with self.assertRaises(g.RpcError):
                g.validate_public_descriptor("cli", "secret", self.origin, self.xpub)
            self.assertTrue(rpc.call_args.kwargs["sensitive"])

    def test_verification_requires_every_branch_and_inactive_state(self):
        for descriptors in [[{"desc": "first", "active": False}],
                            [{"desc": "first", "active": False}, {"desc": "second", "active": True}]]:
            keys = [{"xpub": self.xpub, "has_private": True, "descriptors": descriptors}]
            with patch.object(g, "rpc", return_value=keys), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                g.verify_signer("cli", "wallet", self.xpub, ["first", "second"])

    def test_unowned_or_private_descriptor_never_exports_secrets(self):
        key = self.origin + self.xpub
        for info, keys in [
            ({"descriptor": f"wpkh({key}/0/*)#sum", "hasprivatekeys": True}, []),
            ({"descriptor": f"wpkh({key}/0/*)#sum"}, [{"xpub": self.xpub, "has_private": False}]),
            ({"descriptor": f"wpkh({key}/0/*)#sum"}, [{"xpub": "tpubOTHER", "has_private": True}]),
        ]:
            def rpc(cli, method, *args, **kwargs):
                if method == "getdescriptorinfo":
                    return info
                if method == "gethdkeys" and not args:
                    return keys
                raise AssertionError("Unexpected private export or import")
            with patch.object(g, "rpc", side_effect=rpc), self.assertRaises(g.DescriptorError):
                g.import_public_descriptor("cli", "wrong-wallet", "public")

    def test_origin_is_preserved_when_binding_wallet_owned_xpub(self):
        raw = f"wsh(multi(1,[87654321/48h/1h/0h/2h]{self.xpub}/0/*,{self.xpub}/1/*))#sum"
        with patch.object(g, "rpc", return_value={"descriptor": raw}):
            descs, bodies, pattern, counts = g.validate_public_descriptor("cli", raw, None, self.xpub)
        self.assertEqual(counts, [2])
        replaced = pattern.sub(lambda match: match.group(0).replace(self.xpub, "secret"), bodies[0])
        self.assertIn("[87654321/48h/1h/0h/2h]secret", replaced)
        self.assertEqual(descs, [raw])


@unittest.skipUnless(os.environ.get("CORE_TEST_CLI"), "Set CORE_TEST_CLI to an isolated regtest CLI wrapper")
class CoreIntegrationTests(unittest.TestCase):
    def test_separate_create_import_and_partial_retry(self):
        cli = os.environ["CORE_TEST_CLI"]
        for convention, choice in [("bip87", "1"), ("bip48", "2")]:
            wallet = f"two-step-{convention}"
            with patch("builtins.input", side_effect=[choice, wallet]), contextlib.redirect_stdout(io.StringIO()) as output:
                g.create_signer(cli, "/bin/true", 1)
            keys = g.rpc(cli, "gethdkeys", wallet=wallet)
            account = [key for key in keys if any(g.descriptor_body(desc["desc"]).startswith("unused([") for desc in key["descriptors"])][0]
            public = g.descriptor_body(account["descriptors"][0]["desc"])[7:-1]
            self.assertIn(public, output.getvalue())
            self.assertTrue(account["has_private"])
            raw = f"wpkh({public}/<0;1>/*)"
            g.rpc(cli, "unloadwallet", wallet)
            available = g.rpc(cli, "listwalletdir")["wallets"]
            number = next(i for i, item in enumerate(available, 1) if item["name"] == wallet)
            with patch("builtins.input", return_value=str(number)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(g.select_wallet(cli), wallet)
            other = f"two-step-wrong-{convention}"
            g.create_blank_wallet(cli, other)
            g.rpc(cli, "addhdkey", wallet=other)
            with self.assertRaises(g.DescriptorError):
                g.import_public_descriptor(cli, other, raw)
            original = g.import_signing_descriptor
            def interrupted(*args, **kwargs):
                original(*args, **kwargs)
                raise KeyboardInterrupt
            with patch.object(g, "import_signing_descriptor", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
                g.import_public_descriptor(cli, wallet, raw)
            before = g.rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]
            imported = [desc for desc in before if not desc["desc"].startswith("unused(")]
            self.assertEqual(len(imported), 1)
            g.rpc(cli, "unloadwallet", wallet)
            g.rpc(cli, "loadwallet", wallet)
            with patch.object(g, "import_signing_descriptor", wraps=original) as imported_rpc:
                g.import_public_descriptor(cli, wallet, raw)
            self.assertEqual(imported_rpc.call_count, 1)
            with patch.object(g, "import_signing_descriptor", side_effect=AssertionError("already imported")):
                g.import_public_descriptor(cli, wallet, raw)
            after = g.rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]
            self.assertEqual(next(desc for desc in after if desc["desc"] == imported[0]["desc"]), imported[0])

    def test_descriptor_forms(self):
        cli = os.environ["CORE_TEST_CLI"]
        self.assertEqual(g.core_info(cli)[1], "regtest")
        forms = [
            "wpkh({k}/0/*)", "pkh({k}/0/0)", "pk({k}/0/*)",
            "combo({k}/0/*)", "tr({k}/0/*)",
            "wsh(sortedmulti(1,{k}/0/*,{other}/0/*))",
            "wsh(or_d(pk({k}/0/*),and_v(v:pkh({k}/1/*),older(10))))",
            "wpkh({k}/<0;1>/*)", "wpkh({k}/<0;1;2>/*)",
            "tr({k}/<0;1>/*,pk({other}/<0;1>/*))",
            "sh(wpkh({k}/0/*))",
        ]
        for convention in ["bip87", "bip48"]:
            for index, form in enumerate(forms):
                with self.subTest(convention=convention, form=form):
                    wallet = f"test-{convention}-{index}"
                    with patch("builtins.input", side_effect=["1" if convention == "bip87" else "2", wallet]), contextlib.redirect_stdout(io.StringIO()):
                        g.create_signer(cli, "/bin/true", 1)
                    account = next(key for key in g.rpc(cli, "gethdkeys", wallet=wallet) if any(
                        g.descriptor_body(desc["desc"]).startswith("unused([") for desc in key["descriptors"]))
                    public = g.descriptor_body(account["descriptors"][0]["desc"])[7:-1]
                    xpub = account["xpub"]
                    other_root = g.rpc(cli, "addhdkey", wallet=wallet)["xpub"]
                    other = g.rpc(cli, "derivehdkey", "m/87h/1h/1h",
                        json.dumps({"hdkey": other_root, "private": False}), wallet=wallet)
                    raw = form.format(k=public, other=other["origin"] + other["xpub"])
                    with contextlib.redirect_stdout(io.StringIO()):
                        g.import_public_descriptor(cli, wallet, raw)
                    info = g.rpc(cli, "getdescriptorinfo", raw)
                    descs = info.get("multipath_expansion", [info["descriptor"]])
                    states = {d["desc"]: d["active"] for d in g.rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]}
                    g.verify_signer(cli, wallet, xpub, descs, states)
                    stored = g.rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]
                    self.assertTrue(set(descs).issubset({d["desc"] for d in stored}))
                    g.rpc(cli, "unloadwallet", wallet)
                    g.rpc(cli, "loadwallet", wallet)
                    g.verify_signer(cli, wallet, xpub, descs, states)

    def test_two_of_two_receive_and_change_after_repair(self):
        cli = os.environ["CORE_TEST_CLI"]
        wallet = "two-of-two-address-repair"
        with patch("builtins.input", side_effect=["1", wallet]), contextlib.redirect_stdout(io.StringIO()):
            g.create_signer(cli, "/bin/true", 1)
        account = next(key for key in g.rpc(cli, "gethdkeys", '{"private":true}', wallet=wallet)
                       if any(d["desc"].startswith("unused([") for d in key["descriptors"]))
        public = g.descriptor_body(account["descriptors"][0]["desc"])[7:-1]
        root = g.rpc(cli, "addhdkey", wallet=wallet)["xpub"]
        other = g.rpc(cli, "derivehdkey", "m/87h/1h/1h", json.dumps({"hdkey": root}), wallet=wallet)
        raw = f"wsh(sortedmulti(2,{public}/<0;1>/*,{other['origin']}{other['xpub']}/<0;1>/*))"
        descs, bodies, pattern, counts = g.validate_public_descriptor(cli, raw, None, account["xpub"])
        for i, (desc, body, count) in enumerate(zip(descs, bodies, counts)):
            g.import_signing_descriptor(cli, wallet, desc, body, pattern, count,
                                        account["xpub"], account["xprv"], internal=i == 1)
        before = {d["desc"]: d for d in g.rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]}
        g.import_public_descriptor(cli, wallet, raw)
        after = {d["desc"]: d for d in g.rpc(cli, "listdescriptors", wallet=wallet)["descriptors"]}
        for desc in descs:
            self.assertTrue(after[desc]["active"])
            for field in ("range", "next_index", "timestamp"):
                self.assertEqual(after[desc][field], before[desc][field])
        receive = g.rpc(cli, "getnewaddress", "", "bech32", wallet=wallet)
        change = g.rpc(cli, "getrawchangeaddress", "bech32", wallet=wallet)
        self.assertEqual([receive], g.rpc(cli, "deriveaddresses", descs[0], "[0,0]"))
        self.assertEqual([change], g.rpc(cli, "deriveaddresses", descs[1], "[0,0]"))
        before = g.rpc(cli, "listdescriptors", wallet=wallet)
        g.import_public_descriptor(cli, wallet, raw)
        self.assertEqual(before, g.rpc(cli, "listdescriptors", wallet=wallet))

    def test_existing_active_policy_state_is_preserved(self):
        cli = os.environ["CORE_TEST_CLI"]
        wallet = "already-active"
        with patch("builtins.input", side_effect=["1", wallet]), contextlib.redirect_stdout(io.StringIO()):
            g.create_signer(cli, "/bin/true", 1)
        account = next(key for key in g.rpc(cli, "gethdkeys", '{"private":true}', wallet=wallet) if any(
            g.descriptor_body(desc["desc"]).startswith("unused([") for desc in key["descriptors"]))
        public = g.descriptor_body(account["descriptors"][0]["desc"])[7:-1]
        raw = f"wpkh({public}/0/*)"
        private_body = raw.replace(account["xpub"], account["xprv"])
        checksum = g.rpc(cli, "getdescriptorinfo", private_body, sensitive=True)["checksum"]
        request = [{"desc": private_body + "#" + checksum, "active": True, "range": [0, 20], "next_index": 7, "timestamp": "now"}]
        self.assertTrue(g.rpc(cli, "importdescriptors", json.dumps(request), wallet=wallet, sensitive=True)[0]["success"])
        before = g.rpc(cli, "listdescriptors", wallet=wallet)
        with patch.object(g, "import_signing_descriptor", side_effect=AssertionError("Existing descriptor reimported")):
            g.import_public_descriptor(cli, wallet, raw)
        self.assertEqual(g.rpc(cli, "listdescriptors", wallet=wallet), before)


if __name__ == "__main__":
    unittest.main()
