#!/bin/sh
set -e

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
umask 077

project_slug="core-multisig-signer"
output_dir_name="signer-wallets"

zenity --text-info \
    --title="Pre-Creation Guide" \
    --filename="$here/PRE-CREATION-GUIDE.txt" \
    --width=800 \
    --height=700 \
    >/dev/null 2>&1 &

echo "Please read PRE-CREATION-GUIDE.txt before creating a signer, if you have not already done so."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 was not found." >&2
    exit 1
fi

if ! command -v qr >/dev/null 2>&1; then
    echo "Error: qr was not found. Tails provides it through python3-qrcode." >&2
    exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
    echo "Error: nmcli was not found." >&2
    exit 1
fi

nmcli networking off
if [ "$(LC_ALL=C nmcli networking)" != "disabled" ]; then
    echo "Failed to disable networking."
    exit 1
fi

state=$(mktemp -d "/dev/shm/$project_slug.XXXXXX")
trap 'rm -rf "$state"' EXIT
trap 'exit 1' HUP INT TERM

archive="$here/../bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz"

# Bitcoin Core Feature Overlay baseline, reviewed for this utility:
# https://bitcoincore.org/bin/bitcoin-core-32.0/test.rc2/SHA256SUMS
printf '0255103718033e6aee15fa944717fc277e047b845bff1e7408af0ea732d8d0c1  %s\n' "$archive" | sha256sum --check

core_dir=$(mktemp -d "$here/../bitcoin-32.0rc2-$project_slug.XXXXXX")
tar -xzf "$archive" -C "$core_dir" --strip-components=1 --no-same-owner

bitcoin_cli="$core_dir/bin/bitcoin-cli"
bitcoind_bin="$core_dir/bin/bitcoind"
qr_bin=$(command -v qr)

if [ ! -x "$bitcoin_cli" ] || [ ! -x "$bitcoind_bin" ]; then
    echo "Bitcoin Core v32.0rc2 binaries missing or not executable in the verified extraction."
    exit 1
fi

output_dir="$here/$output_dir_name"

original_home=$HOME
export HOME="$state"
cd "$here"

stop_core() {
    "$bitcoin_cli" stop >/dev/null 2>&1 || true
    pkill -TERM -x bitcoind >/dev/null 2>&1 || true
    pkill -TERM -x bitcoin-qt >/dev/null 2>&1 || true

    while pgrep -x bitcoind >/dev/null 2>&1 || pgrep -x bitcoin-qt >/dev/null 2>&1; do
        sleep 1
    done
}

cleanup() {
    stop_core
    rm -rf "$state"
}

trap cleanup EXIT

stop_core

# Fail closed rather than reuse an old signer output.
mkdir "$output_dir"

"$bitcoind_bin" -daemonwait -networkactive=0 -listen=0 -walletdir="$output_dir"
printf '\n'

python3 "$here/generator.py" "$bitcoin_cli" "$qr_bin"

cleanup
trap - EXIT HUP INT TERM
export HOME="$original_home"

setsid -f zenity --text-info \
    --title="Post-Creation Guide" \
    --filename="$here/POST-CREATION-GUIDE.txt" \
    --width=800 \
    --height=700 \
    </dev/null >/dev/null 2>&1

echo "Please read POST-CREATION-GUIDE.txt."
printf '\nSigner creation complete. You may now close this window.\n'
