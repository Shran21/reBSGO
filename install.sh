#!/bin/sh
# github.com/Shran21

set -u
HERE=$(cd "$(dirname "$0")" && pwd)
CHECK=0
SYSTEMD=1
RESTART=1
INPLACE=0
TARGET=""
while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK=1 ;;
        --no-systemd) SYSTEMD=0 ;;
        --no-restart) RESTART=0 ;;
        --here) INPLACE=1 ;;
        --dir) shift; TARGET=${1:-}; [ -n "$TARGET" ] || { echo "--dir: missing path"; exit 2; } ;;
        --dir=*) TARGET=${1#--dir=} ;;
        *) echo "unknown flag: $1"; exit 2 ;;
    esac
    shift
done

case "${REBSGO_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in
    hu*|HU*|magyar*|Hungarian*) NYELV=hu ;;
    *) NYELV=en ;;
esac
t() {
    if [ "$NYELV" = hu ]; then printf '%s' "$1"; else printf '%s' "$2"; fi
}

if [ -t 1 ] || [ "${INSTALL_SZINES:-0}" = 1 ]; then
    ZOLD=$(printf '\033[1;32m'); CIAN=$(printf '\033[1;36m')
    PIROS=$(printf '\033[1;31m'); SARGA=$(printf '\033[1;33m')
    VASTAG=$(printf '\033[1m'); VEGE=$(printf '\033[0m')
else
    ZOLD=; CIAN=; PIROS=; SARGA=; VASTAG=; VEGE=
fi

OSSZES_FAZIS=9
FAZIS=0

fazis() {
    FAZIS=$((FAZIS + 1))
    printf '\n%s[%s/%s] %s%s\n' "$CIAN" "$FAZIS" "$OSSZES_FAZIS" "$1" "$VEGE"
}
kesz()  { printf '  %s✔ %s%s\n' "$ZOLD" "$*" "$VEGE"; }
mond()  { printf '    %s\n' "$*"; }
figyel(){ printf '  %s! %s%s\n' "$SARGA" "$*" "$VEGE"; }
fail()  { printf '\n%s✘ %s: %s%s\n' "$PIROS" "$(t 'HIBA' 'ERROR')" "$*" "$VEGE" >&2; exit 1; }

kibonto() {
    _osszes=$(tar tzf "$1" | wc -l)
    mkdir -p "$2"
    tar xzvf "$1" -C "$2" 2>&1 | awk -v ossz="$_osszes" -v zold="$ZOLD" -v vege="$VEGE" '
        BEGIN { split("5 10 20 30 40 50 60 70 80 90 100", hatar, " "); i = 1 }
        {
            n++
            szazalek = int(n * 100 / ossz)
            while (i <= 11 && szazalek >= hatar[i]) {
                sav = ""
                tele = int(hatar[i] / 5)
                for (j = 1; j <= 20; j++) sav = sav (j <= tele ? "#" : ".")
                printf "    [%s] %s%3d%%%s\n", sav, zold, hatar[i], vege
                i++
            }
        }
        END {
            while (i <= 11) {
                printf "    [####################] %s%3d%%%s\n", zold, hatar[i], vege
                i++
            }
        }'
}

printf '%s' "$CIAN"
cat <<'FELIRAT'
              ____  ____   ____  ___
    _ __ ___ | __ )/ ___| / ___|/ _ \
   | '__/ _ \|  _ \\___ \| |  _| | | |
   | | |  __/| |_) |___) | |_| | |_| |
   |_|  \___||____/|____/ \____|\___/
FELIRAT
printf '%s' "$VEGE"
printf '            %s@ S H R A N 2 1%s\n' "$SARGA" "$VEGE"
printf '            %sgithub.com/Shran21%s\n' "$CIAN" "$VEGE"
printf '   %s%s%s — %s\n' "$VASTAG" "$(t 'telepítő' 'installer')" "$VEGE" "$HERE"
if [ "$CHECK" = 1 ]; then
    figyel "$(t 'ellenőrző mód: semmi nem változik' 'check mode: nothing is changed')"
elif [ "$INPLACE" = 0 ]; then
    sleep 5
fi

fazis "$(t 'Célmappa — hova kerüljön a szerver?' 'Target directory — where should the server live?')"
if [ "$INPLACE" = 1 ]; then
    TARGET="$HERE"
elif [ -z "$TARGET" ]; then
    if [ -t 0 ]; then
        mond "$(t 'Enter = marad itt:' 'Enter = stays here:') $HERE"
        printf '    %s: ' "$(t 'célmappa' 'target directory')"
        read -r VALASZ || VALASZ=""
        TARGET=${VALASZ:-$HERE}
    else
        TARGET="$HERE"
        mond "$(t 'nincs terminál, nem kérdezek: marad itt' 'no terminal, no question asked: it stays here')"
    fi
fi
case "$TARGET" in
    "~") TARGET="$HOME" ;;
    "~/"*) TARGET="$HOME/${TARGET#\~/}" ;;
esac
case "$TARGET" in /*) : ;; *) TARGET="$PWD/$TARGET" ;; esac
if [ "$CHECK" = 0 ]; then
    mkdir -p "$TARGET" || fail "$(t 'a célmappa nem hozható létre:' 'the target directory cannot be created:') $TARGET"
fi
[ -d "$TARGET" ] && TARGET=$(cd "$TARGET" && pwd)
if [ "$TARGET" = "$HERE" ]; then
    kesz "$(t 'helyben marad:' 'staying in place:') $HERE"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(átmásolná ide, és onnan folytatná:' '(it would copy the tree here and carry on from there:') $TARGET)"
else
    mond "$(t 'másolás:' 'copying:') $HERE -> $TARGET"
    KIHAGY="--exclude=./runtime --exclude=./WebPanel/venv --exclude=./logs"
    KIHAGY="$KIHAGY --exclude=./WebPanel/logs --exclude=./cache --exclude=./.git --exclude=__pycache__"
    for ALLAPOT in .env sqlite GameData/local WebPanel/panel.env; do
        [ -e "$TARGET/$ALLAPOT" ] && KIHAGY="$KIHAGY --exclude=./$ALLAPOT"
    done
    # shellcheck disable=SC2086
    ( cd "$HERE" && tar $KIHAGY -cf - . ) | tar -xf - -C "$TARGET" \
        || fail "$(t 'a másolás elakadt' 'the copy failed')"
    # An interpreter tarball or a wheel an older version left in the target is
    # not part of this one, and it would only take up room next to the new ones.
    for REGI in "$TARGET"/vendor/python/cpython-*.tar.gz "$TARGET"/WebPanel/vendor/wheels/*.whl; do
        [ -f "$REGI" ] || continue
        case "$REGI" in
            "$TARGET"/vendor/python/*) UJ="$HERE/vendor/python/$(basename "$REGI")" ;;
            *) UJ="$HERE/WebPanel/vendor/wheels/$(basename "$REGI")" ;;
        esac
        [ -f "$UJ" ] || rm -f "$REGI"
    done
    # The Rust accelerator of earlier versions (native/, src/rebsgo/native/) is
    # gone from the tree; left in the target it would only mislead.
    for REGI in native src/rebsgo/native; do
        [ -d "$TARGET/$REGI" ] && [ ! -d "$HERE/$REGI" ] && rm -rf "$TARGET/$REGI"
    done
    kesz "$(t 'átmásolva; a telepítés az új helyről folytatódik' 'copied; the installation carries on from the new place')"
    TOVABB="--here"
    [ "$SYSTEMD" = 0 ] && TOVABB="$TOVABB --no-systemd"
    [ "$RESTART" = 0 ] && TOVABB="$TOVABB --no-restart"
    # shellcheck disable=SC2086
    exec sh "$TARGET/install.sh" $TOVABB
fi
ROOT="$TARGET"

fazis "$(t 'Python — az értelmező' 'Python — the interpreter')"
GEP=$(uname -m)
# A Python 3.11 or newer that really starts here: one built for another
# processor (the bundled x86_64 one on an ARM machine) is executable on paper
# and fails on every call.
fut() { "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; }
PYTHON="$ROOT/runtime/python/bin/python3"
# The interpreter's version with a "t" for the free-threaded (GIL-free) build,
# in the same form as the bundled tarball's name (cpython-3.14.6t-...).
valtozat() {
    "$1" -c 'import sys, sysconfig
print("%d.%d.%d" % sys.version_info[:3] + ("t" if sysconfig.get_config_var("Py_GIL_DISABLED") else ""))' 2>/dev/null
}
gil_jel() { case "$1" in *t) t ', GIL nélkül' ', GIL-free' ;; esac; }
# The processes running from an interpreter directory right now: bsgo, or the
# panel through its venv. Removing it under them breaks their next import, and
# bsgo still saves the pilots on its way out.
hasznaljak() {
    for _exe in /proc/[0-9]*/exe; do
        _cel=$(readlink "$_exe" 2>/dev/null) || continue
        case "$_cel" in "$1"/*) _pid=${_exe#/proc/}; printf '%s ' "${_pid%/exe}" ;; esac
    done
}
# Several tarballs side by side (an update unpacked over an older tree): the newest one.
if printf '1\n' | sort -V >/dev/null 2>&1; then RENDEZ="sort -V"; else RENDEZ="sort"; fi
TARBALL=$(ls "$ROOT"/vendor/python/cpython-*.tar.gz 2>/dev/null | $RENDEZ | tail -1)
ILLIK=0
[ -n "$TARBALL" ] && case "$(basename "$TARBALL")" in *"-$GEP-"*) ILLIK=1 ;; esac
CSOMAGOLT=""
[ "$ILLIK" = 1 ] && CSOMAGOLT=$(basename "$TARBALL" | sed -n 's/^cpython-\([0-9][0-9.]*t\{0,1\}\)-.*/\1/p')
MOST=""
fut "$PYTHON" && MOST=$(valtozat "$PYTHON")
CSERE=1
# An update brings its own interpreter: one that starts but is another version
# than the bundled one (3.13 before the GIL-free 3.14t) is replaced, not kept.
if [ -n "$MOST" ] && [ -n "$CSOMAGOLT" ] && [ "$MOST" != "$CSOMAGOLT" ]; then
    mond "$(t "frissítés: a kibontott $MOST helyére a csomagolt $CSOMAGOLT kerül" "update: the bundled $CSOMAGOLT replaces the unpacked $MOST")"
    if [ "$CHECK" = 0 ]; then
        AKTIV=""
        if [ "$SYSTEMD" = 1 ] && command -v systemctl >/dev/null 2>&1 && [ "$(id -u)" = 0 ]; then
            for SZOLGALTATAS in bsgo rebsgo-panel; do
                [ "$(systemctl is-active "$SZOLGALTATAS" 2>/dev/null)" = active ] && AKTIV="$AKTIV $SZOLGALTATAS"
            done
        fi
        if [ -n "$AKTIV" ] && [ "$RESTART" = 0 ]; then
            figyel "$(t "a cseréhez le kellene állítani:$AKTIV - a --no-restart miatt marad a $MOST" "the swap would need a stop of:$AKTIV - with --no-restart the $MOST stays")"
            CSERE=0
        elif [ -n "$AKTIV" ]; then
            mond "$(t "leállítás a cseréhez:$AKTIV (a végén újraindulnak; a bent lévők kilépnek, a pilóták mentődnek)..." "stopping for the swap:$AKTIV (they start again at the end; players inside are signed out, the pilots are saved)...")"
            # shellcheck disable=SC2086
            systemctl stop $AKTIV
        fi
        FUTO=$(hasznaljak "$ROOT/runtime/python")
        FUTO=${FUTO% }
        if [ "$CSERE" = 1 ] && [ -n "$FUTO" ]; then
            figyel "$(t "még fut belőle folyamat (pid: $FUTO) - állítsd le, és futtasd újra; addig marad a $MOST" "a process still runs from it (pid: $FUTO) - stop it and run this again; until then the $MOST stays")"
            CSERE=0
        fi
    fi
fi
if [ -n "$MOST" ] && { [ "$CSERE" = 0 ] || [ -z "$CSOMAGOLT" ] || [ "$MOST" = "$CSOMAGOLT" ]; }; then
    kesz "$(t 'már ki van bontva:' 'already unpacked:') $("$PYTHON" -V 2>&1)$(gil_jel "$MOST")"
elif [ "$ILLIK" = 1 ]; then
    mond "$(t 'kibontás:' 'unpacking:') $(basename "$TARBALL")"
    if [ "$CHECK" = 0 ]; then
        # Unpacked beside the old one first: an interrupted run leaves that one whole.
        rm -rf "$ROOT/runtime/.kibontas"
        kibonto "$TARBALL" "$ROOT/runtime/.kibontas"
        fut "$ROOT/runtime/.kibontas/python/bin/python3" \
            || fail "$(t 'a kibontott értelmező nem indul' 'the unpacked interpreter does not start')"
        rm -rf "$ROOT/runtime/python"
        mv "$ROOT/runtime/.kibontas/python" "$ROOT/runtime/python"
        rm -rf "$ROOT/runtime/.kibontas"
        fut "$PYTHON" || fail "$(t 'a kibontott értelmező nem indul' 'the unpacked interpreter does not start')"
        kesz "$(t 'kész:' 'done:') $("$PYTHON" -V 2>&1)$(gil_jel "$(valtozat "$PYTHON")")"
    else
        mond "$(t '(kibontaná ide: runtime/)' '(it would unpack into runtime/)')"
    fi
else
    if [ -n "$TARBALL" ]; then
        figyel "$(t "a csomagolt értelmező másik processzorra készült, ez a gép $GEP - a rendszer python3-at használom" "the bundled interpreter was built for another processor, this machine is $GEP - using the system python3")"
    else
        figyel "$(t 'nincs csomagolt értelmező; a rendszer python3-ra váltok' 'no bundled interpreter; falling back to the system python3')"
    fi
    if [ -e "$ROOT/runtime/python" ] && [ "$CHECK" = 0 ]; then
        rm -rf "$ROOT/runtime/python"
        mond "$(t 'egy korábbi futás itt nem induló értelmezője törölve: runtime/python' "an earlier run's interpreter that does not start here was removed: runtime/python")"
    fi
    PYTHON=$(command -v python3) \
        || fail "$(t 'ezen a gépen nincs python3 - telepítsd: apt install python3 python3-venv' 'this machine has no python3 - install it: apt install python3 python3-venv')"
    fut "$PYTHON" \
        || fail "$(t "3.11 vagy újabb Python kell, ez: $("$PYTHON" -V 2>&1)" "Python 3.11 or newer is needed, this one is: $("$PYTHON" -V 2>&1)")"
    kesz "$(t 'rendszer-értelmező:' 'system interpreter:') $PYTHON, $("$PYTHON" -V 2>&1)"
fi

fazis "$(t 'Szerverfa és mappák' 'The server tree and its directories')"
[ -d "$ROOT/src/rebsgo" ] || fail "$(t 'src/rebsgo hiányzik - ez nem egy szerverfa?' 'src/rebsgo is missing - is this a server tree?')"
if [ "$CHECK" = 0 ]; then
    mkdir -p "$ROOT/logs" "$ROOT/sqlite" "$ROOT/WebPanel/logs"
fi
kesz "$(t 'mappák: logs/ sqlite/ WebPanel/logs/' 'directories: logs/ sqlite/ WebPanel/logs/')"
# GitHub's upload page and a Windows checkout both drop the execute bit, and
# systemd will not start WebPanel/run.sh without it.
if [ "$CHECK" = 0 ]; then
    chmod +x "$ROOT/install.sh" "$ROOT/uninstall.sh" "$ROOT/WebPanel/run.sh" "$ROOT"/tools/*.py 2>/dev/null
    kesz "$(t 'futtatható: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py' 'executable: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py')"
else
    mond "$(t '(futtathatóvá tenné: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py)' '(it would make these executable: install.sh, uninstall.sh, WebPanel/run.sh, tools/*.py)')"
fi

fazis "$(t 'Beállítások (.env)' 'Settings (.env)')"
if [ ! -f "$ROOT/.env" ]; then
    mond "$(t 'nincs .env - készítem a .env.example-ből, friss panel-tokennel' 'no .env - writing one from .env.example, with a fresh panel token')"
    if [ "$CHECK" = 0 ]; then
        TOKEN=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")
        [ -n "$TOKEN" ] || fail "$(t 'nem sikerült panel-tokent készíteni' 'could not make a panel token')"
        cp "$ROOT/.env.example" "$ROOT/.env" 2>/dev/null || touch "$ROOT/.env"
        printf '\nREBSGO_PANEL_TOKEN=%s\nREBSGO_NET_PANEL_DOOR_PORT=27053\n' "$TOKEN" >> "$ROOT/.env"
        chmod 600 "$ROOT/.env"
        kesz "$(t '.env elkészült, a panel-token friss; csak a tulajdonosa olvashatja' '.env written, with a fresh panel token; readable by its owner only')"
    else
        mond "$(t '(elkészítené)' '(it would write one)')"
    fi
# An interrupted earlier run can leave .env with an empty token, and the
# panel door does not open without one.
elif [ -z "$(sed -n 's/^REBSGO_PANEL_TOKEN=//p' "$ROOT/.env" | tail -1)" ]; then
    if [ "$CHECK" = 0 ]; then
        TOKEN=$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe(32))")
        [ -n "$TOKEN" ] || fail "$(t 'nem sikerült panel-tokent készíteni' 'could not make a panel token')"
        printf '\nREBSGO_PANEL_TOKEN=%s\n' "$TOKEN" >> "$ROOT/.env"
        kesz "$(t '.env már van, de panel-token nélkül - friss tokent írtam bele' '.env is there, but without a panel token - a fresh one is written into it')"
    else
        mond "$(t '(a .env-ből hiányzik a panel-token - pótolná)' '(.env has no panel token - it would add one)')"
    fi
else
    kesz "$(t '.env már van - nem nyúlok hozzá' '.env is already there - left untouched')"
fi
# At the server's own default every sector simulates at full speed even with
# nobody in it, and a small machine cannot keep up with that. A setting the
# operator made, either way, stays as it is.
if grep -qE '^(REBSGO_SECTOR_GATING_MODE|REBSGO_SECTOR_EMPTY_GATING)=.' "$ROOT/.env" 2>/dev/null; then
    kesz "$(t 'szektor-altatás: a .env saját beállítása marad' 'sector gating: the setting in .env stays')"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(bekapcsolná a szektor-altatást: REBSGO_SECTOR_GATING_MODE=idle)' '(it would switch sector gating on: REBSGO_SECTOR_GATING_MODE=idle)')"
else
    printf '\n# %s\nREBSGO_SECTOR_GATING_MODE=idle\n' \
        "empty sectors sleep, a player arriving wakes them; off = every sector simulates all the time" >> "$ROOT/.env"
    kesz "$(t 'szektor-altatás bekapcsolva: az üres szektorok alszanak (REBSGO_SECTOR_GATING_MODE=idle)' 'sector gating switched on: empty sectors sleep (REBSGO_SECTOR_GATING_MODE=idle)')"
    mond "$(t 'kikapcsolás: REBSGO_SECTOR_GATING_MODE=off a .env-ben, majd a bsgo újraindítása' 'to switch it off: REBSGO_SECTOR_GATING_MODE=off in .env, then restart bsgo')"
fi

fazis "$(t 'Gyorspróba — betölt-e a szerverkód, fut-e GIL nélkül' 'Quick check — does the server code load, does it run without the GIL')"
if [ "$CHECK" = 1 ]; then
    mond "$(t '(lefuttatná)' '(it would run this)')"
else
    # Exit code 4: the GIL is off. It is read after the imports: an extension
    # module that does not declare itself free-threading safe switches it back
    # on while loading.
    ( cd "$ROOT" && PYTHONPATH="$ROOT/src" "$PYTHON" -c '
import sys
import rebsgo.main  # import binds no ports; a broken tree fails right here
raise SystemExit(0 if getattr(sys, "_is_gil_enabled", lambda: True)() else 4)
' )
    RC=$?
    case "$RC" in
        0|4) kesz "$(t 'a szerver kódja betölt' 'the server code loads')" ;;
        *) fail "$(t 'a szerver kódja nem tölt be - hiányos vagy sérült fa?' 'the server code does not load - an incomplete or damaged tree?')" ;;
    esac
    case "$RC" in
        4) kesz "$(t 'GIL: kikapcsolva - a szektorok szálai párhuzamosan, több magon futnak' 'GIL: off - the sector threads run in parallel, on several cores')" ;;
        *) mond "$(t 'GIL: bekapcsolva - a szerver összesen kb. egy magot használ' 'GIL: on - the server uses about one core in all')" ;;
    esac
fi

fazis "$(t 'Launcher — az exe és a fájllista útvonalai' 'Launcher — the exe and the file-list paths')"
if [ -f "$ROOT/launcher/rebsgo-launcher.exe" ]; then
    kesz "$(t 'launcher/rebsgo-launcher.exe - ezt kapják a játékosok' 'launcher/rebsgo-launcher.exe - this is what the players get')"
else
    figyel "$(t 'nincs launcher/rebsgo-launcher.exe ebben a fában' 'there is no launcher/rebsgo-launcher.exe in this tree')"
fi
kulcs() { sed -n "s/^$1=//p" "$ROOT/.env" 2>/dev/null | tail -1; }
for NEV in REBSGO_LAUNCHER_MANIFEST_DIR REBSGO_LAUNCHER_CLIENT_DIR; do
    ERTEK=$(kulcs "$NEV")
    [ -n "$ERTEK" ] || continue
    case "$ERTEK" in /*) UT="$ERTEK" ;; *) UT="$ROOT/$ERTEK" ;; esac
    if [ -d "$UT" ]; then
        kesz "$NEV: $(t 'megvan' 'present')"
    else
        figyel "$(t "$NEV a .env-ben erre mutat, de nincs meg:" "$NEV in .env points here, but it does not exist:") $ERTEK"
        figyel "$(t '  (generálás: tools/gen_launcher_manifests.py; kulcs nélkül nincs fájllista)' '  (generate it with tools/gen_launcher_manifests.py; without the keys there is no file list)')"
    fi
done

fazis "$(t 'Webpanel — venv a csomagolt wheel-ekből' 'WebPanel — a venv from the bundled wheels')"
VENV="$ROOT/WebPanel/venv"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
    kesz "$(t 'a venv már fel van építve' 'the venv is already built')"
elif [ "$CHECK" = 0 ]; then
    rm -rf "$VENV"
    DARAB=$(ls "$ROOT"/WebPanel/vendor/wheels/*.whl 2>/dev/null | wc -l)
    mond "$(t "venv létrehozása, majd a panel csomagjai: elsőként a hozott $DARAB wheel, hálózat nélkül" "creating the venv, then the panel's packages: the $DARAB bundled wheels first, with no network")"
    "$PYTHON" -m venv "$VENV" \
        || fail "$(t 'a venv létrehozása nem sikerült (Debianon, Ubuntun: apt install python3-venv)' 'the venv could not be created (on Debian, Ubuntu: apt install python3-venv)')"
    # The bundled wheels are built for x86_64 and Python 3.13. Anywhere else,
    # whatever does not fit comes from PyPI.
    if "$VENV/bin/pip" install --quiet --disable-pip-version-check --no-index \
            --find-links "$ROOT/WebPanel/vendor/wheels" \
            -r "$ROOT/WebPanel/requirements.txt" 2>/dev/null; then
        kesz "$(t 'a panel venv-je kész' "the panel's venv is ready")"
    else
        figyel "$(t "a hozott wheel-ek nem mind illenek ehhez a géphez ($GEP) - a többit a PyPI-ról töltöm le" "not all bundled wheels fit this machine ($GEP) - fetching the rest from PyPI")"
        mond "$(t 'ami fordítást kíván, az lassabb gépen percekig is eltarthat' 'whatever needs compiling can take minutes on a slower machine')"
        # What PyPI has no wheel for on this machine (psutil on 32-bit ARM) is
        # compiled here. pip's long output goes to a log; only its tail is shown.
        NAPLO="$ROOT/logs/panel-pip.log"
        : > "$NAPLO"
        pip_pypi() {
            "$VENV/bin/pip" install --disable-pip-version-check \
                --find-links "$ROOT/WebPanel/vendor/wheels" \
                -r "$ROOT/WebPanel/requirements.txt" >>"$NAPLO" 2>&1
        }
        pip_hiba() {
            tail -n 15 "$NAPLO" >&2
            fail "$(t "$1 - a teljes napló: $NAPLO" "$2 - the full log: $NAPLO")"
        }
        if ! pip_pypi; then
            # Compiling needs the Python headers and the C compiler Python was built with.
            HIANY=$("$PYTHON" -c 'import os, shutil, sysconfig
h = []
if not os.path.isfile(os.path.join(sysconfig.get_paths()["include"], "Python.h")): h.append("python3-dev")
if not shutil.which((os.environ.get("CC") or sysconfig.get_config_var("CC") or "cc").split()[0]): h.append("gcc")
print(" ".join(h))')
            # Only a failed build is the tools' fault; anything else (the network) is shown as it is.
            [ -n "$HIANY" ] && grep -qE 'Failed building wheel|Failed to build|Could not build wheels' "$NAPLO" \
                || pip_hiba 'a panel csomagjai nem települtek (van hálózat?)' "the panel's packages did not install (is there a network?)"
            CSOMAG=$(sed -n 's/.*Failed building wheel for \([A-Za-z0-9_.-]*\).*/\1/p' "$NAPLO" | sort -u | paste -sd ' ' -)
            figyel "$(t "${CSOMAG:-egy csomag}: erre a gépre nincs kész wheel, helyben kell fordítani - ehhez hiányzik: $HIANY" "${CSOMAG:-a package}: there is no ready wheel for this machine, it has to be compiled here - missing for that: $HIANY")"
            [ "$(id -u)" = 0 ] && command -v apt-get >/dev/null 2>&1 \
                || fail "$(t "telepítsd rootként (Debianon: apt install $HIANY)" "install it as root (on Debian: apt install $HIANY)")"
            mond "$(t "telepítés: apt-get install $HIANY" "installing: apt-get install $HIANY")"
            apt_tesz() {
                DEBIAN_FRONTEND=noninteractive apt-get install -y -q -o DPkg::Lock::Timeout=300 "$@" >>"$NAPLO" 2>&1
            }
            # shellcheck disable=SC2086
            apt_tesz $HIANY || { apt-get update -q >>"$NAPLO" 2>&1 && apt_tesz $HIANY; } \
                || pip_hiba "az apt-get install $HIANY nem sikerült" "apt-get install $HIANY failed"
            kesz "$(t "felkerült: $HIANY" "installed: $HIANY")"
            mond "$(t 'fordítás és telepítés' 'compiling and installing')"
            pip_pypi || pip_hiba 'a panel csomagjai nem települtek' "the panel's packages did not install"
        fi
        kesz "$(t 'a panel venv-je kész' "the panel's venv is ready")"
    fi
else
    mond "$(t '(felépítené a WebPanel/vendor/wheels tartalmából)' '(it would build one from WebPanel/vendor/wheels)')"
fi
# Left to the panel, panel.env is written on its first start - after run.sh has
# already read it and found nothing.
PANEL_ENV="$ROOT/WebPanel/panel.env"
if [ -f "$PANEL_ENV" ]; then
    kesz "$(t 'WebPanel/panel.env már van - nem nyúlok hozzá' 'WebPanel/panel.env is already there - left untouched')"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(elkészítené a WebPanel/panel.env-et: a panel minden hálózati címen elérhető lenne)' '(it would write WebPanel/panel.env: the panel would be reachable on every network address)')"
elif ( cd "$ROOT/WebPanel" && REBSGO_LANG="$NYELV" "$VENV/bin/python" -c 'from panel import settings; settings.raw()' ) \
        && [ -f "$PANEL_ENV" ]; then
    chmod 600 "$PANEL_ENV"
    kesz "$(t 'WebPanel/panel.env elkészült: a panel minden hálózati címen elérhető (PANEL_HOST=0.0.0.0)' 'WebPanel/panel.env written: the panel is reachable on every network address (PANEL_HOST=0.0.0.0)')"
else
    figyel "$(t 'a WebPanel/panel.env nem készült el - az első indításkor a panel maga írja meg' 'WebPanel/panel.env was not written - the panel writes it on its first start')"
fi

fazis "$(t 'Első admin fiók — a WebPanelhez és a fejlesztői jogokhoz' 'The first admin account — for the WebPanel and the developer rights')"
PILOTAK="$ROOT/tools/pilots.py"
POTLAS="\"$PYTHON\" \"$PILOTAK\" create <$(t 'név' 'name')> --grant Developer,Console"
if [ "$CHECK" = 1 ]; then
    ADMIN="$(t '(ellenőrző módban nem néztem meg)' '(not looked at in check mode)')"
    mond "$(t '(ha még nincs Developer szerepű fiók, felajánlaná, hogy most létrehozza)' '(if no account has the Developer role yet, it would offer to make one now)')"
elif "$PYTHON" "$PILOTAK" admins >/dev/null 2>&1; then
    ADMIN="$(t 'már van - a listájuk:' 'already there - to list them:') \"$PYTHON\" \"$PILOTAK\" admins"
    kesz "$(t 'van már Developer szerepű fiók - nem kérdezek' 'an account with the Developer role is already there - no question asked')"
elif [ -t 0 ]; then
    ADMIN="$(t 'még nincs - később:' 'none yet - later:') $POTLAS"
    mond "$(t 'A WebPanelbe csak Developer vagy Console szereppel lehet belépni, fiókot pedig csak' 'Only a Developer or a Console gets into the WebPanel, and only a Developer can make')"
    mond "$(t 'Developer hozhat létre. Ez az első fiók mindkettőt megkapja, és a játékba is ezzel' 'accounts there. This first account gets both, and it signs in to the game as well.')"
    mond "$(t 'lehet belépni. A jelszó legalább 5 karakter. Enter = kihagyás.' 'The password is at least 5 characters. Enter = skip.')"
    PROBA=0
    LETREJOTT=0
    while [ "$PROBA" -lt 3 ]; do
        printf '    %s: ' "$(t 'pilótanév' 'pilot name')"
        read -r NEV || NEV=""
        [ -n "$NEV" ] || break
        if "$PYTHON" "$PILOTAK" create "$NEV" --grant Developer,Console; then
            ADMIN="$NEV (Developer, Console)"
            LETREJOTT=1
            kesz "$(t "kész: $NEV - ezzel lehet belépni a WebPanelbe és a játékba" "done: $NEV - this one signs in to the WebPanel and the game")"
            break
        fi
        PROBA=$((PROBA + 1))
    done
    [ "$LETREJOTT" = 1 ] || figyel "$(t 'nem készült admin fiók - később:' 'no admin account was made - later:') $POTLAS"
else
    ADMIN="$(t 'még nincs - később:' 'none yet - later:') $POTLAS"
    figyel "$(t 'nincs admin fiók, és terminál sincs, hogy megkérdezzem' 'there is no admin account, and no terminal to ask about one')"
    mond "$(t 'később:' 'later:') $POTLAS"
fi

fazis "$(t 'Szolgáltatások — telepítés és indítás' 'Services — installing and starting')"
if [ "$SYSTEMD" = 0 ]; then
    figyel "$(t 'kihagyva kérésre (--no-systemd)' 'skipped on request (--no-systemd)')"
    mond "$(t 'kézi indítás:' 'start by hand:')  cd $ROOT && PYTHONPATH=src $PYTHON -m rebsgo.main"
    mond "$(t 'panel kézzel:' 'panel by hand:')  $ROOT/WebPanel/run.sh"
elif ! command -v systemctl >/dev/null 2>&1; then
    figyel "$(t 'ezen a gépen nincs systemctl - kihagyva' 'this machine has no systemctl - skipped')"
    mond "$(t 'kézi indítás:' 'start by hand:')  cd $ROOT && PYTHONPATH=src $PYTHON -m rebsgo.main"
elif [ "$(id -u)" != 0 ]; then
    figyel "$(t 'nem rootként fut - a szolgáltatás-telepítés kimaradt' 'not running as root - the service installation was skipped')"
    mond "$(t 'rootként újrafuttatva a bsgo és a rebsgo-panel is felkerül és elindul' 'run again as root and both bsgo and rebsgo-panel are installed and started')"
elif [ "$CHECK" = 1 ]; then
    mond "$(t '(telepítené, engedélyezné és elindítaná: bsgo, rebsgo-panel)' '(it would install, enable and start: bsgo, rebsgo-panel)')"
else
    # REBSGO_SYSTEMD_DIR: only for trying the installer out without touching the real units.
    UNIT_DIR=${REBSGO_SYSTEMD_DIR:-/etc/systemd/system}
    sed -e "s|__ROOT__|$ROOT|g" -e "s|__PYTHON__|$PYTHON|g" -e "s|__LANG__|$NYELV|g" \
        "$ROOT/deploy/bsgo.service.template" > "$UNIT_DIR/bsgo.service"
    sed -e "s|__PANEL_DIR__|$ROOT/WebPanel|g" -e "s|__LANG__|$NYELV|g" \
        "$ROOT/WebPanel/deploy/rebsgo-panel.service" > "$UNIT_DIR/rebsgo-panel.service"
    # The October 2026 GIL-free package (telepit.sh) pointed bsgo at
    # runtime/python314t with this drop-in. Once runtime/python is the GIL-free
    # interpreter itself, the override goes, and bsgo starts like a fresh install.
    REGI_DROPIN="$UNIT_DIR/bsgo.service.d/20-python314t.conf"
    if [ -f "$REGI_DROPIN" ] && grep -q 'runtime/python314t' "$REGI_DROPIN" \
            && case "$(valtozat "$PYTHON")" in *t) true ;; *) false ;; esac; then
        rm -f "$REGI_DROPIN"
        rmdir "$UNIT_DIR/bsgo.service.d" 2>/dev/null
        kesz "$(t 'a korábbi GIL nélküli kiegészítő (20-python314t.conf) törölve: a bsgo a runtime/python-ból indul' 'the earlier GIL-free drop-in (20-python314t.conf) removed: bsgo starts from runtime/python')"
    fi
    systemctl daemon-reload
    systemctl enable bsgo rebsgo-panel >/dev/null 2>&1
    kesz "$(t 'unitok a helyükön, mindkettő engedélyezve (újraindulás után is felállnak)' 'both units are in place and enabled (they come up after a reboot too)')"
    MAR_FUTOTT=""
    for SZOLGALTATAS in bsgo rebsgo-panel; do
        [ "$(systemctl is-active "$SZOLGALTATAS")" = active ] && MAR_FUTOTT="$MAR_FUTOTT $SZOLGALTATAS"
    done
    # An update only takes over once the services restart; stopping bsgo
    # signs the players out, and on the way out it saves the pilots.
    if [ -n "$MAR_FUTOTT" ] && [ "$RESTART" = 1 ]; then
        mond "$(t "újraindítás, hogy a frissítés életbe lépjen:$MAR_FUTOTT (a bent lévők kilépnek, a pilóták mentődnek)..." "restarting so the update takes over:$MAR_FUTOTT (players inside are signed out, the pilots are saved)...")"
        # shellcheck disable=SC2086
        systemctl restart $MAR_FUTOTT
    else
        mond "$(t 'indítás...' 'starting...')"
    fi
    systemctl start bsgo rebsgo-panel
    sleep 3
    for SZOLGALTATAS in bsgo rebsgo-panel; do
        if [ "$(systemctl is-active "$SZOLGALTATAS")" = active ]; then
            kesz "$SZOLGALTATAS: $(t 'fut' 'running')"
        else
            figyel "$(t "$SZOLGALTATAS nem indult el - napló: journalctl -u $SZOLGALTATAS -e" "$SZOLGALTATAS did not start - log: journalctl -u $SZOLGALTATAS -e")"
        fi
    done
    if [ -n "$MAR_FUTOTT" ] && [ "$RESTART" = 0 ]; then
        figyel "$(t "már előtte is futott:$MAR_FUTOTT - kérésre nem indítottam újra (--no-restart); a frissítés az újraindítás után él" "already running before:$MAR_FUTOTT - not restarted on request (--no-restart); the update takes over after a restart")"
        mond "systemctl restart$MAR_FUTOTT"
        mond "$(t '(a bsgo leállása kilépteti a játékosokat, a pilótákat elmenti)' '(stopping bsgo signs the players out, and saves the pilots)')"
    fi
    # What the old drop-in ran is unused once bsgo restarted from runtime/python.
    if [ -d "$ROOT/runtime/python314t" ] && [ ! -f "$REGI_DROPIN" ]; then
        FUTO=$(hasznaljak "$ROOT/runtime/python314t")
        FUTO=${FUTO% }
        if [ -n "$FUTO" ]; then
            figyel "$(t "a runtime/python314t-ből még fut folyamat (pid: $FUTO) - újraindítás után törölhető" "a process still runs from runtime/python314t (pid: $FUTO) - it can go after a restart")"
        else
            rm -rf "$ROOT/runtime/python314t"
            kesz "$(t 'a korábbi runtime/python314t törölve (a runtime/python ugyanez az értelmező)' 'the earlier runtime/python314t removed (runtime/python is that same interpreter)')"
        fi
    fi
fi

printf '\n%s%s✔ %s%s\n' "$VASTAG" "$ZOLD" "$(t 'Kész.' 'Done.')" "$VEGE"
mond "$(t 'szerver:         ' 'server:          ')$ROOT"
mond "$(t 'beléptető ajtó:  http://<ez-a-gép>:27051/   (a launcher ide csatlakozik)' 'admission door:  http://<this-machine>:27051/   (the launcher connects here)')"
mond "$(t 'launcher:        ' 'launcher:        ')$ROOT/launcher/rebsgo-launcher.exe"
mond "$(t 'webpanel:        http://<ez-a-gép>:27055/   (minden hálózati címen; csak helyi eléréshez' 'webpanel:        http://<this-machine>:27055/   (on every network address; for local-only access')"
mond "$(t '                 PANEL_HOST=127.0.0.1 a WebPanel/panel.env-ben; nyilvánosan TLS-proxy mögé)' '                 PANEL_HOST=127.0.0.1 in WebPanel/panel.env; publicly, behind a TLS proxy)')"
mond "$(t 'beállítások:     ' 'settings:        ')$ROOT/.env"
mond "$(t 'admin fiók:      ' 'admin account:   ')$ADMIN"
mond "$(t 'eltávolítás:     ' 'uninstall:       ')sh $ROOT/uninstall.sh"
exit 0
