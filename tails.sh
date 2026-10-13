#!/bin/sh
set -eu
umask 077
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

if [ "$#" -eq 0 ]; then
    printf '(c)reate - Create wallet and export public key\n(i)mport - Import descriptor into an existing wallet\n'
    while :; do
        printf '\nType create (c) or import (i): '
        IFS= read -r step || exit 1
        case "$step" in
            create|c|C) step=create; break ;;
            import|i|I) step=import; break ;;
            *) echo "Please type create (c) or import (i)." ;;
        esac
    done
else
    [ "$#" -eq 1 ] || { echo "Usage: sh tails.sh [create|import]" >&2; exit 1; }
    case "$1" in
        create|c|C) step=create ;;
        import|i|I) step=import ;;
        *) echo "Usage: sh tails.sh [create|import]" >&2; exit 1 ;;
    esac
fi

for command in python3 qr nmcli; do
    command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
nmcli networking off
[ "$(LC_ALL=C nmcli networking)" = disabled ] || { echo "Networking is still enabled." >&2; exit 1; }

output_dir="$here/descriptor-signer-wallets"
if [ "$step" = import ]; then
    [ -d "$output_dir" ] || { echo "Run sh tails.sh create first." >&2; exit 1; }
else
    mkdir -p "$output_dir"
fi
archive="$here/../bitcoin-32.0rc2-x86_64-linux-gnu.tar.gz"
printf '0255103718033e6aee15fa944717fc277e047b845bff1e7408af0ea732d8d0c1  %s\n' "$archive" | sha256sum --check

state=$(mktemp -d /dev/shm/core-descriptor-signer.XXXXXX)
core_pid=""
cleanup() {
    if [ -n "$core_pid" ]; then
        kill -TERM "$core_pid" 2>/dev/null || true
        wait "$core_pid" || return 1
        core_pid=""
    fi
    rm -rf -- "$state"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
core_dir=$(mktemp -d "$here/../bitcoin-32.0rc2-core-descriptor-signer.XXXXXX")
tar -xzf "$archive" -C "$core_dir" --strip-components=1 --no-same-owner

# The wrapper uses the same isolated datadir for every RPC, including later loads.
printf '#!/bin/sh\nexec "%s" -datadir="%s" "$@"\n' "$core_dir/bin/bitcoin-cli" "$state" > "$state/bitcoin-cli"
chmod 700 "$state/bitcoin-cli"
"$core_dir/bin/bitcoind" -datadir="$state" -daemon=0 -printtoconsole=0 \
    -networkactive=0 -listen=0 -walletdir="$output_dir" &
core_pid=$!
"$state/bitcoin-cli" -rpcwait -rpcwaittimeout=60 getblockchaininfo >/dev/null
python3 "$here/generator.py" "$state/bitcoin-cli" "$(command -v qr)" "$step"
cleanup
rm -rf -- "$core_dir"
trap - EXIT HUP INT TERM
printf '\nStep complete. Back up descriptor-signer-wallets/ before shutting down Tails.\n'
