"""CLI entry point: `python -m bar_launch ...`.

Resolves an intent (or explicit --game label) to an engine command and either
prints it (--print-cmd) or executes it. The Tk GUI is launched when no
intent-style flags are provided and --no-gui isn't set.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from typing import Optional

from .core import build_context, check_host_bridge, explain_exit, host_cmd_prefix
from .engine_cmd import argv_of, build_runcmd, missing_binary_message
from .intents import Intent, default_boot, resolve_intent


def _resolve_bar_install(args) -> Optional[str]:
    if args.bar_install:
        return args.bar_install
    # Windows install layout is <install>\Beyond-All-Reason.exe + <install>\data.
    # The WSL shim passes --data-dir but no --bar-install; derive the install
    # root so launcher boots resolve the .exe instead of argv[0]'s dir.
    # abspath first: dirname of a relative single-component path ("data")
    # would otherwise be "", which build_context would take as a literal
    # install path and resolve everything against cwd with a bare .exe name.
    if args.data_dir and platform.system() == "Windows":
        return os.path.dirname(os.path.abspath(os.path.normpath(args.data_dir)))
    return None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bar_launch",
        description="Launch BAR / Recoil for development. Headless or with the existing Tk GUI.",
    )
    p.add_argument("--gui", dest="gui", action="store_true", default=None,
                   help="force the Tk GUI (default unless --no-gui/--headless or --print-cmd is given)")
    p.add_argument("--no-gui", "--headless", dest="gui", action="store_false",
                   help="run headless; requires either --play or --game")
    p.add_argument("--data-dir", help="override BAR data dir (default: auto-detect)")
    p.add_argument("--bar-install", help="override BAR install path (default: dirname of argv[0])")
    p.add_argument("--launcher-binary", help="override launcher (AppImage / .exe) path")
    p.add_argument("--engine", help="engine version key from the engine cache (e.g. 'recoil_2025.06.19' or 'local-build')")
    p.add_argument("--play", choices=("chobby", "bar", "replay"), help="what to launch")
    p.add_argument("--source", choices=("latest", "local", "pinned"), default="latest",
                   help="version source: latest test channel, local checkout under <data-dir>/games/, or a pinned cached version")
    p.add_argument("--version", help="cached version, only meaningful with --source pinned")
    p.add_argument("--boot", choices=("launcher", "engine"),
                   help="boot via the AppImage launcher or directly into the engine (defaults: launcher for chobby, engine for bar/replay)")
    p.add_argument("--map", dest="mapname", help="map name (only with --play bar)")
    p.add_argument("--modopts", default="", help="additional modoptions (only with --play bar)")
    p.add_argument("--game", help="legacy: pick by exact modinfos label (skips --play/--source resolution)")
    p.add_argument("--print-cmd", action="store_true", help="resolve and print the engine command, don't execute")
    return p


def _resolve_engine(ctx, requested: Optional[str]) -> str:
    if requested:
        # Allow exact match or trailing-substring match (e.g. 'local-build' for 'recoil_local-build').
        if requested in ctx.engines:
            return requested
        for k in ctx.engines:
            if requested in k:
                return k
        raise SystemExit(f"engine {requested!r} not found in {sorted(ctx.engines.keys())}")
    if not ctx.engines or list(ctx.engines.keys()) == ["NO ENGINES FOUND!"]:
        raise SystemExit("no engines installed in the BAR data dir")
    return sorted(ctx.engines.keys())[-1]


def _resolve_modinfo(ctx, args) -> tuple[str, dict]:
    if args.game is not None:
        if args.game not in ctx.modinfos:
            raise SystemExit(f"--game {args.game!r} not found; valid: {sorted(ctx.modinfos.keys())}")
        return args.game, ctx.modinfos[args.game]
    if args.play is None:
        raise SystemExit("headless mode requires --play (or --game for legacy label-based selection)")
    intent = Intent(
        play=args.play,
        source=args.source,
        boot=args.boot or default_boot(args.play),
        version=args.version,
    )
    return resolve_intent(intent, ctx.modinfos)


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    # GUI is the default. Going headless is an explicit choice -- either
    # --no-gui/--headless, or --print-cmd which is a pure-CLI affordance and
    # has no GUI equivalent. Intent flags (--play, --source, etc.) on their
    # own do NOT skip the GUI; they're irrelevant in GUI mode (the GUI has
    # its own default-resolution logic) but they shouldn't be a trapdoor that
    # silently bypasses it. When the user wants headless, they say so.
    run_gui = args.gui if args.gui is not None else (not args.print_cmd)
    bar_install = _resolve_bar_install(args)

    if run_gui:
        # The Tk GUI still lives in BAR_Debug_Launcher.py for now; spawn it.
        # It has no CLI of its own, so hand it --data-dir/--bar-install via env.
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gui_script = os.path.join(here, "BAR_Debug_Launcher.py")
        if not os.path.exists(gui_script):
            raise SystemExit(f"GUI entry point not found at {gui_script}")
        env = dict(os.environ)
        if args.data_dir:
            env["BAR_DATA_DIR"] = args.data_dir
        if bar_install:
            env["BAR_INSTALL_PATH"] = bar_install
        if args.launcher_binary:
            # The GUI's launcher discovery honors BAR_APPIMAGE_PATH (file or
            # directory), so --launcher-binary rides along on that.
            env["BAR_APPIMAGE_PATH"] = args.launcher_binary
        return subprocess.call([sys.executable, gui_script], env=env)

    ctx = build_context(
        barinstallpath=bar_install,
        datafolder=args.data_dir,
        launcher_binary=args.launcher_binary,
    )
    engine_version = _resolve_engine(ctx, args.engine)
    label, modinfo = _resolve_modinfo(ctx, args)
    cmd = build_runcmd(ctx, modinfo, engine_version, args.mapname, args.modopts)

    if args.print_cmd:
        print(cmd)
        return 0

    problem = missing_binary_message(cmd, modinfo)
    if problem:
        raise SystemExit(f"error: {problem}")
    prefix = host_cmd_prefix()
    bridge_problem = check_host_bridge(prefix)
    if bridge_problem:
        raise SystemExit(f"error: {bridge_problem}")
    argv = prefix + argv_of(cmd)
    print(f"Launching ({label!r} on engine {engine_version!r}):", argv, flush=True)
    # Stay attached. Fire-and-forget Popen + exit looked fine on a bare host
    # (the orphaned engine kept the terminal), but the devtools flow runs this
    # inside `distrobox enter`: when we exit, the exec session's pty closes and
    # the distrobox-host-exec -> host-spawn chain is SIGHUP'd before the engine
    # prints a single line -- a "launch" that produces exactly nothing after
    # the Launching line. Headless is a terminal command; behave like one.
    proc = subprocess.Popen(argv, close_fds=True)
    try:
        rc = proc.wait()
        hint = explain_exit(rc, argv)
        if hint:
            print(f"bar_launch: {hint}", file=sys.stderr)
        return rc
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 130


if __name__ == "__main__":
    sys.exit(main())
