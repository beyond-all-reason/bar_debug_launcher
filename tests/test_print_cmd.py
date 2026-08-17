"""End-to-end smoke test for `python -m bar_launch --print-cmd ...`.

Exercises the same (play, source, boot) matrix as test_intents.py, but drives
the full main() entry point against a fixture Context (no Tk, no real BAR
data dir, no subprocess). Confirms that resolve_intent + build_runcmd compose
correctly: every valid intent in the grid produces a non-empty engine command
string with the expected boot-mode shape.

If something breaks the GUI's gencmd path -- which calls the same resolve_intent
+ build_runcmd pair -- this catches it without needing a live Tk session.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

import pytest

import bar_launch.__main__ as bl_main
from bar_launch.core import Context

from tests.test_intents import FIXTURE_MODINFOS, _MATRIX, _PINNED_VERSION


@pytest.fixture
def fake_ctx(tmp_path):
    # build_runcmd writes side-effect files (start script / dev-lobby config)
    # into cwd; chdir into tmp_path so we don't pollute the repo.
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        engine_key = "recoil_2025.06.19"
        ctx = Context(
            barinstallpath=str(tmp_path),
            datafolder="data",
            launcher_binary="Beyond-All-Reason.AppImage",
            engines={engine_key: str(tmp_path / "data" / "engine" / engine_key / "spring")},
            modinfos=dict(FIXTURE_MODINFOS),
        )
        yield ctx, engine_key
    finally:
        os.chdir(old_cwd)


@contextmanager
def _patched_main(ctx):
    # main() calls build_context() to build a real Context. We swap it for a
    # function that returns the fixture Context regardless of args.
    with patch.object(bl_main, "build_context", lambda **kw: ctx):
        yield


_VALID_CELLS = sorted(
    (p, s, b) for (p, s, b), v in _MATRIX.items() if v[0] == "ok"
)
_INVALID_CELLS = sorted(
    (p, s, b) for (p, s, b), v in _MATRIX.items() if v[0] == "raise"
)


@pytest.mark.parametrize(("play", "source", "boot"), _VALID_CELLS)
def test_print_cmd_grid_valid(fake_ctx, capsys, play, source, boot):
    ctx, engine_key = fake_ctx
    argv = ["--print-cmd", "--play", play, "--source", source, "--boot", boot,
            "--engine", engine_key]
    if source == "pinned":
        argv += ["--version", _PINNED_VERSION[play]]

    with _patched_main(ctx):
        rc = bl_main.main(argv)
    assert rc == 0, (play, source, boot)

    out = capsys.readouterr().out.strip().splitlines()[-1]
    # Resolve what the matrix says we should land on, then check the printed
    # command's *shape* matches that modtype.
    expected_label = _MATRIX[(play, source, boot)][1]
    expected_modtype = _MATRIX[(play, source, boot)][2]
    if expected_modtype == "0":
        # AppImage launcher path: "<install>/<launcher>" -c "<config.json>"
        assert "Beyond-All-Reason.AppImage" in out, (play, source, boot, out)
        assert "bar_debug_launcher_config.json" in out, (play, source, boot, out)
    elif expected_modtype == "5":
        # Engine direct, --menu mode.
        assert "--menu" in out, (play, source, boot, out)
        assert "Beyond-All-Reason.AppImage" not in out, (play, source, boot, out)
    elif expected_modtype == "1":
        # Engine direct, no map = bare invocation; no --menu, no -c.
        assert "--isolation" in out, (play, source, boot, out)
        assert "--menu" not in out, (play, source, boot, out)
        assert "-c " not in out, (play, source, boot, out)


@pytest.mark.parametrize(("play", "source", "boot"), _INVALID_CELLS)
def test_print_cmd_grid_invalid(fake_ctx, play, source, boot):
    ctx, engine_key = fake_ctx
    argv = ["--print-cmd", "--play", play, "--source", source, "--boot", boot,
            "--engine", engine_key]
    if source == "pinned":
        argv += ["--version", _PINNED_VERSION[play]]

    with _patched_main(ctx):
        # Replay cells raise ValueError out of resolve_intent. main() doesn't
        # catch it -- which is fine: the CLI surfaces the error to stderr and
        # exits non-zero. We just assert it bubbled up.
        with pytest.raises(ValueError, match="try_start_replay"):
            bl_main.main(argv)


def test_print_cmd_pinned_requires_version(fake_ctx):
    ctx, engine_key = fake_ctx
    argv = ["--print-cmd", "--play", "bar", "--source", "pinned", "--boot", "engine",
            "--engine", engine_key]
    with _patched_main(ctx):
        with pytest.raises(ValueError, match="requires version"):
            bl_main.main(argv)
