"""Unit tests for bar_launch.intents.

These run without Tk and without a populated BAR data dir — they exercise the
intent translation against a fixture modinfos dict that mirrors what
build_context() produces in practice.
"""
from __future__ import annotations

import pytest

from bar_launch.intents import (
    BOOT_CHOICES,
    Intent,
    PLAY_CHOICES,
    SOURCE_CHOICES,
    default_boot,
    resolve_intent,
)


# Mirrors the canonical entries build_context() always inserts, plus a couple
# of $VERSION-tagged + [LOCAL] entries to exercise pinned/local resolution.
# Includes a chobby-pinned pair so the (chobby, pinned, *) cells of the matrix
# can resolve to a real entry rather than KeyError on a missing fixture.
FIXTURE_MODINFOS = {
    "Spring-launcher with rapid://byar-chobby:test": {"modtype": "0", "name": "rapid://byar-chobby:test"},
    "Latest BYAR Chobby Lobby: rapid://byar-chobby:test": {"name": "rapid://byar-chobby:test", "version": "", "modtype": "5"},
    "Latest BAR Game: rapid://byar:test": {"name": "rapid://byar:test", "version": "", "modtype": "1"},
    "Beyond All Reason 2025.04.1234 $VERSION": {"modtype": "1", "name": "Beyond All Reason 2025.04.1234"},
    "Spring-launcher with BYAR Chobby v1.2.3 $VERSION": {"modtype": "0", "name": "BYAR Chobby v1.2.3"},
    "BYAR Chobby v1.2.3 $VERSION (no launcher)": {"modtype": "5", "name": "BYAR Chobby v1.2.3"},
    "[LOCAL] Beyond-All-Reason": {"modtype": "1", "name": "Beyond All Reason $VERSION"},
    "[LOCAL] BYAR-Chobby": {"modtype": "5", "name": "BYAR Chobby $VERSION"},
    "[LOCAL] Spring-launcher with BYAR-Chobby": {"modtype": "0", "name": "BYAR Chobby $VERSION"},
}


def test_default_boot():
    assert default_boot("chobby") == "launcher"
    assert default_boot("bar") == "engine"
    assert default_boot("replay") == "engine"


def test_latest_chobby_via_launcher():
    label, mi = resolve_intent(Intent("chobby", "latest", "launcher"), FIXTURE_MODINFOS)
    assert label == "Spring-launcher with rapid://byar-chobby:test"
    assert mi["modtype"] == "0"


def test_latest_chobby_direct_engine():
    label, mi = resolve_intent(Intent("chobby", "latest", "engine"), FIXTURE_MODINFOS)
    assert label == "Latest BYAR Chobby Lobby: rapid://byar-chobby:test"
    assert mi["modtype"] == "5"


def test_latest_bar_engine():
    label, mi = resolve_intent(Intent("bar", "latest", "engine"), FIXTURE_MODINFOS)
    assert label == "Latest BAR Game: rapid://byar:test"
    assert mi["modtype"] == "1"


def test_local_bar_engine():
    label, mi = resolve_intent(Intent("bar", "local", "engine"), FIXTURE_MODINFOS)
    assert label == "[LOCAL] Beyond-All-Reason"
    assert mi["modtype"] == "1"


def test_local_chobby_launcher():
    label, mi = resolve_intent(Intent("chobby", "local", "launcher"), FIXTURE_MODINFOS)
    assert label == "[LOCAL] Spring-launcher with BYAR-Chobby"
    assert mi["modtype"] == "0"


def test_local_chobby_engine():
    label, mi = resolve_intent(Intent("chobby", "local", "engine"), FIXTURE_MODINFOS)
    assert label == "[LOCAL] BYAR-Chobby"
    assert mi["modtype"] == "5"


def test_pinned_bar_by_substring():
    label, mi = resolve_intent(Intent("bar", "pinned", "engine", version="2025.04"), FIXTURE_MODINFOS)
    assert "2025.04.1234" in label
    assert mi["modtype"] == "1"


def test_pinned_requires_version():
    with pytest.raises(ValueError, match="requires version"):
        resolve_intent(Intent("bar", "pinned", "engine"), FIXTURE_MODINFOS)


def test_replay_intent_rejected():
    with pytest.raises(ValueError, match="try_start_replay"):
        resolve_intent(Intent("replay", "latest", "engine"), FIXTURE_MODINFOS)


def test_unknown_play_rejected():
    with pytest.raises(ValueError, match="unknown play"):
        resolve_intent(Intent("blizzcon", "latest", "engine"), FIXTURE_MODINFOS)


def test_local_bar_missing_raises():
    incomplete = {k: v for k, v in FIXTURE_MODINFOS.items() if not k.startswith("[LOCAL] Beyond")}
    with pytest.raises(KeyError, match="linked into"):
        resolve_intent(Intent("bar", "local", "engine"), incomplete)


def test_pinned_no_match_raises():
    with pytest.raises(KeyError, match="no entry containing"):
        resolve_intent(Intent("bar", "pinned", "engine", version="9999.99"), FIXTURE_MODINFOS)


def test_pinned_prefers_exact_token_over_substring():
    # '2025.04.1' is a substring of '2025.04.10'; an exact token match must
    # win even when the substring-only entry comes first in insertion order.
    modinfos = {
        "Beyond All Reason 2025.04.10 $VERSION": {"modtype": "1", "name": "Beyond All Reason 2025.04.10"},
        "Beyond All Reason 2025.04.1 $VERSION": {"modtype": "1", "name": "Beyond All Reason 2025.04.1"},
    }
    label, mi = resolve_intent(Intent("bar", "pinned", "engine", version="2025.04.1"), modinfos)
    assert label == "Beyond All Reason 2025.04.1 $VERSION"
    # Partial pins still fall back to substring matching.
    label, _ = resolve_intent(Intent("bar", "pinned", "engine", version="2025.04"), modinfos)
    assert "2025.04" in label


def test_local_matches_any_checkout_dir_name():
    # The games/ scan labels checkouts '[LOCAL] {gamedir}' for any directory
    # name; resolution must not depend on hardcoded checkout names.
    modinfos = {
        "[LOCAL] my-bar-fork.sdd": {"modtype": "1", "name": "My BAR Fork $VERSION"},
        "[LOCAL] chobby-dev": {"modtype": "5", "name": "Chobby Dev $VERSION"},
        "[LOCAL] Spring-launcher with chobby-dev": {"modtype": "0", "name": "Chobby Dev $VERSION"},
    }
    label, mi = resolve_intent(Intent("bar", "local", "engine"), modinfos)
    assert label == "[LOCAL] my-bar-fork.sdd" and mi["modtype"] == "1"
    label, mi = resolve_intent(Intent("chobby", "local", "engine"), modinfos)
    assert label == "[LOCAL] chobby-dev" and mi["modtype"] == "5"
    label, mi = resolve_intent(Intent("chobby", "local", "launcher"), modinfos)
    assert label == "[LOCAL] Spring-launcher with chobby-dev" and mi["modtype"] == "0"


# ---------------------------------------------------------------------------
# Full permutation grid: 3 play x 3 source x 2 boot = 18 cells.
#
# Each cell is one of:
#   ("ok", expected_label, expected_modtype)  -- resolves cleanly
#   ("raise", exc_type, message_substring)    -- resolve_intent rejects it
#
# The matrix is the canonical reference for what every (play, source, boot)
# combination is *supposed* to do. If you change resolve_intent's behaviour,
# update the matrix in the same diff so the regression net stays explicit.
#
# Notes on edge cells:
#   - (replay, *, *) all reject: replay goes through try_start_replay, which
#     handles its own engine resolution from the demo header.
#   - (bar, latest, launcher) and (bar, latest, engine) resolve to the *same*
#     label ("Latest BAR Game: rapid://byar:test", modtype=1). resolve_intent
#     intentionally ignores boot for play=bar+source=latest because there is
#     only one canonical "latest BAR" entry. The boot axis only diverges for
#     chobby (where rapid:// vs direct-engine are two real labels) and for
#     pinned cached versions (where the modtype differs).
#   - (bar, local, launcher) silently degrades to engine boot: there is no
#     "[LOCAL] Spring-launcher with Beyond-All-Reason" entry — local BAR
#     checkouts only exist as modtype=1, and intents.py picks the modtype=1
#     entry rather than raising. If we want this to raise instead, change
#     intents.py and flip this cell from "ok" to "raise".
# ---------------------------------------------------------------------------

# version is supplied for all (*, pinned, *) cells; resolve_intent rejects
# pinned without version separately in test_pinned_requires_version above.
_MATRIX = {
    # (chobby, latest, *)
    ("chobby", "latest", "launcher"): ("ok", "Spring-launcher with rapid://byar-chobby:test", "0"),
    ("chobby", "latest", "engine"):   ("ok", "Latest BYAR Chobby Lobby: rapid://byar-chobby:test", "5"),
    # (bar, latest, *) -- boot axis collapses for latest BAR
    ("bar", "latest", "launcher"):    ("ok", "Latest BAR Game: rapid://byar:test", "1"),
    ("bar", "latest", "engine"):      ("ok", "Latest BAR Game: rapid://byar:test", "1"),
    # (chobby, local, *)
    ("chobby", "local", "launcher"):  ("ok", "[LOCAL] Spring-launcher with BYAR-Chobby", "0"),
    ("chobby", "local", "engine"):    ("ok", "[LOCAL] BYAR-Chobby", "5"),
    # (bar, local, *) -- launcher silently degrades to the modtype=1 entry
    ("bar", "local", "launcher"):     ("ok", "[LOCAL] Beyond-All-Reason", "1"),
    ("bar", "local", "engine"):       ("ok", "[LOCAL] Beyond-All-Reason", "1"),
    # (chobby, pinned, *) -- needs a version that substring-matches a fixture entry
    ("chobby", "pinned", "launcher"): ("ok", "Spring-launcher with BYAR Chobby v1.2.3 $VERSION", "0"),
    ("chobby", "pinned", "engine"):   ("ok", "BYAR Chobby v1.2.3 $VERSION (no launcher)", "5"),
    # (bar, pinned, *)
    ("bar", "pinned", "launcher"):    ("ok", "Beyond All Reason 2025.04.1234 $VERSION", "1"),
    ("bar", "pinned", "engine"):      ("ok", "Beyond All Reason 2025.04.1234 $VERSION", "1"),
    # (replay, *, *) -- always rejected
    ("replay", "latest", "launcher"): ("raise", ValueError, "try_start_replay"),
    ("replay", "latest", "engine"):   ("raise", ValueError, "try_start_replay"),
    ("replay", "local", "launcher"):  ("raise", ValueError, "try_start_replay"),
    ("replay", "local", "engine"):    ("raise", ValueError, "try_start_replay"),
    ("replay", "pinned", "launcher"): ("raise", ValueError, "try_start_replay"),
    ("replay", "pinned", "engine"):   ("raise", ValueError, "try_start_replay"),
}


# Sanity check: the matrix MUST cover every cell. If someone adds a new
# play/source/boot value, this catches the missing rows immediately.
def test_matrix_is_complete():
    expected = {(p, s, b) for p in PLAY_CHOICES for s in SOURCE_CHOICES for b in BOOT_CHOICES}
    assert set(_MATRIX.keys()) == expected, (
        f"matrix missing: {expected - set(_MATRIX.keys())}; "
        f"extra: {set(_MATRIX.keys()) - expected}"
    )


# Version supplied for (*, pinned, *) cells. "replay" never reaches the
# version-substring lookup -- resolve_intent rejects it on play before then --
# but we still need *some* string so the version-required check earlier in
# resolve_intent doesn't fire first and shadow the expected error message.
_PINNED_VERSION = {"chobby": "v1.2.3", "bar": "2025.04", "replay": "irrelevant"}


@pytest.mark.parametrize(("play", "source", "boot"), sorted(_MATRIX.keys()))
def test_intent_grid(play, source, boot):
    expectation = _MATRIX[(play, source, boot)]
    version = _PINNED_VERSION.get(play) if source == "pinned" else None
    intent = Intent(play, source, boot, version=version)

    if expectation[0] == "raise":
        _, exc_type, msg_substr = expectation
        with pytest.raises(exc_type, match=msg_substr):
            resolve_intent(intent, FIXTURE_MODINFOS)
        return

    _, expected_label, expected_modtype = expectation
    label, mi = resolve_intent(intent, FIXTURE_MODINFOS)
    assert label == expected_label, (play, source, boot)
    assert str(mi["modtype"]) == expected_modtype, (play, source, boot)
