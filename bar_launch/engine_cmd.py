"""Pure command-string construction. Shared by GUI gencmd and CLI."""
from __future__ import annotations

import json
import os
import platform
import shlex
from typing import Optional

from .core import Context


def q(arg: str) -> str:
    """Quote one argv element for the command string.

    The string is consumed via shlex.split(), so either quoting style parses;
    what matters is what happens when a user copies it from the GUI panel or
    --print-cmd into a shell. POSIX shells (and PowerShell) expand $VERSION
    inside double quotes, turning --menu "BYAR Chobby $VERSION" into
    "BYAR Chobby " and producing an unhelpful "Dependent archive ... not
    found" from the engine -- while the very same string worked from the
    launcher, which never goes through a shell. shlex.quote single-quotes on
    POSIX so the pasted command matches what the launcher runs. cmd.exe has
    no single quotes, so Windows keeps double quotes.
    """
    if platform.system() == "Windows":
        return f'"{arg}"'
    return shlex.quote(arg)


def argv_of(cmd: str) -> list[str]:
    """Inverse of build_runcmd's string encoding: the argv Popen will get."""
    return shlex.split(cmd)

SCRIPT_BASE = """
[game]
{
    [allyteam1]
    {
        numallies=0;
    }
    [team1]
    {
        teamleader=0;
        allyteam=1;
    }
    [ai0]
    {
        shortname=NullAI;
        name=NullAI;
        version=0.1;
        team=1;
        host=0;
    }
    [modoptions]
    {
        %s
    }
    [allyteam0]
    {
        numallies=0;
    }
    [team0]
    {
        teamleader=0;
        allyteam=0;
    }
    [player0]
    {
        team=0;
        name=DebugLauncher;
    }
    mapname=%s;
    myplayername=DebugLauncher;
    ishost=1;
    gametype=%s;
    nohelperais=0;
}"""


def write_start_script(modopts: str, mapname: str, gamename: str, path: str = "bar_debug_launcher_script.txt") -> str:
    """Write the engine start script. Returns the path written."""
    script = SCRIPT_BASE % (modopts, mapname, gamename)
    with open(path, "w") as f:
        f.write(script)
    print("Generated script:", script)
    return path


def write_dev_lobby_config(
    engine_version: str,
    mod_name: str,
    path: str = "bar_debug_launcher_config.json",
) -> str:
    """Write the spring-launcher dev-lobby config. Returns the path written."""
    config = {
        "title": "Beyond All Reason",
        "setups": [
            {
                "package": {"id": "dev-lobby", "display": "Dev Lobby"},
                "downloads": {"engines": [engine_version]},
                "no_start_script": True,
                "no_downloads": True,
                "auto_start": True,
                "launch": {"start_args": ["--menu", mod_name]},
            }
        ],
    }
    with open(path, "w") as f:
        json.dump(config, f, indent=4)
    return path


def build_runcmd(
    ctx: Context,
    modinfo: dict,
    engine_version: str,
    mapname: Optional[str] = None,
    modopts: str = "",
    script_path: str = "bar_debug_launcher_script.txt",
    config_path: str = "bar_debug_launcher_config.json",
) -> str:
    """Build the engine command string for a given (modinfo, engine, map) triple.

    `engine_version` is a key into ctx.engines (e.g. "recoil_2025.06.19" or
    "105.1.1-941-g941148f bar"). Returns the shell command string; the caller
    is responsible for executing or printing it.
    """
    write_dir = os.path.join(ctx.barinstallpath, ctx.datafolder)
    enginepath = ctx.engines.get(engine_version)
    if enginepath is None:
        raise KeyError(f"engine {engine_version!r} not in ctx.engines")

    # Anchor relative side-effect files under barinstallpath so the file we
    # write is the same file the command references. (The GUI chdirs to
    # barinstallpath, so this is a no-op there; the headless CLI never chdirs,
    # and previously wrote the config to cwd while pointing the launcher at a
    # nonexistent/stale barinstallpath copy.)
    if not os.path.isabs(script_path):
        script_path = os.path.join(ctx.barinstallpath, script_path)
    if not os.path.isabs(config_path):
        config_path = os.path.join(ctx.barinstallpath, config_path)

    mtype = modinfo["modtype"]
    if mtype == "5":
        return f'{q(enginepath)} --isolation --write-dir {q(write_dir)} --menu {q(modinfo["name"])}'
    if mtype == "1":
        if mapname and mapname != "Ill choose my own once ingame":
            write_start_script(modopts, mapname, modinfo["name"], script_path)
            return f'{q(enginepath)} --isolation --write-dir {q(write_dir)} {q(script_path)}'
        return f'{q(enginepath)} --isolation --write-dir {q(write_dir)}'
    if mtype == "0":
        write_dev_lobby_config(engine_version, modinfo["name"], config_path)
        return f'{q(os.path.join(ctx.barinstallpath, ctx.launcher_binary))} -c {q(config_path)}'
    raise ValueError(f"unknown modtype {mtype!r}")


def missing_binary_message(cmd: str, modinfo: dict) -> Optional[str]:
    """Explain a guaranteed launch failure up front, or None if the binary exists.

    Both the AppImage launcher and the engine are addressed by absolute path,
    so a missing file means Popen (or distrobox-host-exec) would only produce
    a traceback / "command not found" in whatever terminal the GUI happens to
    be attached to. The launcher-boot case gets the actionable hint: nothing
    about a local engine + local checkout needs the AppImage.
    """
    argv = argv_of(cmd)
    if not argv or os.path.isfile(argv[0]):
        return None
    msg = f"Binary not found: {argv[0]}"
    if modinfo.get("modtype") == "0":
        msg += ("\nThis boot goes through the Beyond-All-Reason launcher. Either pick "
                "Boot = engine (runs spring directly, needs no AppImage / .exe), or point "
                "at one with --launcher-binary / BAR_APPIMAGE_PATH.")
    return msg
