#!/bin/sh
# github.com/Shran21
#
# Removes a reBSGO installation: the bsgo and rebsgo-panel services and the
# tree, keeping the players' data or not, as chosen.
#
#   sudo sh /opt/rebsgo/uninstall.sh
#   sudo sh uninstall.sh --dir /opt/rebsgo --keep-data --yes
#
# --keep-data     the program goes, the data stays where it is: sqlite/, .env,
#                 WebPanel/panel.env, GameData/local; installing into the same
#                 directory again picks all of it up
# --backup FILE   the data goes into FILE (.tar.gz) first, then everything goes
# --purge         everything goes, the players' data included
# --yes           no questions (needs one of the three above)
#
# Nothing runs before the very last line calls fo: sh reads the whole script
# first, so removing the tree it sits in cannot cut it off halfway.

set -u

MEGTARTOTT="sqlite .env WebPanel/panel.env GameData/local"

fo() {
    HERE=$(cd "$(dirname "$0")" && pwd)
    ROOT=""
    MOD=""
    ARCHIV=""
    IGEN=0

    case "${REBSGO_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in
        hu*|HU*|magyar*|Hungarian*) NYELV=hu ;;
        *) NYELV=en ;;
    esac
    if [ -t 1 ]; then
        ZOLD=$(printf '\033[1;32m'); CIAN=$(printf '\033[1;36m')
        PIROS=$(printf '\033[1;31m'); SARGA=$(printf '\033[1;33m')
        VASTAG=$(printf '\033[1m'); VEGE=$(printf '\033[0m')
    else
        ZOLD=; CIAN=; PIROS=; SARGA=; VASTAG=; VEGE=
    fi

    while [ $# -gt 0 ]; do
        case "$1" in
            --dir) [ $# -gt 1 ] || fail "--dir: $(t 'hiányzik az útvonal' 'missing path')"
                   shift; ROOT=$1 ;;
            --dir=*) ROOT=${1#--dir=} ;;
            --keep-data) MOD=megtart ;;
            --backup) [ $# -gt 1 ] || fail "--backup: $(t 'hiányzik a fájl' 'missing file')"
                      shift; MOD=ment; ARCHIV=$1 ;;
            --backup=*) MOD=ment; ARCHIV=${1#--backup=} ;;
            --purge) MOD=mindent ;;
            --yes|-y) IGEN=1 ;;
            -h|--help) sed -n '3,16s/^# \{0,1\}//p' "$0"; exit 0 ;;
            *) fail "$(t 'ismeretlen kapcsoló:' 'unknown flag:') $1" ;;
        esac
        shift
    done
    [ "$IGEN" = 0 ] || [ -n "$MOD" ] \
        || fail "$(t '--yes mellé kell a --keep-data, a --backup vagy a --purge' '--yes needs --keep-data, --backup or --purge with it')"
    if (exec </dev/tty) 2>/dev/null; then TTY=1; else TTY=0; fi
    [ "$IGEN" = 1 ] || [ "$TTY" = 1 ] \
        || fail "$(t 'nincs terminál a kérdésekhez - használd a --yes kapcsolót egy móddal' 'no terminal for the questions - use --yes with a mode')"

    printf '\n%sreBSGO — %s%s\n' "$CIAN" "$(t 'eltávolítás' 'uninstall')" "$VEGE"

    fazis 1 "$(t 'Mi van telepítve' 'What is installed')"
    ROOT=${ROOT:-$HERE}
    case "$ROOT" in /*) : ;; *) ROOT="$PWD/$ROOT" ;; esac
    [ -d "$ROOT" ] || fail "$(t 'nincs ilyen mappa:' 'no such directory:') $ROOT"
    ROOT=$(cd "$ROOT" && pwd)
    case "$ROOT" in
        /|/opt|/usr|/usr/local|/home|/root|/srv|/var|"${HOME:-/root}")
            fail "$(t 'ezt a mappát nem törlöm:' 'this directory is not one to remove:') $ROOT" ;;
    esac
    [ -d "$ROOT/src/rebsgo" ] && [ -f "$ROOT/install.sh" ] \
        || fail "$(t 'ez nem egy reBSGO-fa (nincs src/rebsgo és install.sh):' 'this is not a reBSGO tree (no src/rebsgo and install.sh):') $ROOT"
    kesz "$(t 'telepítés:' 'installation:') $ROOT ($(du -sh "$ROOT" 2>/dev/null | cut -f1))"
    if [ -f "$ROOT/sqlite/bgo_server.db" ]; then
        mond "$(t 'adatbázis:' 'database:') sqlite/bgo_server.db ($(du -sh "$ROOT/sqlite" 2>/dev/null | cut -f1))"
    else
        mond "$(t 'adatbázis: nincs (a szerver még nem indult el)' 'database: none (the server never started)')"
    fi
    [ -d "$ROOT/.git" ] && figyel "$(t 'ez egy git-klón is: a törlés a klónt is viszi' 'this is a git clone as well: removing it takes the clone too')"

    EGYSEGEK=""
    for EGYSEG in bsgo rebsgo-panel; do
        FAJL="/etc/systemd/system/$EGYSEG.service"
        [ -f "$FAJL" ] || continue
        MUNKAHELY=$(sed -n 's/^WorkingDirectory=//p' "$FAJL" | tail -1)
        if [ "$MUNKAHELY" = "$ROOT" ] || [ "$MUNKAHELY" = "$ROOT/WebPanel" ]; then
            EGYSEGEK="$EGYSEGEK $EGYSEG"
            mond "$(t 'szolgáltatás:' 'service:') $EGYSEG ($(systemctl is-active "$EGYSEG" 2>/dev/null || true))"
        else
            figyel "$(t "a(z) $EGYSEG szolgáltatás egy másik telepítéshez tartozik - nem nyúlok hozzá" "the $EGYSEG service belongs to another installation - left alone")"
        fi
    done
    [ -n "$EGYSEGEK" ] || mond "$(t 'szolgáltatás: nincs ehhez a telepítéshez' 'services: none for this installation')"
    if [ -n "$EGYSEGEK" ] && [ "$(id -u)" != 0 ]; then
        fail "$(t 'a szolgáltatások eltávolításához root kell: sudo sh' 'removing the services needs root: sudo sh') $0"
    fi
    MENTESEK=$(sed -n 's/^PANEL_BACKUP_DIR=//p' "$ROOT/WebPanel/panel.env" 2>/dev/null | tail -1)
    MENTESEK=${MENTESEK:-/opt/bsgo-backups}

    fazis 2 "$(t 'Mit töröljek?' 'What should go?')"
    if [ -z "$MOD" ]; then
        mond "1) $(t 'a programot; az adatok maradnak a helyükön (ajánlott)' 'the program; the data stays where it is (recommended)')"
        mond "   $(t 'sqlite/, .env, WebPanel/panel.env, GameData/local - egy újabb telepítés ugyanide visszakapja őket' 'sqlite/, .env, WebPanel/panel.env, GameData/local - installing here again picks them up')"
        mond "2) $(t 'mindent, de előtte az adatokat egy .tar.gz mentésbe teszem' 'everything, after putting the data into a .tar.gz backup')"
        mond "3) $(t 'mindent, mentés nélkül - a játékosok adatai is elvesznek' 'everything, with no backup - player data is lost too')"
        mond "0) $(t 'mégse' 'cancel')"
        printf '    %s [1]: ' "$(t 'választás' 'choice')"
        read -r VALASZ </dev/tty || VALASZ=0
        case "${VALASZ:-1}" in
            1) MOD=megtart ;;
            2) MOD=ment ;;
            3) MOD=mindent ;;
            *) mond "$(t 'mégse - semmi nem változott' 'cancelled - nothing changed')"; exit 0 ;;
        esac
    fi
    if [ "$MOD" = ment ] && [ -z "$ARCHIV" ]; then
        ARCHIV="$(dirname "$ROOT")/$(basename "$ROOT")-$(t adatok data)-$(date +%Y%m%d-%H%M%S).tar.gz"
        if [ "$IGEN" = 0 ]; then
            printf '    %s [%s]: ' "$(t 'mentés ide' 'backup to')" "$ARCHIV"
            read -r VALASZ </dev/tty || VALASZ=""
            ARCHIV=${VALASZ:-$ARCHIV}
        fi
    fi
    if [ -n "$ARCHIV" ]; then
        case "$ARCHIV" in /*) : ;; *) ARCHIV="$PWD/$ARCHIV" ;; esac
        case "$ARCHIV" in
            "$ROOT"/*) fail "$(t 'a mentés nem kerülhet a törlendő mappába:' 'the backup cannot go inside the directory being removed:') $ARCHIV" ;;
        esac
        [ ! -e "$ARCHIV" ] || fail "$(t 'ez a fájl már létezik:' 'this file exists already:') $ARCHIV"
    fi
    case "$MOD" in
        megtart) kesz "$(t 'a program megy, az adatok maradnak:' 'the program goes, the data stays:') $ROOT" ;;
        ment) kesz "$(t 'mentés ide, utána minden megy:' 'backup to this file, then everything goes:') $ARCHIV" ;;
        mindent) figyel "$(t 'minden megy, mentés nélkül - a játékosok adatai is' 'everything goes, with no backup - player data too')" ;;
    esac
    if [ "$IGEN" = 0 ]; then
        if [ "$MOD" = mindent ]; then
            SZO=$(t torles delete)
            printf '    %s %s%s%s: ' "$(t 'Biztos? Írd be:' 'Sure? Type:')" "$VASTAG" "$SZO" "$VEGE"
            read -r VALASZ </dev/tty || VALASZ=""
            [ "$VALASZ" = "$SZO" ] || { mond "$(t 'mégse - semmi nem változott' 'cancelled - nothing changed')"; exit 0; }
        else
            printf '    %s [i/N]: ' "$(t 'Mehet?' 'Go ahead?')"
            read -r VALASZ </dev/tty || VALASZ=""
            case "$VALASZ" in
                i|I|igen|y|Y|yes) : ;;
                *) mond "$(t 'mégse - semmi nem változott' 'cancelled - nothing changed')"; exit 0 ;;
            esac
        fi
    fi

    fazis 3 "$(t 'Leállítás' 'Stopping')"
    if [ -n "$EGYSEGEK" ]; then
        mond "$(t 'leállítás (a bsgo kilépéskor elmenti a pilótákat)...' 'stopping (on the way out bsgo saves the pilots)...')"
        # shellcheck disable=SC2086
        systemctl stop $EGYSEGEK || fail "$(t 'a szolgáltatások nem álltak le' 'the services did not stop')"
        # shellcheck disable=SC2086
        systemctl disable $EGYSEGEK >/dev/null 2>&1
        for EGYSEG in $EGYSEGEK; do
            rm -f "/etc/systemd/system/$EGYSEG.service"
        done
        systemctl daemon-reload
        systemctl reset-failed >/dev/null 2>&1
        kesz "$(t 'szolgáltatások leállítva és eltávolítva:' 'services stopped and removed:')$EGYSEGEK"
    fi
    # A server or panel started by hand runs from this tree too, and its
    # database has to be closed before the files go. Only those two are looked
    # for: a shell standing in the directory is no business of this script.
    FUTOK=""
    for CWD in /proc/[0-9]*/cwd; do
        CEL=$(readlink "$CWD" 2>/dev/null) || continue
        case "$CEL" in "$ROOT"|"$ROOT/WebPanel") : ;; *) continue ;; esac
        PID=${CWD#/proc/}; PID=${PID%/cwd}
        case "$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null)" in
            *rebsgo.main*|*panel.app:app*) FUTOK="$FUTOK $PID" ;;
        esac
    done
    if [ -n "$FUTOK" ]; then
        mond "$(t 'kézzel indított folyamatok ebből a mappából:' 'processes started by hand from this directory:')$FUTOK"
        # shellcheck disable=SC2086
        kill -TERM $FUTOK 2>/dev/null
        VARAKOZAS=0
        while [ $VARAKOZAS -lt 30 ]; do
            MARAD=""
            for PID in $FUTOK; do kill -0 "$PID" 2>/dev/null && MARAD="$MARAD $PID"; done
            [ -n "$MARAD" ] || break
            sleep 1; VARAKOZAS=$((VARAKOZAS + 1))
        done
        [ -z "$MARAD" ] || fail "$(t 'ezek nem álltak le 30 mp alatt - állítsd le őket, és futtasd újra:' 'these did not stop within 30 s - stop them and run this again:')$MARAD"
        kesz "$(t 'leállítva' 'stopped')"
    fi
    [ -n "$EGYSEGEK" ] || [ -n "$FUTOK" ] || kesz "$(t 'nem futott semmi' 'nothing was running')"

    fazis 4 "$(t 'Törlés' 'Removing')"
    case "$MOD" in
        megtart)
            TARTO="$ROOT.megmarad.$$"
            mkdir "$TARTO" || fail "$(t 'nem tudok átmeneti mappát nyitni:' 'cannot open a holding directory:') $TARTO"
            for ELEM in $MEGTARTOTT; do
                [ -e "$ROOT/$ELEM" ] || continue
                mkdir -p "$TARTO/$(dirname "$ELEM")"
                mv "$ROOT/$ELEM" "$TARTO/$ELEM" \
                    || fail "$(t 'az adatok félreállítása elakadt, semmi nem törlődött; ami átkerült, itt van:' 'setting the data aside failed, nothing was removed; what was moved is here:') $TARTO"
            done
            rm -rf "$ROOT"
            mv "$TARTO" "$ROOT" || fail "$(t 'az adatok itt maradtak:' 'the data was left here:') $TARTO"
            kesz "$(t 'a program törölve, az adatok a helyükön:' 'the program is removed, the data is in place:') $ROOT"
            ;;
        ment)
            set --
            for ELEM in $MEGTARTOTT; do
                [ -e "$ROOT/$ELEM" ] && set -- "$@" "$ELEM"
            done
            [ $# -gt 0 ] || fail "$(t 'nincs mit menteni - semmi nem törlődött' 'there is nothing to back up - nothing was removed')"
            if ! { tar czf "$ARCHIV" -C "$ROOT" "$@" && tar tzf "$ARCHIV" >/dev/null; }; then
                rm -f "$ARCHIV"
                fail "$(t 'a mentés nem sikerült - semmi nem törlődött' 'the backup failed - nothing was removed')"
            fi
            chmod 600 "$ARCHIV"
            kesz "$(t 'mentés:' 'backup:') $ARCHIV ($(du -h "$ARCHIV" | cut -f1))"
            rm -rf "$ROOT"
            kesz "$(t 'törölve:' 'removed:') $ROOT"
            ;;
        mindent)
            rm -rf "$ROOT"
            kesz "$(t 'törölve:' 'removed:') $ROOT"
            ;;
    esac

    printf '\n%s%s✔ %s%s\n' "$VASTAG" "$ZOLD" "$(t 'Kész.' 'Done.')" "$VEGE"
    case "$PWD" in "$ROOT"|"$ROOT"/*) [ "$MOD" = megtart ] || mond "$(t 'a mappa, ahol állsz, már nincs meg: cd /' 'the directory you stand in is gone: cd /')" ;; esac
    case "$MOD" in
        megtart) mond "$(t 'újratelepítés ugyanide, az adatokkal együtt:' 'installing here again, data and all:')"
                 mond "  curl -fsSL https://raw.githubusercontent.com/Shran21/reBSGO/main/install-basic.sh | sudo sh -s -- --dir $ROOT"
                 mond "$(t 'az adatok végleges törlése:' 'removing the data for good:') rm -rf $ROOT" ;;
        ment) mond "$(t 'visszaállítás egy új telepítésbe (a szolgáltatások leállítása után):' 'restoring into a new installation (with its services stopped):')"
              mond "  tar xzf $ARCHIV -C <$(t 'telepítési mappa' 'install directory')>" ;;
    esac
    [ -d "$MENTESEK" ] && mond "$(t 'a panel mentései megmaradtak, ha kell, töröld kézzel:' 'the panel backups are still there, remove them by hand if need be:') $MENTESEK"
    exit 0
}

t() {
    if [ "$NYELV" = hu ]; then printf '%s' "$1"; else printf '%s' "$2"; fi
}
fazis() { printf '\n%s[%s/4] %s%s\n' "$CIAN" "$1" "$2" "$VEGE"; }
kesz()  { printf '  %s✔ %s%s\n' "$ZOLD" "$*" "$VEGE"; }
mond()  { printf '    %s\n' "$*"; }
figyel(){ printf '  %s! %s%s\n' "$SARGA" "$*" "$VEGE"; }
fail()  { printf '\n%s✘ %s: %s%s\n' "$PIROS" "$(t 'HIBA' 'ERROR')" "$*" "$VEGE" >&2; exit 1; }

fo "$@"
