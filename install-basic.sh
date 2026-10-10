#!/bin/sh
# github.com/Shran21
#
# One command that fetches reBSGO from GitHub and runs its installer:
#
#   curl -fsSL https://raw.githubusercontent.com/Shran21/reBSGO/main/install-basic.sh | sudo sh
#   wget -qO- https://raw.githubusercontent.com/Shran21/reBSGO/main/install-basic.sh | sudo sh
#
# Switches, after `sh -s --`: --dir <directory> (default /opt/rebsgo, or
# ~/rebsgo without root), --ref <branch or tag> (default main), --no-systemd.
# Run again, it updates: the code is replaced, while .env, sqlite/ and the
# local settings stay. A fork sets REBSGO_REPO=<owner>/<repo>, a mirror
# REBSGO_URL=<the .tar.gz to fetch>.
#
# Nothing runs before the very last line calls fo: piped into sh, a download
# cut off halfway runs nothing at all, not half a script.

set -u

fo() {
    TAROLO=${REBSGO_REPO:-Shran21/reBSGO}
    REF=${REBSGO_REF:-main}
    CEL=${REBSGO_DIR:-}
    TOVABB=""

    case "${REBSGO_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in
        hu*|HU*|magyar*|Hungarian*) NYELV=hu ;;
        *) NYELV=en ;;
    esac
    REBSGO_LANG=$NYELV
    export REBSGO_LANG

    if [ -t 2 ]; then
        ZOLD=$(printf '\033[1;32m'); CIAN=$(printf '\033[1;36m')
        PIROS=$(printf '\033[1;31m'); SARGA=$(printf '\033[1;33m'); VEGE=$(printf '\033[0m')
    else
        ZOLD=; CIAN=; PIROS=; SARGA=; VEGE=
    fi

    while [ $# -gt 0 ]; do
        case "$1" in
            --dir) [ $# -gt 1 ] || fail "--dir: $(t 'hiányzik az útvonal' 'missing path')"
                   shift; CEL=$1 ;;
            --dir=*) CEL=${1#--dir=} ;;
            --ref) [ $# -gt 1 ] || fail "--ref: $(t 'hiányzik az ág vagy a tag' 'missing branch or tag')"
                   shift; REF=$1 ;;
            --ref=*) REF=${1#--ref=} ;;
            --no-systemd) TOVABB="--no-systemd" ;;
            -h|--help) printf '%s\n' "curl -fsSL https://raw.githubusercontent.com/$TAROLO/main/install-basic.sh | sudo sh -s -- [--dir <dir>] [--ref <branch|tag>] [--no-systemd]"
                       exit 0 ;;
            *) fail "$(t 'ismeretlen kapcsoló:' 'unknown flag:') $1" ;;
        esac
        shift
    done

    printf '\n%sreBSGO — %s%s\n' "$CIAN" "$(t 'letöltés és telepítés' 'download and install')" "$VEGE"
    printf '    %s: github.com/%s (%s)\n' "$(t 'forrás' 'source')" "$TAROLO" "$REF"

    if (exec </dev/tty) 2>/dev/null; then TTY=1; else TTY=0; fi

    if [ "$(id -u)" = 0 ]; then
        ALAP=/opt/rebsgo
    else
        ALAP="$HOME/rebsgo"
        figyel "$(t 'nem rootként fut: a bsgo és a rebsgo-panel szolgáltatás nem kerül fel' 'not running as root: the bsgo and rebsgo-panel services will not be installed')"
        mond "$(t 'teljes telepítéshez: ... | sudo sh' 'for the full installation: ... | sudo sh')"
    fi

    if [ -z "$CEL" ]; then
        if [ "$TTY" = 1 ]; then
            mond "$(t 'Hova kerüljön a szerver? Enter =' 'Where should the server live? Enter =') $ALAP"
            printf '    %s: ' "$(t 'célmappa' 'target directory')"
            read -r CEL </dev/tty || CEL=""
        fi
        CEL=${CEL:-$ALAP}
    fi
    # shellcheck disable=SC2088
    case "$CEL" in
        "~") CEL="$HOME" ;;
        "~/"*) CEL="$HOME/${CEL#\~/}" ;;
    esac
    case "$CEL" in /*) : ;; *) CEL="$PWD/$CEL" ;; esac
    if [ -f "$CEL/install.sh" ]; then
        kesz "$(t 'meglévő telepítés - frissítem; a .env, az sqlite/ és a helyi beállítások maradnak:' 'an existing installation - updating it; .env, sqlite/ and the local settings stay:') $CEL"
    else
        kesz "$(t 'célmappa:' 'target directory:') $CEL"
    fi

    for PARANCS in tar gzip mktemp; do
        command -v "$PARANCS" >/dev/null 2>&1 \
            || fail "$(t "hiányzik a(z) $PARANCS parancs" "the $PARANCS command is missing")"
    done
    if command -v curl >/dev/null 2>&1; then
        LETOLTO=curl
    elif command -v wget >/dev/null 2>&1; then
        LETOLTO=wget
    else
        fail "$(t 'se curl, se wget - telepítsd az egyiket (pl. apt install curl)' 'neither curl nor wget - install one of them (e.g. apt install curl)')"
    fi

    ATMENETI=$(mktemp -d "${TMPDIR:-/tmp}/rebsgo.XXXXXX") \
        || fail "$(t 'nem tudok átmeneti mappát nyitni' 'cannot open a temporary directory')"
    trap 'rm -rf "$ATMENETI"' EXIT
    trap 'rm -rf "$ATMENETI"; exit 130' INT TERM

    URL=${REBSGO_URL:-https://github.com/$TAROLO/archive/$REF.tar.gz}
    mond "$(t 'letöltés:' 'downloading:') $URL"
    if [ "$LETOLTO" = curl ]; then
        JELZO=-sS
        [ -t 2 ] && JELZO=--progress-bar
        curl -fL "$JELZO" -o "$ATMENETI/rebsgo.tar.gz" "$URL"
    else
        wget -q -O "$ATMENETI/rebsgo.tar.gz" "$URL"
    fi || fail "$(t 'a letöltés nem sikerült - jó az ág vagy a tag neve, van hálózat?' 'the download failed - is the branch or tag name right, is there a network?')"

    mkdir "$ATMENETI/fa"
    tar xzf "$ATMENETI/rebsgo.tar.gz" -C "$ATMENETI/fa" --strip-components=1 \
        || fail "$(t 'a letöltött csomag nem bontható ki' 'the downloaded archive cannot be unpacked')"
    rm -f "$ATMENETI/rebsgo.tar.gz"
    [ -f "$ATMENETI/fa/install.sh" ] && [ -d "$ATMENETI/fa/src/rebsgo" ] \
        || fail "$(t 'a letöltött fában nincs install.sh vagy src/rebsgo' 'the downloaded tree has no install.sh or src/rebsgo')"
    kesz "$(t 'letöltve:' 'downloaded:') reBSGO $(cat "$ATMENETI/fa/VERSION" 2>/dev/null || printf '%s' "$REF")"

    # The installer asks its questions on stdin, which here is the pipe the
    # script came through; the terminal is still there, on /dev/tty.
    # shellcheck disable=SC2086
    if [ "$TTY" = 1 ]; then
        sh "$ATMENETI/fa/install.sh" --dir "$CEL" $TOVABB </dev/tty
    else
        sh "$ATMENETI/fa/install.sh" --dir "$CEL" $TOVABB </dev/null
    fi
    RC=$?
    if [ "$RC" != 0 ]; then
        printf '\n%s✘ %s%s\n' "$PIROS" "$(t "a telepítő hibával állt meg (kód: $RC)" "the installer stopped with an error (code: $RC)")" "$VEGE" >&2
        [ -f "$CEL/install.sh" ] && mond "$(t 'a hiba kijavítása után folytatható:' 'once the cause is fixed, carry on with:') sh $CEL/install.sh --here"
    fi
    return "$RC"
}

t() {
    if [ "$NYELV" = hu ]; then printf '%s' "$1"; else printf '%s' "$2"; fi
}
kesz()  { printf '  %s✔ %s%s\n' "$ZOLD" "$*" "$VEGE"; }
mond()  { printf '    %s\n' "$*"; }
figyel(){ printf '  %s! %s%s\n' "$SARGA" "$*" "$VEGE"; }
fail()  { printf '\n%s✘ %s: %s%s\n' "$PIROS" "$(t 'HIBA' 'ERROR')" "$*" "$VEGE" >&2; exit 1; }

fo "$@"
