"""Unit tests for bar_launch.engine_cmd string encoding and pre-launch checks.

The command string is displayed (GUI panel, --print-cmd, launch log) and also
parsed back into argv for Popen. These tests pin the contract that both agree
and that the displayed form survives a paste into a POSIX shell.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys

import pytest

from bar_launch.core import Context
from bar_launch.engine_cmd import argv_of, build_runcmd, missing_binary_message

MENU_NAME = "BYAR Chobby $VERSION"


@pytest.fixture
def ctx(tmp_path):
    install = tmp_path / "Beyond All Reason"   # space on purpose
    engine = install / "data" / "engine" / "local-build" / "spring"
    engine.parent.mkdir(parents=True)
    engine.write_text("")
    return Context(
        barinstallpath=str(install),
        datafolder="data",
        launcher_binary="Beyond-All-Reason.AppImage",
        engines={"local-build": str(engine)},
    ), str(engine)


def test_argv_roundtrip_keeps_version_placeholder(ctx):
    c, engine = ctx
    cmd = build_runcmd(c, {"modtype": "5", "name": MENU_NAME}, "local-build")
    assert argv_of(cmd) == [
        engine, "--isolation", "--write-dir", os.path.join(c.barinstallpath, "data"),
        "--menu", MENU_NAME,
    ]


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX shell paste contract")
def test_displayed_command_is_posix_paste_safe(ctx):
    # A user copying the panel/--print-cmd text into bash must get the same
    # argv the launcher runs: "$VERSION" in double quotes would expand to ""
    # and the engine would fail with 'Dependent archive "byar chobby " ...'.
    c, _ = ctx
    cmd = build_runcmd(c, {"modtype": "5", "name": MENU_NAME}, "local-build")
    # Run the displayed string through a real shell and print each argv item.
    probe = f'set -- {cmd}; for a; do printf "%s\\n" "$a"; done'
    out = subprocess.run(["sh", "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.splitlines() == argv_of(cmd)
    assert "'BYAR Chobby $VERSION'" in cmd


def test_missing_binary_message_engine(ctx):
    c, engine = ctx
    cmd = build_runcmd(c, {"modtype": "5", "name": MENU_NAME}, "local-build")
    assert missing_binary_message(cmd, {"modtype": "5"}) is None
    os.remove(engine)
    msg = missing_binary_message(cmd, {"modtype": "5"})
    assert msg and engine in msg and "Boot = engine" not in msg


def test_missing_binary_message_launcher_hint(ctx):
    c, _ = ctx
    mi = {"modtype": "0", "name": MENU_NAME}
    cmd = build_runcmd(c, mi, "local-build")
    msg = missing_binary_message(cmd, mi)
    assert msg and "Beyond-All-Reason.AppImage" in msg
    assert "Boot = engine" in msg and "BAR_APPIMAGE_PATH" in msg


def test_explain_exit_127_via_host_bridge():
    from bar_launch.core import explain_exit
    argv = ["/usr/bin/distrobox-host-exec", "/opt/b a r/spring", "--isolation"]
    hint = explain_exit(127, argv)
    assert hint and "host bridge" in hint and "'/opt/b a r/spring'" in hint
    assert explain_exit(0, argv) is None
    assert explain_exit(1, argv) is None
    direct = explain_exit(127, ["/opt/spring", "--isolation"])
    assert direct and "could not exec '/opt/spring'" in direct


def test_check_host_bridge():
    from bar_launch.core import check_host_bridge
    assert check_host_bridge([]) is None                       # native: nothing to check
    assert check_host_bridge(["/usr/bin/env"]) is None         # a working "bridge"
    msg = check_host_bridge(["/bin/sh", "-c", "echo 'no flatpak session helper' >&2; exit 127; --"])
    assert msg and "exit 127" in msg and "flatpak" in msg
