"""Discovery and platform glue for the launcher.

No side effects on import: callers build a Context via build_context().
"""
from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

from slpp import slpp


def host_cmd_prefix():
    """Prefix to run a host binary from inside a distrobox/toolbox container.

    The engine/AppImage needs host-side FUSE + GPU userspace, so when we're
    containerized we run it on the host. Empty list when running natively.
    """
    if os.path.exists("/run/.containerenv") or os.environ.get("CONTAINER_ID"):
        for tool in ("distrobox-host-exec", "host-spawn"):
            path = shutil.which(tool)
            if path:
                if tool == "distrobox-host-exec" and not shutil.which("host-spawn"):
                    # distrobox-host-exec is a shim over host-spawn; when that's
                    # missing it stops on an interactive "install host-spawn?
                    # [Y/n]" prompt on *our* stdin -- from the GUI that's a
                    # launch that silently never happens. Say so.
                    print("warning: host-spawn is not installed in this container; "
                          "distrobox-host-exec will prompt to install it on this terminal "
                          "(or run `distrobox-host-exec -Y true` once).", file=sys.stderr)
                return [path]
    return []


def check_host_bridge(prefix: list[str], timeout: float = 15.0) -> Optional[str]:
    """Verify the container->host bridge works before we bet a launch on it.

    Returns None if `prefix` is empty or `prefix + [/bin/true]` succeeds; else a
    human explanation. The bridge (distrobox-host-exec -> host-spawn) is a call
    to org.freedesktop.Flatpak.Development.HostCommand on the host's session
    bus, i.e. it needs flatpak's session helper on the host -- a dependency
    that has nothing to do with the engine and fails as a bare exit 127.
    """
    if not prefix:
        return None
    try:
        r = subprocess.run(prefix + ["/bin/true"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return (f"{os.path.basename(prefix[0])} did not answer within {timeout:.0f}s "
                "(is it waiting on a prompt in the terminal, e.g. to install host-spawn?)")
    except OSError as e:
        return f"could not run {prefix[0]}: {e}"
    if r.returncode == 0:
        return None
    detail = (r.stderr or r.stdout).strip().splitlines()
    why = f": {detail[-1]}" if detail else ""
    return (f"container->host bridge failed (exit {r.returncode}{why}). "
            "distrobox-host-exec/host-spawn need flatpak's session helper on the HOST "
            "(install flatpak there), or run the launcher outside the container so it "
            "execs the engine directly.")


def explain_exit(rc: int, argv: list[str]) -> Optional[str]:
    """Human hint for a launch child's exit code, or None if nothing to add.

    127 is the shared signature of "could not exec": host-spawn uses it when
    the host side fails to spawn (no flatpak session helper on the host, path
    missing on the host), and ld.so uses it when the binary loads but a shared
    library is missing (an engine built against container libs, run on the
    host). Both look identical from inside the container, so hand over the
    one-liners that tell them apart.
    """
    if rc != 127 or not argv:
        return None
    if os.path.basename(argv[0]) in ("distrobox-host-exec", "host-spawn") and len(argv) > 1:
        binary = shlex.quote(argv[1])
        return (
            "exit 127 came back through the host bridge: either the bridge failed or the engine "
            "can't be exec'd on the host. From inside the container:\n"
            "  distrobox-host-exec /bin/echo host-ok           # bridge works? (needs flatpak's session helper on the host)\n"
            f"  distrobox-host-exec ls -L {binary}   # symlink target exists on the host?\n"
            f"  distrobox-host-exec ldd {binary} | grep -i 'not found'   # loadable on the host?"
        )
    return (f"exit 127: could not exec {argv[0]!r} -- missing file, missing ELF interpreter, "
            "or a shared library not found (try: ldd on it)")


# ---------------------------------------------------------------------------
# Platform-specific constants.
# ---------------------------------------------------------------------------

if platform.system() == "Windows":
    engine_binary = "spring.exe"
    prd_binary = "pr-downloader.exe"
    default_datafolder = "data"
    default_launcher_binary = "Beyond-All-Reason.exe"
    launcher_binary_display = "Beyond-All-Reason.exe"
    engine_download_baseurl = "https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_windows-64-minimal-portable.7z"
    engine_download_baseurl_new = "https://github.com/beyond-all-reason/spring/releases/download/{enginebaseversion}/spring_bar_.{releaseID}.{enginebaseversion}_windows-64-minimal-portable.7z"
    engine_download_baseurl_newest = "https://github.com/beyond-all-reason/RecoilEngine/releases/download/{enginebaseversion}/recoil_{enginebaseversion}_amd64-windows.7z"
elif platform.system() == "Linux":
    engine_binary = "spring"
    prd_binary = "pr-downloader"
    default_datafolder = None  # resolved per-Context via find_linux_datadir()
    default_launcher_binary = None  # resolved per-Context via find_linux_launcher_binary()
    launcher_binary_display = "Beyond-All-Reason AppImage"
    engine_download_baseurl = "https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_linux-64-minimal-portable.7z"
    engine_download_baseurl_new = "https://github.com/beyond-all-reason/spring/releases/download/{enginebaseversion}/spring_bar_.{releaseID}.{enginebaseversion}_linux-64-minimal-portable.7z"
    engine_download_baseurl_newest = "https://github.com/beyond-all-reason/RecoilEngine/releases/download/{enginebaseversion}/recoil_{enginebaseversion}_amd64-linux.7z"
else:
    raise Exception("Unsupported platform")


# ---------------------------------------------------------------------------
# Linux discovery helpers.
# ---------------------------------------------------------------------------

def find_linux_datadir() -> str:
    try:
        documents = subprocess.check_output(
            ["xdg-user-dir", "DOCUMENTS"], encoding="utf-8"
        ).strip()
    except Exception:
        documents = os.path.expanduser("~")
    if os.path.exists(os.path.join(documents, "Beyond All Reason")):
        return os.path.join(documents, "Beyond All Reason")

    state_home = os.getenv(
        "XDG_STATE_HOME",
        default=os.path.join(os.path.expanduser("~"), ".local", "state"),
    )
    return os.path.join(state_home, "Beyond All Reason")


# Order:
#   1. $BAR_APPIMAGE_PATH if set and pointing at an existing file
#   2. Scan barinstallpath, then cwd, for an AppImage matching the regex
#   3. Fallback string so the GUI still has *something* to display
_APPIMAGE_RE = re.compile(r"^beyond[-_]?all[-_]?reason.*\.appimage$", re.IGNORECASE)


def find_linux_launcher_binary(barinstallpath: Optional[str] = None) -> str:
    # Resolution order:
    #   1. $BAR_APPIMAGE_PATH if it points at an existing AppImage *file*.
    #   2. $BAR_APPIMAGE_PATH if it points at a *directory* containing one --
    #      this lets users set BAR_APPIMAGE_PATH=~/Applications/ or =~/apps/BAR/
    #      without having to know the AppImage's exact filename, which churns
    #      with each release.
    #   3. barinstallpath / cwd scan, for the standalone "drop the launcher
    #      next to the AppImage and double-click" workflow. The explicitly
    #      configured install path outranks cwd so a stray AppImage in
    #      whatever directory the CLI happens to run from can't shadow it.
    candidates = []
    env_path = os.environ.get("BAR_APPIMAGE_PATH")
    if env_path:
        expanded = os.path.expanduser(env_path)
        if os.path.isfile(expanded):
            return expanded
        if os.path.isdir(expanded):
            candidates.append(expanded)

    if barinstallpath:
        candidates.append(barinstallpath)
    candidates.append(os.getcwd())
    for d in candidates:
        if not os.path.isdir(d):
            continue
        for name in reversed(sorted(os.listdir(d))):
            if _APPIMAGE_RE.match(name):
                return os.path.join(d, name)
    return "Beyond-All-Reason.AppImage"


# ---------------------------------------------------------------------------
# Engine + cache discovery (returns dicts, no global state).
# ---------------------------------------------------------------------------

def findengines(enginefolder: str) -> dict[str, str]:
    engines: dict[str, str] = {}
    if os.path.exists(enginefolder):
        for engineversion in os.listdir(enginefolder):
            enginedir = os.path.join(enginefolder, engineversion)
            enginepath = os.path.join(enginedir, engine_binary)
            if os.path.isdir(enginedir) and os.path.exists(enginepath):
                print(f"Found engine version {engineversion} in path: {enginepath}")
                engines[engineversion] = enginepath
    if not engines:
        engines["NO ENGINES FOUND!"] = "NO ENGINES FOUND!"
    return engines


def parsecache(path: str) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    maps: dict[str, str] = {}
    games: dict[str, str] = {}
    menus: dict[str, str] = {}
    try:
        cachefiles: list[tuple[str, float]] = []
        if not os.path.isdir(path):
            return maps, games, menus
        for item in os.listdir(path):
            itempath = os.path.join(path, item)
            if os.path.isdir(itempath):
                for archivecachefile in os.listdir(itempath):
                    if (
                        "archivecache" in archivecachefile.lower()
                        and archivecachefile.lower().endswith(".lua")
                    ):
                        archivecachefilepath = os.path.join(itempath, archivecachefile)
                        lastmodified = os.path.getmtime(archivecachefilepath)
                        print("Found a cache file", item, archivecachefile, "last modified:", lastmodified)
                        cachefiles.append((archivecachefilepath, lastmodified))
            elif "archivecache" in item.lower() and item.lower().endswith(".lua"):
                lastmodified = os.path.getmtime(itempath)
                print("Found a cache file (direct)", item, "last modified:", lastmodified)
                cachefiles.append((itempath, lastmodified))

        if cachefiles:
            cachefiles.sort(key=lambda x: x[1], reverse=True)
            archivecachefilepath = cachefiles[0][0]
            print("Loading Archive Cache File:", archivecachefilepath)
            archivecachecontents = open(archivecachefilepath).read()
            archivetable = "{" + archivecachecontents.partition("{")[2].rpartition("}")[0] + "}"
            archivetable = slpp.decode(archivetable)
            for archive in archivetable["archives"]:
                if "archivedata" in archive and "modtype" in archive["archivedata"]:
                    archivedata = archive["archivedata"]
                    modtype = archivedata["modtype"]
                    if modtype == 3:
                        maps[archivedata["name"]] = archive["name"]
                    elif modtype == 5:
                        menus[archivedata["name"]] = archive["name"]
                    elif modtype == 1:
                        games[archivedata["name"]] = archive["name"]
            print(f"Found {len(maps)} maps, {len(games)} games, {len(menus)} menus")
    except Exception as e:
        print("parsecache error, dont code blind!", e)
    return maps, games, menus


def parsemodinfo(path: str) -> Optional[dict]:
    try:
        with open(path, "r") as f:
            contents = f.read()
        table_str = "{" + contents.partition("{")[2].rpartition("}")[0] + "}"
        return slpp.decode(table_str)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        return None


# ---------------------------------------------------------------------------
# Context: the resolved state used by both the GUI and the CLI.
# ---------------------------------------------------------------------------

@dataclass
class Context:
    barinstallpath: str
    datafolder: str
    launcher_binary: str
    engines: dict[str, str] = field(default_factory=dict)
    maps: dict[str, str] = field(default_factory=dict)
    games: dict[str, str] = field(default_factory=dict)
    menus: dict[str, str] = field(default_factory=dict)
    modinfos: dict[str, dict] = field(default_factory=dict)


def build_context(
    barinstallpath: Optional[str] = None,
    datafolder: Optional[str] = None,
    launcher_binary: Optional[str] = None,
) -> Context:
    """Build a fresh Context by scanning the BAR install for cache, engines, and games."""
    if barinstallpath is None:
        barinstallpath = os.path.abspath(os.path.dirname(sys.argv[0]))

    if datafolder is None:
        datafolder = default_datafolder or find_linux_datadir()

    if launcher_binary is None:
        launcher_binary = default_launcher_binary or find_linux_launcher_binary(barinstallpath)

    ctx = Context(
        barinstallpath=barinstallpath,
        datafolder=datafolder,
        launcher_binary=launcher_binary,
    )

    ctx.maps, ctx.games, ctx.menus = parsecache(os.path.join(barinstallpath, datafolder, "cache"))
    ctx.engines = findengines(os.path.join(barinstallpath, datafolder, "engine"))

    modinfos: dict[str, dict] = {}
    modinfos["Spring-launcher with rapid://byar-chobby:test"] = {"modtype": "0", "name": "rapid://byar-chobby:test"}
    modinfos["Latest BYAR Chobby Lobby: rapid://byar-chobby:test"] = {"name": "rapid://byar-chobby:test", "version": "", "modtype": "5"}
    modinfos["Latest BAR Game: rapid://byar:test"] = {"name": "rapid://byar:test", "version": "", "modtype": "1"}

    for menuname in ctx.menus.keys():
        if "$VERSION" in menuname:
            modinfos[f"Spring-launcher with {menuname}"] = {"modtype": "0", "name": menuname}
            modinfos[f"{menuname} (no launcher)"] = {"modtype": "5", "name": menuname}
    for gamename in ctx.games.keys():
        if "$VERSION" in gamename:
            modinfos[gamename] = {"modtype": "1", "name": gamename}

    gamespath = os.path.join(barinstallpath, datafolder, "games")
    if os.path.exists(gamespath):
        for gamedir in os.listdir(gamespath):
            gamepath = os.path.join(gamespath, gamedir)
            if not os.path.isdir(gamepath):
                continue
            modinfopath = os.path.join(gamepath, "modinfo.lua")
            if not os.path.exists(modinfopath):
                continue
            modinfo = parsemodinfo(modinfopath)
            if not (modinfo and "name" in modinfo):
                continue
            base_name = modinfo["name"]
            version = modinfo.get("version", "")
            if version == "$VERSION" and "$VERSION" not in base_name:
                name = f"{base_name} $VERSION"
            else:
                name = base_name
            mtype = str(modinfo.get("modtype", "1"))
            display_name = f"[LOCAL] {gamedir}"
            modinfos[display_name] = {"modtype": mtype, "name": name}
            if mtype == "5":
                modinfos[f"[LOCAL] Spring-launcher with {gamedir}"] = {"modtype": "0", "name": name}

    ctx.modinfos = modinfos
    for k, v in modinfos.items():
        print(k, v)

    return ctx
