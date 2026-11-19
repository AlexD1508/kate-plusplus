#!/usr/bin/env bash
# Kate++ installer.
#
#   curl -fsSL https://raw.githubusercontent.com/AlexD1508/kate-plusplus/main/install.sh | bash
#
# Extra options go after `bash -s --`, e.g.  ... | bash -s -- --profile generic --no-overlay
set -euo pipefail

REPO_URL="https://github.com/AlexD1508/kate-plusplus.git"
DEST="${KPP_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/kate-plusplus/app}"

here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [[ -n "$here" && -x "$here/bin/kate-plusplus" && -d "$here/lib/kpp" ]]; then
    exec "$here/bin/kate-plusplus" install "$@"          # running from a checkout
fi

for tool in git python3; do
    command -v "$tool" >/dev/null || { echo "Kate++ needs '$tool'. Please install it first." >&2; exit 1; }
done

if [[ -d "$DEST/.git" ]]; then
    git -C "$DEST" pull --ff-only --quiet
else
    mkdir -p "$(dirname "$DEST")"
    git clone --depth 1 --quiet "$REPO_URL" "$DEST"
fi
exec "$DEST/bin/kate-plusplus" install "$@"
