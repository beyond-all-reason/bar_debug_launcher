"""Intent translation: human-meaningful (play, source, boot) -> raw modinfo.

The launcher's existing dropdown labels conflate three orthogonal axes into
one string:

    1. What you want to play: chobby (lobby/menu) vs bar (game) vs replay
    2. Which version: latest test channel, local checkout, or a pinned cached
       version
    3. How it boots: through the AppImage launcher (modtype 0) or straight
       into the engine (modtype 5 for menus, modtype 1 for games)

This module takes a triple and returns a (label, modinfo) pair the rest of
the launcher already understands. Tests live in tests/test_intents.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


PLAY_CHOICES = ("chobby", "bar", "replay")
SOURCE_CHOICES = ("latest", "local", "pinned")
BOOT_CHOICES = ("launcher", "engine")


@dataclass
class Intent:
    play: str            # "chobby" | "bar" | "replay"
    source: str          # "latest" | "local" | "pinned"
    boot: str            # "launcher" | "engine"
    version: Optional[str] = None  # required iff source == "pinned"


def default_boot(play: str) -> str:
    """Default boot mode for a given --play value.

    Chobby boots via the AppImage launcher (modtype 0) so the launcher can
    handle splash + downloads. BAR and replays boot the engine directly so we
    don't pay launcher overhead.
    """
    if play == "chobby":
        return "launcher"
    return "engine"


def resolve_intent(intent: Intent, modinfos: dict[str, dict]) -> tuple[str, dict]:
    """Pick the right modinfos entry for an intent.

    Returns (label, modinfo) where label is the modinfos key (useful for
    debugging / --print-cmd) and modinfo is the dict the engine_cmd module
    expects.
    """
    if intent.play not in PLAY_CHOICES:
        raise ValueError(f"unknown play={intent.play!r}, expected one of {PLAY_CHOICES}")
    if intent.source not in SOURCE_CHOICES:
        raise ValueError(f"unknown source={intent.source!r}, expected one of {SOURCE_CHOICES}")
    if intent.boot not in BOOT_CHOICES:
        raise ValueError(f"unknown boot={intent.boot!r}, expected one of {BOOT_CHOICES}")
    if intent.source == "pinned" and not intent.version:
        raise ValueError("source=pinned requires version=...")
    if intent.play == "replay":
        raise ValueError("replay intents go through try_start_replay, not resolve_intent")

    # Latest -> the canonical rapid:// keys that build_context always inserts.
    if intent.source == "latest":
        if intent.play == "chobby":
            label = (
                "Spring-launcher with rapid://byar-chobby:test"
                if intent.boot == "launcher"
                else "Latest BYAR Chobby Lobby: rapid://byar-chobby:test"
            )
        else:  # bar
            label = "Latest BAR Game: rapid://byar:test"
        if label not in modinfos:
            raise KeyError(f"expected {label!r} in modinfos but it's missing")
        return label, modinfos[label]

    # Local -> entries discovered by the [LOCAL] scan in build_context. The
    # scan labels checkouts f"[LOCAL] {gamedir}" for *any* directory name, so
    # match on the [LOCAL] tag + modtype rather than hardcoded checkout names:
    #   modtype 1 = game, modtype 5 = chobby engine-direct, and for every
    #   modtype-5 checkout the scan also adds a paired modtype-0
    #   "[LOCAL] Spring-launcher with ..." entry for launcher boots.
    if intent.source == "local":
        if intent.play == "chobby":
            wanted_modtype = "5" if intent.boot == "engine" else "0"
        else:  # bar
            wanted_modtype = "1"
        for label, mi in modinfos.items():
            if label.startswith("[LOCAL]") and str(mi.get("modtype", "")) == wanted_modtype:
                return label, mi
        raise KeyError(
            f"no [LOCAL] entry matches play={intent.play} boot={intent.boot}; "
            f"is a checkout linked into <data-dir>/games/?"
        )

    # Pinned -> match $VERSION-tagged entries by intent.version. Prefer an
    # exact whitespace-delimited token match so e.g. version "2025.04.1" can't
    # silently resolve to "... 2025.04.10 $VERSION"; fall back to substring so
    # partial pins like "2025.04" keep working.
    assert intent.source == "pinned" and intent.version
    needle = intent.version
    wanted_modtype = "1" if intent.play == "bar" else ("0" if intent.boot == "launcher" else "5")
    token_re = re.compile(rf"(?<!\S){re.escape(needle)}(?!\S)")
    exact_match = None
    substring_match = None
    for label, mi in modinfos.items():
        if str(mi.get("modtype", "")) != wanted_modtype or needle not in label:
            continue
        if exact_match is None and token_re.search(label):
            exact_match = (label, mi)
        if substring_match is None:
            substring_match = (label, mi)
    if exact_match or substring_match:
        return exact_match or substring_match
    raise KeyError(f"no entry containing {needle!r} found for play={intent.play} boot={intent.boot}")
