#!/usr/bin/env python

# This file is part of the "spring relay site / srs" program. It is published
# under the GPLv3.
#
# Copyright (C) 2016-2020 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gzip
import logging
import pprint
import re
import struct
import sys
import threading
import zlib
from datetime import timedelta
from struct import unpack
from time import localtime, strftime
from typing import Union

#import magic
import json as ujson

#from .match_stats import MatchStatsGeneration

#if not hasattr(magic, "from_file"):
#    print(
#        "Please install python-magic (with pip, version should be around 0.4, NOT 5.xx)!"
#    )
#    exit(1)

try:
    from .script import (
        Script,
        ScriptAI,
        ScriptAlly,
        ScriptGamesetup,
        ScriptMapoptions,
        ScriptModoptions,
        ScriptPlayer,
        ScriptRestrictions,
        ScriptTeam,
    )
    from .demoparser import Demoparser
    from django.conf import settings

    DEBUG = settings.DEBUG
except ImportError:
    # commandline use
    from script import (
        Script,
        ScriptAI,
        ScriptAlly,
        ScriptGamesetup,
        ScriptMapoptions,
        ScriptModoptions,
        ScriptPlayer,
        ScriptRestrictions,
        ScriptTeam,
    )
    from demoparser import Demoparser

    # direct import of settings module (not through Django means) to allow usage without Django installation
#    from ..spring_replay_site.settings import DEBUG
    DEBUG = True


logger = logging.getLogger(__name__)


#
# From rts/System/LoadSave/demofile.h
#
#  * Demo file layout is like this:
#  *
#  * - DemoFileHeader
#  *   - Data chunks:
#  *     - Startscript (scriptSize)
#  *     - Demo stream (demoStreamSize)
#  *     - Player statistics, one PlayerStatistic for each player
#  *     - Team statistics, consisting of:
#  *       - Array of numTeams dwords indicating the number of
#  *         CTeam::Statistics for each team.
#  *       - Array of all CTeam::Statistics (total number of items is the
#  *         sum of the elements in the array of dwords).
#  *
#  * The header is designed to be extensible: it contains a version field and a
#  * headerSize field to support this. The version field is a major version number
#  * of the file format, if this changes, anything may have changed in the file.
#  * It is not supposed to change often (if at all). The headerSize field is a
#  * minor version number, which happens to be equal to sizeof(DemoFileHeader).
#  *
#  * If Spring did not cleanup properly (crashed), the demoStreamSize is 0 and it
#  * can be assumed the demo stream continues until the end of the file.
#
#
#  * The demo stream layout is as follows:
#  *
#  * - DemoStreamChunkHeader
#  * - length bytes raw data from network stream
#  * - DemoStreamChunkHeader
#  * - length bytes raw data from network stream
#  * - ...
#


class ParseError(Exception):
    pass


class BadFileType(ParseError):
    pass


class Parse_demo_file:
    BA_platform_data_to_API = {
        "CPU": "cpuName",
        "CPU cores": "cpuCores",
        "RAM": "ram",
        "GPU": "glRenderer",
        "GPU VRAM": "gpuMemorySize",
        "OS": "osFamily",
    }

    def __init__(self, filename):
        self.filename = filename
        self.demofile = None
        self.header = dict()
        self.game_setup = {
            "ai": {},
            "allyteam": {},
            "mapoptions": {},
            "modoptions": {},
            "player": {},
            "restrict": {},
            "team": {},
            "host": {},
        }
        self.additional = {
            "gameover_frame": False,
            "chat": list(),
            "faction_change": dict(),
            "not_connected": dict(),
            "quit": dict(),
            "kicked": dict(),
            "timeout": dict(),
            "mapdraw": list(),
        }
        self.script = ""
        self.player_stats = None
        self.team_stats = None
        self.stats_thread = None
        self.tmp_stats = {}

    def read_blob(self, seek_size: int, blob_size: int) -> bytes:
        self.demofile.seek(seek_size)
        return self.demofile.read(blob_size)

    def read_blob_into_int(self, seek_size, blob_size):
        return unpack("i", self.read_blob(seek_size, blob_size))

    def check_magic(self):
        """
        - may raise IOError when opening a file to read
        - may raise Exception when file is not a spring demofile
        """
        return True

        '''
        filemagic = magic.from_file(self.filename, mime=True)

        if filemagic.endswith("gzip"):
            myopen = gzip.open
        else:
            myopen = open
        with myopen(self.filename, "rb") as demofile:
            demofile.seek(0)
            _magic = demofile.read(16)
            if not _magic.startswith(b"spring demofile"):
                raise BadFileType("Not a spring demofile.")
        '''

    def parse(self):
        """
        reads data from sdf, populates self.header and self.game_setup
        - may raise IOError when opening a file to read or write
        - may raise Exception when file is not a spring demofile
        """
        #filemagic = magic.from_file(self.filename, mime=True)
        #if filemagic.endswith("gzip"):
        #    myopen = gzip.open
        #else:
        #    myopen = open
        myopen = gzip.open
        # Example 20161016_233916_Charlie in the Hills v2_103.sdfz file size = 1104963 byte
        #         20161016_233916_Charlie in the Hills v2_103.sdf  file size = 3187862 byte

        # {'demoStreamSize': 3088877,
        #  'gameID': 'f34405581adec916289cf47c6b65bf7c',
        #  'gameTime': '0:28:45',
        #  'headerSize': 352,
        #  'magic': 'spring demofile',
        #  'numPlayers': 23,
        #  'numTeams': 10,
        #  'playerStatElemSize': 20,
        #  'playerStatSize': 460,
        #  'scriptSize': 4533,
        #  'teamStatElemSize': 80,
        #  'teamStatPeriod': 15,
        #  'teamStatSize': 93640,
        #  'unixTime': '2016-10-16 23:39:16',
        #  'version': 5,
        #  'versionString': '103',
        #  'wallclockTime': '0:30:43',
        #  'winningAllyTeamsSize': 1}
        #self.start_stats_thread()
        with myopen(self.filename, "rb") as self.demofile:
            self.parse_header()  # pos:       0 -     352 (0 -> headerSize)
            self.parse_script()  # pos:     352 -    4885 (headerSize -> + scriptSize)
            self.parse_demostream()  # pos:    4885 - 3093743 (headerSize + scriptSize -> + demoStreamSize | END)
            #                                                        352 + 4533 + 3088877 = 3093762
            # self.parse_player_stats()      # pos:       ? -       ? (numPlayers * playerStatElemSize = playerStatSize -> 23 * 20 = 460)
            # self.parse_team_stats()        # pos:       ? -       ? (teamStatSize = numTeams * char/uint (size of teams stats)
            #                                                                       + numTeams * teams stats * teamStatElemSize)
            self.parse_winningAllyTeams()  # pos: 3093762 - 3093763 (headerSize + scriptSize + demoStreamSize -> + winningAllyTeamsSize)
        logger.debug("Waiting for stats thread...")
        #self.join_stats_thread()
        logger.info("Stats thread finished.")
        #logger.debug("len(self.player_stats)=%d", len(self.player_stats))
        #logger.debug("len(self.team_stats)=%d", len(self.team_stats))
    def parse_header_and_script(self):
        with gzip.open(self.filename, "rb") as self.demofile:
            self.parse_header()  # pos:       0 -     352 (0 -> headerSize)
            self.parse_script()  # pos:     352 -    4885 (headerSize -> + scriptSize)


    def parse_header(self):
        #
        # struct DemoFileHeader from rts/System/LoadSave/demofile.h
        #
        self.header["magic"] = self.read_blob(
            0, 16
        )  # char magic[16]; ///< DEMOFILE_MAGIC
        if not self.header["magic"].startswith(b"spring demofile"):
            raise Exception("Not a spring demofile.")
        self.header["version"] = self.read_blob_into_int(16, 4)[
            0
        ]  # int version; ///< DEMOFILE_VERSION
        self.header["headerSize"] = self.read_blob_into_int(20, 4)[
            0
        ]  # int headerSize; ///< Size of the DemoFileHeader, minor version number.
        if (
            self.header["version"] > 4
        ):  # springrts commit ddf5be4f8a7006dcb870c5736b1a59c455df0535
            self.header["versionString"] = self.read_blob(
                24, 256
            )  # char versionString[256]; ///< Spring version string, e.g. "0.75b2", "0.75b2+svn4123"
        else:
            self.header["versionString"] = self.read_blob(24, 16)
        self.header["gameID"] = self.read_blob(
            280, 16
        )  # boost::uint8_t gameID[16]; ///< Unique game identifier. Identical for each player of the game.
        self.header["unixTime"] = self.read_blob(
            296, 8
        )  # boost::uint64_t unixTime; ///< Unix time when game was started.
        self.header["scriptSize"] = self.read_blob_into_int(304, 4)[
            0
        ]  # int scriptSize; ///< Size of startscript.
        self.header["demoStreamSize"] = self.read_blob_into_int(308, 4)[
            0
        ]  # int demoStreamSize; ///< Size of the demo stream.
        self.header["gameTime"] = self.read_blob_into_int(312, 4)[
            0
        ]  # int gameTime; ///< Total number of seconds game time.
        self.header["wallclockTime"] = self.read_blob_into_int(316, 4)[
            0
        ]  # int wallclockTime; ///< Total number of seconds wallclock time.
        self.header["numPlayers"] = self.read_blob_into_int(320, 4)[
            0
        ]  # int numPlayers; ///< Number of players for which stats are saved.
        self.header["playerStatSize"] = self.read_blob_into_int(324, 4)[
            0
        ]  # int playerStatSize; ///< Size of the entire player statistics chunk.
        self.header["playerStatElemSize"] = self.read_blob_into_int(328, 4)[
            0
        ]  # int playerStatElemSize; ///< sizeof(CPlayer::Statistics)
        self.header["numTeams"] = self.read_blob_into_int(332, 4)[
            0
        ]  # int numTeams; ///< Number of teams for which stats are saved.
        self.header["teamStatSize"] = self.read_blob_into_int(336, 4)[
            0
        ]  # int teamStatSize; ///< Size of the entire team statistics chunk.
        self.header["teamStatElemSize"] = self.read_blob_into_int(340, 4)[
            0
        ]  # int teamStatElemSize; ///< sizeof(CTeam::Statistics)
        self.header["teamStatPeriod"] = self.read_blob_into_int(344, 4)[
            0
        ]  # int teamStatPeriod; ///< Interval (in seconds) between team stats.
        self.header["winningAllyTeamsSize"] = self.read_blob_into_int(348, 4)[
            0
        ]  # int winningAllyTeamsSize; ///< The size of the vector of the winning ally teams

        #        self.header['void_swab']            = self.read_blob(352, self.header['headerSize']-352)    # lol?

        #        demo_stream = self.read_blob(self.demofile.tell(), self.header['demoStreamSize'])
        #        i = 0
        #        player_stats = []
        #        while i < self.header['numPlayers']:
        #            player_stats[i] = self.read_blob(self.demofile.tell(), self.header['playerStatElemSize'])
        #            i += 1
        self.header["magic"] = self.header["magic"].decode("utf-8").partition("\x00")[0]
        self.header["versionString"] = (
            self.header["versionString"].decode("utf-8").partition("\x00")[0]
        )
        self.header["gameID"] = (
            "%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x"
            % unpack("16B", self.header["gameID"])
        )
        self.header["unixTime"] = "%s" % strftime(
            "%Y-%m-%d %H:%M:%S", localtime(unpack("Q", self.header["unixTime"])[0])
        )
        self.header["gameTime"] = "%s" % str(timedelta(seconds=self.header["gameTime"]))
        self.header["wallclockTime"] = "%s" % str(
            timedelta(seconds=self.header["wallclockTime"])
        )
        logger.debug("self.header=\n%s", pprint.pformat(self.header))
        return self.header

    def parse_winningAllyTeams(self):
        self.winningAllyTeams = []
        winnning_team = 0
        self.demofile.seek(
            self.header["headerSize"]
            + self.header["scriptSize"]
            + self.header["demoStreamSize"]
        )
        while winnning_team < self.header["winningAllyTeamsSize"]:
            blob = self.read_blob(self.demofile.tell(), 1)
            logger.debug("blob=%r", blob)
            team = unpack_B = unpack("B", blob)
            self.winningAllyTeams.append(team[0])
            winnning_team += 1
        logger.debug("self.winningAllyTeams=%r", self.winningAllyTeams)
        return self.winningAllyTeams

    def parse_script(self):
        script = self.read_blob(self.header["headerSize"], self.header["scriptSize"])
        game = re.match(
            rb"^\[game\]\n\{(?P<data>.*)\}\n", script, re.DOTALL
        ).groupdict()
        game_data = game["data"].replace(b"\n", b"").replace(b"[options]{}", b"")
        section_iter = re.finditer(
            rb"\[(?P<name>.*?)\]\{(?P<data>.*?)\}", game_data, re.DOTALL
        )

        self.script = Script()

        for section_ in section_iter:
            section = section_.groupdict()
            if section and section["data"].strip():
                if section["name"].startswith(b"player"):
                    player = ScriptPlayer(section["name"], section["data"])
                    if player.spectator:
                        self.script.spectators[player.name] = player
                    else:
                        self.script.players[player.name] = player
                    self.game_setup["player"][player.num] = player.__dict__
                elif section["name"].startswith(b"ai"):
                    bot = ScriptAI(section["name"], section["data"])
                    if not hasattr(bot, "name"):
                        bot.name = section["name"]
                    self.script.bots[bot.name] = bot
                    self.game_setup["ai"][bot.name] = bot.__dict__
                elif section["name"].startswith(b"allyteam"):
                    ally = ScriptAlly(section["name"], section["data"])
                    self.script.allies.append(ally)
                    self.game_setup["allyteam"][ally.num] = ally.__dict__
                elif section["name"].startswith(b"team"):
                    team = ScriptTeam(section["name"], section["data"])
                    self.script.teams.append(team)
                    self.game_setup["team"][team.num] = team.__dict__
                elif section["name"] == "restrict":
                    self.script.restrictions = ScriptRestrictions(
                        section["name"], section["data"]
                    )
                    self.game_setup["restrict"] = self.script.restrictions
                elif section["name"] == "mapoptions":
                    self.script.mapoptions = ScriptMapoptions(
                        section["name"], section["data"]
                    )
                    self.game_setup["mapoptions"] = self.script.mapoptions.__dict__
                elif section["name"] == "modoptions":
                    self.script.modoptions = ScriptModoptions(
                        section["name"], section["data"]
                    )
                    self.game_setup["modoptions"] = self.script.modoptions.__dict__
        game_txt = game["data"].split(b"}")[-1:][0].replace(b"\n", b"")
        self.game_setup["host"] = ScriptGamesetup("game_setup_host", game_txt).__dict__
        self.script.other["mapname"] = self.game_setup["host"]["mapname"]
        self.script.other["modname"] = self.game_setup["host"]["gametype"]
        # logger.debug("self.game_setup=\n%s", pprint.pformat(self.game_setup))
        logger.debug("self.script=\n%s", pprint.pformat(self.script.__dict__))
        return self.script

    def _read(self, length):
        return self.demofile.read(length)

    def _tell(self):
        return self.demofile.tell()

    def _readPacket(self):
        maxSize = self.header["demoStreamSize"] or sys.maxsize
        if maxSize:
            modGameTime, length = struct.unpack("<fI", self._read(8))
            if (
                self._tell()
                + length
                - self.header["headerSize"]
                - self.header["scriptSize"]
                == maxSize
            ):
                return False
            data = self._read(length)
        if not data:
            return False
        return {"modGameTime": modGameTime, "length": length, "data": data}

    @classmethod
    def _ba_stats_to_platform_api(cls, ba_stats_str):
        stats = {}
        for m in re.finditer(
            rb"^(?P<name>\w+): *(?P<value>.*)$", ba_stats_str[3:], re.MULTILINE
        ):
            pl_stats = m.groupdict()
            if re.match(rb".*bit.*Hz", pl_stats["value"]):
                # found resolution, color depth etc: >>1920x1058:24bit @60Hz (windowed)<<
                stats["resolution_x"] = pl_stats["name"].split(b"x")[0]
                stats["resolution_y"] = pl_stats["name"].split(b"x")[1]
                m = re.match(
                    rb"(?P<bit>\d+)bit @(?P<hz>\d+)Hz (?P<windowed>\(.*\))*",
                    pl_stats["value"],
                ).groupdict()
                stats["color_depth"] = m["bit"]
                stats["refresh_rate"] = m["hz"]
                stats["windowed"] = bool(m["windowed"])
            else:
                stats[cls.BA_platform_data_to_API[pl_stats["name"]]] = pl_stats["value"]
        try:
            # remove surplus spaces
            stats["cpuName"] = b" ".join(stats["cpuName"].split())
        except KeyError:
            pass
        try:
            # remove surplus 'MB'
            stats["ram"] = stats["ram"][:-2]
        except KeyError:
            pass
        for attr in (
            "gpuMemorySize",
            "resolution_x",
            "resolution_y",
            "color_depth",
            "refresh_rate",
            "sdlVersionCompiledMajor",
            "sdlVersionCompiledMinor",
            "sdlVersionCompiledPatch",
            "sdlVersionLinkedMajor",
            "sdlVersionLinkedMinor",
            "sdlVersionLinkedPatch",
            "ram",
        ):
            try:
                stats[attr] = int(stats[attr])
            except (KeyError, ValueError):
                pass
        return stats

    def parse_demostream(self):
        def _save_playerinfo(playername, key, value):
            if playername in self.players:
                setattr(self.players[playername], key, value)
                if key in ("quit", "kicked", "timeout"):
                    self.additional[key][playername] = self.players[playername]
            else:
                setattr(self.spectators[playername], key, value)

        def _dictify(obj):
            if isinstance(obj, dict):
                return obj
            else:
                return obj.__dict__

        self.players = self.script.players
        self.spectators = self.script.spectators
        self.bots = self.script.bots
        self.teams = self.script.teams
        self.allies = self.script.allies
        self.options = dict(
            list(_dictify(self.script.modoptions).items())
            + list(_dictify(self.script.other).items())
            + list(_dictify(self.script.mapoptions).items())
        )
        self.restrictions = self.script.restrictions
        self.gameid = self.header["gameID"]

        self.demofile.seek(self.header["headerSize"] + self.header["scriptSize"])
        packet = True
        currentFrame = 0
        playerIDToName = {}
        ba_platform_stats = {}
        if DEBUG:
            kop = open("/tmp/msg.data", "wb")
            stats_fp = open("/tmp/stats.log", "wb")
            stats_fp.write("gameID: {}\n".format(self.header["gameID"]).encode())
        demoparser = Demoparser()
        while packet:
            packet = self._readPacket()
            try:
                messageData = demoparser.parsePacket(packet)
                if DEBUG:
                    kop.write(repr(messageData).encode() + b"\n")

                def clean(name: Union[bytes, str]) -> str:
                    if isinstance(name, bytes):
                        return name.replace(b"\x00", b"").decode()
                    else:
                        return name.replace("\x00", "")

                if messageData:
                    try:
                        clean_name = clean(messageData["playerName"])
                    except KeyError:
                        pass
                    if messageData["cmd"] == "keyframe":
                        currentFrame = messageData["framenum"]
                    elif messageData["cmd"] == "setplayername":
                        playerIDToName[messageData["playerNum"]] = clean_name
                        _save_playerinfo(clean_name, "connected", True)
                        _save_playerinfo(
                            clean_name, "playerNum", messageData["playerNum"]
                        )
                    elif (
                        messageData["cmd"] == "startplaying"
                        and messageData["countdown"] == 0
                    ):
                        self.game_started = True
                    elif messageData["cmd"] == "gameover":
                        if not self.game_started:
                            logger.error("game not started on gameover found")
                        else:
                            self.game_over = currentFrame
                            self.additional["gameover_frame"] = currentFrame
                    elif messageData["cmd"] == "gameid":
                        if self.header["gameID"] != messageData["gameID"]:
                            self.gameid = messageData["gameID"]
                            logger.error(
                                "messageData['gameID']: %s != self.header['gameID']: %s",
                                messageData["gameID"],
                                self.header["gameID"],
                            )
                    elif messageData["cmd"] == "playerleft":
                        playername = clean(messageData["playerName"])
                        if messageData["bIntended"] == 0:
                            _save_playerinfo(playername, "timeout", True)
                        if messageData["bIntended"] == 1:
                            _save_playerinfo(playername, "quit", True)
                        if messageData["bIntended"] == 2:
                            _save_playerinfo(playername, "kicked", True)
                    elif messageData["cmd"] == "team":
                        if clean_name in self.script.spectators.keys():
                            continue
                        if messageData["action"] == "team_died":  # team died event
                            deadTeam = messageData["param"]
                            for name, rank in self.players.items():
                                if rank.team == deadTeam:
                                    self.players[name].died = currentFrame
                        elif messageData["action"] == "giveaway":
                            # giving everything away == death
                            self.players[clean_name].died = currentFrame
                    elif messageData["cmd"] == "startpos":
                        if messageData["ready"] == 1:
                            playername = clean(messageData["playerName"])
                            if playername in self.players:
                                self.game_setup["player"][self.players[playername].num][
                                    "startposx"
                                ] = messageData["x"]
                                self.game_setup["player"][self.players[playername].num][
                                    "startposy"
                                ] = messageData["y"]
                                self.game_setup["player"][self.players[playername].num][
                                    "startposz"
                                ] = messageData["z"]
                    elif messageData["cmd"] == "chat":
                        self.additional["chat"].append(
                            {
                                "fromID": messageData["fromID"],
                                "playerName": messageData["playerName"],
                                "toID": messageData["toID"],
                                "message": messageData["message"][:-1],
                                "frame" : currentFrame,
                            }
                        )
                    elif messageData["cmd"] == "luamsg":
                        if messageData["msgid"] == 36:
                            if DEBUG:
                                stats_fp.write(
                                    "{}: >>{}<<\n".format(
                                        messageData["playerNum"], messageData["msg"]
                                    ).encode()
                                )
                            if messageData["msg"][:6] == "$y$CPU":
                                # found BA platform stats
                                stats = self._ba_stats_to_platform_api(
                                    messageData["msg"]
                                )
                                if "cpuName" in stats and "osFamily" in stats:
                                    self.additional.setdefault("ba_platform_stats", {})[
                                        messageData["playerNum"]
                                    ] = stats
                                else:
                                    logger.warning(
                                        "Platform stats missing cpuName or osFamily in %r generated from msg=%r",
                                        stats,
                                        messageData["msg"],
                                    )
                        elif messageData["msgid"] == 49 and messageData[
                            "msg"
                        ].startswith(b"180"):
                            # https://springrts.com/phpbb/viewtopic.php?f=54&t=36150&p=581964#p581964
                            # CursedID-TeamID:awardtype/counter:awardtype/counter: ...
                            # e.g. "180-0:hero/150:hover/803:rezz/28"
                            teamid = re.findall(
                                rb"^180-(\d+):?.*$", messageData["msg"]
                            )[0]
                            cursed_awards = re.findall(
                                rb":((\w+)/(\d+))*", messageData["msg"]
                            )
                            self.additional.setdefault("cursed_awards", {})[teamid] = [
                                (ca[1], ca[2]) for ca in cursed_awards
                            ]
                        elif messageData["msgid"] == 138:
                            # faction change
                            playername = clean(messageData["playerName"])
                            faction = struct.unpack(
                                "<%iB" % (len(messageData["msg"][1:])),
                                messageData["msg"][1:],
                            )
                            logger.debug(
                                "%s(%d) changed faction to '%s'",
                                playername,
                                messageData["playerNum"],
                                faction,
                            )
                            self.additional["faction_change"][playername] = (
                                self.players[playername],
                                faction,
                            )
                        elif messageData["msgid"] == 161:
                            # BA Awards
                            # http://imolarpg.dyndns.org/trac/balatest/browser/trunk/luarules/gadgets/gui_awards.lua?rev=2070#L389
                            # history:
                            # r1786: start sending data from awards gadget to replay site using luauimsg
                            # r1846: use luamsg, change msg numbers from 150-156 to 161-167
                            # r1850: use luarulesmsg, add 1 to each team# to have always positive numbers
                            # r2043: the scores of each award are appended to the team#, separated by ':' (BA 7.91).
                            # r2070: fix typo causing fightKillAward2ndScore to always be 'nil'
                            try:
                                # unfortunately numbers in this sequence were encoded differently, so parsing
                                # is a little tricky, example:
                                # r1850: (len:  31): '\xa17\xa15\xa16\xa25\xa215\xa23\xa33\xa312\xa315\xa40\xa510\xa615\xa74'
                                # r2043: (len: 124): '\xa11:1147\xa10:0\xa10:0\xa21:946348\xa23:nil\xa22:102684\xa33:1.317666888237\xa31:1.2887364625931\xa32:0.75686019659042\xa40\xa51:6590859\xa63:56526.171875\xa70:0'
                                # (unpack'B'): (161, 55, 161, 53, 161, 54, 162, 53, 162, 49, 53, 162, 51, 163, 51, 163, 49, 50, 163, 49, 53, 164, 48, 165, 49, 48, 166, 49, 53, 167, 52)
                                # (unpack'c'): ('\xa1', '7', '\xa1', '5', '\xa1', '6', '\xa2', '5', '\xa2', '1', '5', '\xa2', '3', '\xa3', '3', '\xa3', '1', '2', '\xa3', '1', '5', '\xa4', '0', '\xa5', '1', '0', '\xa6', '1', '5', '\xa7', '4')
                                # award markers are ints 161-167 encoded in one unsigned char, but the
                                # player numbers are ints 0-31 encoded each digit as a single char
                                # ':' is 58 in str_B (and ':' in str_c)
                                str_B = struct.unpack(
                                    "B" * len(messageData["msg"]), messageData["msg"]
                                )
                                str_c = struct.unpack(
                                    "c" * len(messageData["msg"]), messageData["msg"]
                                )
                                start = end = 0
                                awards_data = list()
                                for pos in range(1, len(str_B)):
                                    if int(str_B[pos]) > 160:

                                        def f_(s):
                                            if s.find(b".") >= 0:
                                                return float(s)
                                            else:
                                                return int(s)

                                        end = pos
                                        awards_data.append(str_B[start])
                                        s_ = b"".join(str_c[start + 1 : end]).split(
                                            b":"
                                        )
                                        try:
                                            awards_data.append(
                                                [int(s_[0]) - 1, f_(s_[1])]
                                            )
                                        except IndexError:
                                            # gadget version < r2043 has no ':score' after the teamID
                                            awards_data.append([int(s_[0]) - 1, -1])
                                        except ValueError:
                                            # beware typo in gadget: http://imolarpg.dyndns.org/trac/balatest/changeset/2070
                                            awards_data.append([int(s_[0]) - 1, -2])
                                        start = end
                                else:
                                    awards_data.append(str_B[start])
                                    s_ = b"".join(str_c[start + 1 :]).split(b":")
                                    try:
                                        awards_data.append([int(s_[0]) - 1, f_(s_[1])])
                                    except IndexError:
                                        # gadget version < r2043 has no ':score' after the teamID
                                        awards_data.append([int(s_[0]) - 1, -1])
                                # Substract 1 from each players number.
                                # It was added in gadget to make all numbers positive.
                                awards = {
                                    "ecoKillAward": (
                                        awards_data[1],
                                        awards_data[3],
                                        awards_data[5],
                                    ),  # 161
                                    "fightKillAward": (
                                        awards_data[7],
                                        awards_data[9],
                                        awards_data[11],
                                    ),  # 162
                                    "effKillAward": (
                                        awards_data[13],
                                        awards_data[15],
                                        awards_data[17],
                                    ),  # 163
                                    "cowAward": awards_data[19],  # 164
                                    "ecoAward": awards_data[21],  # 165
                                    "dmgRecAward": awards_data[23],
                                }  # 166
                                if len(awards_data) > 24:
                                    awards["sleepAward"] = awards_data[25]  # 167
                                else:
                                    awards["sleepAward"] = [-1, -1]
                                self.additional["awards"] = awards
                            except Exception as exc:
                                logger.error("FIXME: to broad exception handling.")
                                logger.exception(
                                    "detecting BA Awards, messageData: %r, Exception: %s",
                                    messageData,
                                    exc,
                                )
                        elif messageData["msgid"] == 199:
                            # XTA Awards, 2014-04-01
                            # forum thread: http://springrts.com/phpbb/viewtopic.php?f=71&t=28019&start=120#p555847
                            # XTA_AWARDMARKER,":",isAlive,":",team,":",name,":",kills,":",age
                            # The fields for 'heroes award':
                            #   1: string '\199', identify XTA unit award
                            #   2: isAlive: 1
                            #   3: teamID, owner of the corresponding unit (0)
                            #   4: name of unit to get award (Maverick)
                            #   5: number of kills (27)
                            #   6: age of unit when game ends (4)
                            # The fields for 'lost in service award':
                            #   1: string '\199', identify XTA unit award
                            #   2: isAlive: 0
                            #   3: teamID, owner of the corresponding unit (0)
                            #   4: name of unit to get award (Commander)
                            #   5: number of kills (43)
                            #   6: age of unit when game ends (1)
                            (
                                xta_isAlive,
                                xta_team,
                                xta_name,
                                xta_kills,
                                xta_age,
                            ) = messageData["msg"][2:].split(b":")
                            xtawards = {
                                "isAlive": int(xta_isAlive),
                                "team": int(xta_team),
                                "name": xta_name,
                                "kills": int(xta_kills),
                                "age": int(xta_age),
                            }
                            try:
                                if xtawards not in self.additional["xtawards"]:
                                    self.additional["xtawards"].append(xtawards)
                            except KeyError:
                                self.additional["xtawards"] = [xtawards]
                        else:
                            # logger.debug('unknown luamsg messageData["msgid"]=%r messageData["msg"]=%r', messageData["msgid"], messageData["msg"])
                            pass
                    elif messageData["cmd"] == "mapdraw":
                        if messageData["command"] == 0 and len(messageData["label"]) > 3:
                            self.additional["chat"].append(
                                {
                                    "fromID": messageData["playerNum"],
                                    "playerName": messageData["playerName"],
                                    "toID": 254,
                                    "message": b"Added Point: " + messageData["label"][1:-1],
                                    "frame" : currentFrame,
                                }
                            )
                            
                            self.additional["mapdraw"].append(
                                {
                                    "fromID": messageData["playerNum"],
                                    "playerName": messageData["playerName"],
                                    "message": messageData["label"][1:-1],
                                    "frame" : currentFrame,
                                }
                            )
                            
            except Exception as exc:
                logger.error("FIXME: to broad exception handling.")
                logger.exception("Exception parsing packet '%s': %s", packet, exc)
                # raise e

        if DEBUG:
            kop.close()
            stats_fp.close()

        for pnum, player in self.players.items():
            if not hasattr(player, "connected"):
                self.additional["not_connected"][pnum] = player

    def start_stats_thread(self):
        if not self.stats_thread:
            self.tmp_stats = {}
            self.stats_thread = threading.Thread(
                target=self.get_match_stats, args=(self.filename, self.tmp_stats)
            )
            self.stats_thread.start()
        return self.stats_thread

    def join_stats_thread(self):
        if self.stats_thread:
            self.stats_thread.join()
            self.stats_thread = None
            self.player_stats = self.tmp_stats["player_stats"]
            self.team_stats = self.tmp_stats["team_stats"]
            self.tmp_stats = {}

    @staticmethod
    def get_match_stats(filename, stats):
        return 
        #match_stats_generation = MatchStatsGeneration(filename)
        #stats["player_stats"], stats["team_stats"] = #match_stats_generation.make_stats()

    def parse_player_stats(self):
        if not self.player_stats:
            self.start_stats_thread()
            self.join_stats_thread()
        return self.player_stats

    def parse_team_stats(self):
        if not self.team_stats:
            self.start_stats_thread()
            self.join_stats_thread()
        return self.team_stats

    def player_stats_as_jsonz(self):
        return zlib.compress(ujson.dumps(self.player_stats))

    def team_stats_as_jsonz(self):
        return dict(
            (k, zlib.compress(ujson.dumps(v))) for k, v in self.team_stats.items()
        )


def main(argv=None):
    global DEBUG
    if argv is None:
        argv = sys.argv
    if len(argv) < 1:
        return 0
    #argv = ['20230112_123955_Archsimkats_Valley_V1_105.1.1-1354-g72b2d55 BAR105.sdfz']
    '''
    if len(argv) == 1 or argv[-1] in ["--winning-test", "--winning-test-header"]:
        print(
            "Usage: %s [--winning-test] [--winning-test-header] demofile"
            % (argv[0])
        )
        return 1
    '''

    DEBUG = True  # command line use is always dev intended
    demo_file = Parse_demo_file(argv[-1])
    demo_file.check_magic()
    demo_file.parse()
    #demo_file.upload_platform_stats()

    if "--winning-test-header" in argv:
        print(
            '"versionString","version","winningAllyTeamsSize","numallyteams","winningAllyTeams","gametype",'
            '"autohostname","gameID","unixTime"'
        )
        if "--winning-test" not in argv:
            return 0

    if "--winning-test" in argv:
        print(
            '"{}","{}","{}","{}","{}","{}","{}","{}","{}"'.format(
                demo_file.header["versionString"],
                demo_file.header["version"],
                demo_file.header["winningAllyTeamsSize"],
                demo_file.game_setup["host"]["numallyteams"],
                ",".join(map(str, demo_file.winningAllyTeams)),
                demo_file.game_setup["host"]["gametype"],
                demo_file.game_setup["host"]["autohostname"],
                demo_file.header["gameID"],
                demo_file.header["unixTime"],
            )
        )
        return 0

    pp = pprint.PrettyPrinter(depth=6)
    print("#################### header ##########################")
    pp.pprint(demo_file.header)
    print("################## game_setup ########################")
    pp.pprint(demo_file.game_setup)
    print("############### winningAllyTeams #####################")
    pp.pprint(demo_file.winningAllyTeams)
    print("################## additional ########################")
    if len(demo_file.additional["chat"]) > 4:
        #demo_file.additional["chat"] = "chat removed for shorter output"
        pp.pprint(demo_file.additional["chat"])
    pp.pprint(demo_file.additional)
    return demo_file


if __name__ == "__main__":
    sys.exit(main())
