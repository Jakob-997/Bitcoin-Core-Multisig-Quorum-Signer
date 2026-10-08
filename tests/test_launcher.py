"""Run with a POSIX shell; all OS/Core commands are disposable test doubles."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("LAUNCHER_TEST_SH") or shutil.which("sh"), "A POSIX shell is required")
class MenuTests(unittest.TestCase):
    def test_word_menu_and_shortcuts(self):
        shell = os.environ.get("LAUNCHER_TEST_SH") or shutil.which("sh")
        launcher = Path(__file__).resolve().parents[1] / "tails.sh"
        subprocess.run([shell, "-n", str(launcher)], check=True)
        def shell_path(value):
            path = Path(value).resolve()
            return "/" + path.drive[0].lower() + path.as_posix()[2:] if os.name == "nt" else path.as_posix()
        shell_directory = shell_path(Path(shell).parent)
        # Stop at the first OS action; never change actual network state.
        cases = [([], "create\n", 0), ([], "import\n", 0),
                 ([], "c\n", 0), ([], "C\n", 0), ([], "i\n", 0), ([], "I\n", 0),
                 ([], "1\n\ninvalid\ncreate\n", 3),
                 (["create"], "", 0), (["import"], "", 0),
                 (["c"], "", 0), (["C"], "", 0), (["i"], "", 0), (["I"], "", 0),
                 ([], "", 0), (["1"], "", 0)]
        for args, input_text, retries in cases:
            with self.subTest(args=args, input=input_text), tempfile.TemporaryDirectory(prefix="menu-test-") as directory:
                root = Path(directory)
                marker = root / "network-action"
                for command in ["python3", "qr", "zenity", "nmcli"]:
                    path = root / command
                    body = 'printf action > "$MENU_TEST_MARKER"\nexit 17' if command == "nmcli" else "exit 0"
                    path.write_text("#!/bin/sh\n" + body + "\n", newline="\n")
                    path.chmod(0o700)
                # A shell assignment keeps MSYS paths/PATH conversion local.
                driver = root / "run.sh"
                driver.write_text('PATH="$MENU_TEST_BIN:$MENU_TEST_SHELL_BIN:/usr/bin:/bin"\nexport PATH\nexec "$MENU_TEST_SHELL" "$MENU_TEST_LAUNCHER" "$@"\n', newline="\n")
                env = dict(os.environ, MENU_TEST_BIN=shell_path(root), MENU_TEST_SHELL_BIN=shell_directory,
                           MENU_TEST_SHELL=shell_path(shell), MENU_TEST_LAUNCHER=shell_path(launcher), MENU_TEST_MARKER=shell_path(marker))
                result = subprocess.run([shell, str(driver)] + args, input=input_text.encode(), env=env, capture_output=True, timeout=10)
                accepted = bool(input_text) or args in (["create"], ["import"], ["c"], ["C"], ["i"], ["I"])
                self.assertEqual(marker.exists(), accepted, result.stderr)
                self.assertEqual(result.returncode, 17 if accepted else 1, result.stderr)
                self.assertEqual(result.stdout.count(b"Please type create (c) or import (i)."), retries)
                self.assertEqual(b"Type create (c) or import (i):" in result.stdout, not args)


@unittest.skipUnless(os.name == "posix", "Launcher requires a POSIX environment")
class LauncherTests(unittest.TestCase):
    def test_success_and_failures(self):
        launcher = Path(__file__).resolve().parents[1] / "tails.sh"
        subprocess.run(["sh", "-n", str(launcher)], check=True)
        cases = ["success", "archive", "extraction", "existing", "startup", "generator", "interrupt", "shutdown", "import", "import-missing", "menu-create", "menu-import", "menu-retry", "menu-c", "menu-C", "menu-i", "menu-I"]
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="overlay-test-") as directory:
                root = Path(directory)
                project = root / "project"
                project.mkdir()
                shutil.copyfile(launcher, project / "tails.sh")
                (project / "keep-source").touch()
                (root / "bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz").touch()
                if case in {"existing", "import", "menu-import", "menu-i", "menu-I"}:
                    (project / "descriptor-signer-wallets").mkdir()
                    (project / "descriptor-signer-wallets/keep-wallet").touch()
                commands = root / "commands"
                commands.mkdir()
                stubs = {
                    "zenity": "exit 0",
                    "setsid": "exit 0",
                    "qr": "exit 0",
                    "nmcli": 'echo disabled',
                    "sha256sum": 'cat >/dev/null; [ "$CASE" != archive ]',
                    "mktemp": '''case "$*" in
                        */dev/shm/*) target="$TEST_ROOT/state" ;;
                        *) target="$TEST_ROOT/core-extracted" ;;
                        esac
                        mkdir "$target"
                        printf '%s\\n' "$target"''',
                    "tar": '''[ "$CASE" != extraction ] || exit 1
                        mkdir -p "$TEST_ROOT/core-extracted/bin"
                        cp "$TEST_ROOT/commands/bitcoind" "$TEST_ROOT/core-extracted/bin/bitcoind"
                        cp "$TEST_ROOT/commands/bitcoin-cli" "$TEST_ROOT/core-extracted/bin/bitcoin-cli"''',
                    "bitcoind": '''trap '[ "$CASE" != shutdown ] || exit 7; exit 0' TERM
                        touch "$TEST_ROOT/ready"
                        while :; do sleep 0.05; done''',
                    "bitcoin-cli": '''while [ ! -f "$TEST_ROOT/ready" ]; do sleep 0.01; done
                        [ "$CASE" != startup ]''',
                    "python3": '''printf '%s' "$4" > "$TEST_ROOT/selected-step"
                        touch "$TEST_ROOT/project/descriptor-signer-wallets/keep-wallet"
                        [ "$CASE" != generator ] || exit 1
                        if [ "$CASE" = interrupt ]; then kill -TERM "$PPID"; exit 1; fi''',
                    # Refuse deletion outside this test's freshly created root.
                    "rm": '''for path do
                        case "$path" in -*) ;; "$TEST_ROOT"/*) ;; *) exit 99 ;; esac
                        done
                        exec /bin/rm "$@"''',
                }
                for name, body in stubs.items():
                    script = commands / name
                    script.write_text("#!/bin/sh\n" + body + "\n")
                    script.chmod(0o700)
                env = dict(os.environ, CASE=case, TEST_ROOT=str(root), PATH=f"{commands}:/usr/bin:/bin")
                args = ["import"] if case in {"import", "import-missing"} else ["create"]
                input_text = None
                if case.startswith("menu-"):
                    args = []
                    input_text = b"import\n" if case == "menu-import" else b"create\n"
                    if case == "menu-retry":
                        input_text = b"1\n\ninvalid\ncreate\n"
                    if case in {"menu-c", "menu-C", "menu-i", "menu-I"}:
                        input_text = (case[-1] + "\n").encode()
                result = subprocess.run(["sh", str(project / "tails.sh")] + args, input=input_text, env=env, capture_output=True, timeout=10)
                success = case in {"success", "existing", "import", "menu-create", "menu-import", "menu-retry", "menu-c", "menu-C", "menu-i", "menu-I"}
                self.assertEqual(result.returncode == 0, success, result.stderr.decode())
                if success:
                    self.assertEqual((root / "selected-step").read_text(), "import" if case in {"import", "menu-import", "menu-i", "menu-I"} else "create")
                self.assertTrue((project / "keep-source").exists())
                self.assertTrue((root / "bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz").exists())
                if success or case in {"generator", "interrupt", "shutdown"}:
                    self.assertTrue((project / "descriptor-signer-wallets/keep-wallet").exists())
                self.assertEqual((root / "core-extracted").exists(), not success and case != "archive")
                self.assertEqual((root / "state").exists(), case == "shutdown")


if __name__ == "__main__":
    unittest.main()
