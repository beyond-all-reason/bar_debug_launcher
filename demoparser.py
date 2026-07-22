# This file is part of the "spring relay site / srs" program. It is published
# under the GPLv3.
#
# Copyright (C) 2016-2020 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#
# The code in this file was originally part of the SpringLadder project
# (https://github.com/renemilk/SpringLadder) by koshi/renemilk and
# BrainDamage. SpringLadder is licensed as "Do What The Fuck You Want To
# Public License, Version 2".
#
# Future modifications of the code as part of the "spring relay site" project
# are licensed as GPLv3 (see above).
#

import logging
import struct
import zlib

logger = logging.getLogger(__name__)


class PlayerDict(dict):
    def __getitem__(self, item):
        return dict.__getitem__(self, item) if item in self else None


class Demoparser(object):
    def __init__(self):
        self.players = PlayerDict()

    def write(self, varis, *keys):
        blacklist = ("newframe",)
        returnval = dict()
        if varis["cmd"] in blacklist:
            return
        for key in keys:
            item = varis[key]
            returnval[key] = item
        return returnval

    def parsePacket(self, packet):
        if not packet or not packet["data"]:
            return
        data = packet["data"]

        cmd = data[0]
        data = data[1:]
        if cmd == 1:
            cmd = "keyframe"
            framenum = struct.unpack("<i", data)[0]
            return self.write(locals(), "cmd", "framenum")
        elif cmd == 2:
            cmd = "newframe"
            return self.write(locals(), "cmd")
        elif cmd == 3:
            cmd = "quit"
            size = struct.unpack("<H", data[:2])[0]
            reason = data[2:]
            return self.write(locals(), "cmd", "size", "reason")
        elif cmd == 4:
            cmd = "startplaying"
            countdown = struct.unpack("<I", data)[0]
            return self.write(locals(), "cmd", "countdown")
        elif cmd == 5:
            cmd = "setplayernum"
            playerNum = data[0]
            return self.write(locals(), "cmd", "playerNum")
        elif cmd == 6:
            cmd = "setplayername"
            size, playerNum = struct.unpack("<BB", data[:2])
            playerName = data[2:]
            if playerNum not in self.players:
                self.players[playerNum] = playerName.strip(b"\0")
            return self.write(locals(), "cmd", "size", "playerNum", "playerName")
        elif cmd == 7:
            cmd = "chat"
            size, fromID, toID = struct.unpack("<3B", data[:3])
            message = data[3:]
            playerName = self.players[fromID] or ""
            return self.write(
                locals(), "cmd", "size", "fromID", "playerName", "toID", "message"
            )
        elif cmd == 8:
            cmd = "randseed"
            randSeed = struct.unpack("<I", data)[0]
            return self.write(locals(), "cmd", "randSeed")
        elif cmd == 9:
            cmd = "gameid"
            gameID = (
                "%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x"
                % struct.unpack("16B", data)
            )
            return self.write(locals(), "cmd", "gameID")
        elif cmd == 10:
            cmd = "path_checksum"
            playerNum = data[0]
            checksum = struct.unpack("<I", data[1:5])[0]
            playerName = self.players[playerNum] or ""
            return self.write(locals(), "cmd", "playerNum", "playerName", "checksum")
        elif cmd == 11:
            cmd = "command"
            size, playerNum, cmdID, options = struct.unpack("<hBiB", data[:8])
            params = struct.unpack("<%if" % ((len(data) - 8) / 4), data[8:])
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd",
                "size",
                "playerNum",
                "playerName",
                "cmdID",
                "options",
                "params",
            )
        elif cmd == 12:
            cmd = "select"
            size, playerNum = struct.unpack("<hB", data[:3])
            selectedUnitIDs = struct.unpack("<%ih" % ((len(data) - 3) / 2), data[3:])
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "selectedUnitIDs"
            )
        elif cmd == 13:
            cmd = "pause"
            playerNum, bPaused = struct.unpack("<BB", data)
            playerName = self.players[playerNum] or ""
            return self.write(locals(), "cmd", "playerNum", "playerName", "bPaused")
        elif cmd == 14:
            cmd = "aicommand"
            size, playerNum, aiId, aiTeamId, unitId, commandId, timeout, options, numParams = struct.unpack('<hBBBhiIBI', data[:20])
            params = struct.unpack('<%if' % numParams, data[20:20 + 4 * numParams]) if numParams > 0 else ()
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), 'cmd', 'size', 'playerNum', 'playerName', 'aiId', 'aiTeamId',
                'unitId', 'commandId', 'timeout', 'options', 'numParams', 'params'
            )
        elif cmd == 15:
            cmd = "aicommands"
            msgsize, playerNum, aiId, pairwise, refCmdId, refCmdOpts, refCmdSize, unitCount = struct.unpack('<hBBBIbHh', data[:14])
            unitIds = struct.unpack('<%dh' % unitCount, data[14:14 + 2 * unitCount])
            pos = 14 + 2 * unitCount
            commandCount = struct.unpack('<H', data[pos:pos + 2])[0]
            pos += 2
            commands = []
            for i in range(commandCount):
                id_ = refCmdId if refCmdId != 0 else struct.unpack('<i', data[pos:pos + 4])[0]
                pos += 4 if refCmdId == 0 else 0
                optionBitmask = refCmdOpts if (refCmdOpts & 0xFF) != 255 else data[pos]
                pos += 1 if (refCmdOpts & 0xFF) == 255 else 0
                size_ = refCmdSize if refCmdSize != 65535 else struct.unpack('<H', data[pos:pos + 2])[0]
                pos += 2 if refCmdSize == 65535 else 0
                params = struct.unpack('<%if' % size_, data[pos:pos + 4 * size_]) if size_ > 0 else ()
                pos += 4 * size_
                commands.append((id_, optionBitmask, size_, params))
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), 'cmd', 'msgsize', 'playerNum', 'playerName', 'aiId', 'pairwise',
                'refCmdId', 'refCmdOpts', 'refCmdSize', 'unitIds', 'commands'
            )
        elif cmd == 16:
            cmd = "aishare"
            size = struct.unpack("<H", data[:2])[0]
            playerNum, aiId, sourceTeam, destTeam = struct.unpack("<4B", data[2:6])
            metal, energy = struct.unpack("<ff", data[6:14])
            unitIDs = struct.unpack("<%dh" % ((len(data) - 14) // 2), data[14:]) if len(data) > 14 else ()
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd", "size", "playerNum", "playerName", "aiId",
                "sourceTeam", "destTeam", "metal", "energy", "unitIDs"
            )
        elif cmd == 17:
            cmd = "memdump"
            raw_size = len(data)
            return self.write(locals(), "cmd", "raw_size")
        elif cmd == 19:
            cmd = "user_speed"
            playerNum, userSpeed = struct.unpack("<Bf", data)
            playerName = self.players[playerNum] or ""
            return self.write(locals(), "cmd", "playerNum", "playerName", "userSpeed")
        elif cmd == 20:
            cmd = "internal_speed"
            internalSpeed = struct.unpack("<f", data)[0]
            return self.write(locals(), "cmd", "internalSpeed")
        elif cmd == 21:
            cmd = "cpu_usage"
            cpuUsage = struct.unpack("<f", data)[0]
            return self.write(locals(), "cmd", "cpuUsage")
        elif cmd == 22:
            cmd = "direct_control"
            playerNum = data[0]
            playerName = self.players[playerNum] or ""
            return self.write(locals(), "cmd", "playerNum", "playerName")
        elif cmd == 23:
            cmd = "dc_update"
            playerNum, status, heading, pitch = struct.unpack("<BBhh", data)
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName", "status", "heading", "pitch"
            )
        elif cmd == 25:
            cmd = "attemptconnect_legacy"
            size = struct.unpack("<H", data[:2])[0] if len(data) >= 2 else 0
            remaining = data[2:] if len(data) > 2 else b""
            parts = remaining.split(b"\0", 3)
            name = parts[0] if len(parts) > 0 else b""
            password = parts[1] if len(parts) > 1 else b""
            version = parts[2].strip(b"\0") if len(parts) > 2 else b""
            platform = parts[3].strip(b"\0") if len(parts) > 3 else b""
            return self.write(locals(), "cmd", "size", "name", "password", "version", "platform")
        elif cmd == 26:
            cmd = "share"
            playerNum, shareTeam, shareUnits, shareMetal, shareEnergy = struct.unpack(
                "<3Bff", data
            )
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd",
                "playerNum",
                "playerName",
                "shareTeam",
                "shareUnits",
                "shareMetal",
                "shareEnergy",
            )
        elif cmd == 27:
            cmd = "setshare"
            playerNum, team, metalShareFraction, energyShareFraction = struct.unpack(
                "<BBff", data
            )
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd",
                "playerNum",
                "playerName",
                "team",
                "metalShareFraction",
                "energyShareFraction",
            )
        elif cmd == 28:
            cmd = "sendself_playerstat"
            raw_size = len(data)
            return self.write(locals(), "cmd", "raw_size")
        elif cmd == 29:
            cmd = "playerstat"
            playerNum = data[0]
            numCommands, unitCommands, mousePixels, mouseClicks, keyPresses = struct.unpack("<5i", data[1:21])
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName",
                "numCommands", "unitCommands", "mousePixels", "mouseClicks", "keyPresses"
            )
        elif cmd == 30:
            cmd = "gameover"
            size, playerNum = struct.unpack("<BB", data[:2])
            winningAllyTeams = list(data[2:])
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "winningAllyTeams"
            )
        elif cmd == 31:
            cmd = "mapdraw_old"
            size, playerNum, command = struct.unpack("<3B", data[:3])
            data = data[3:]
            if command == 0:
                x, z = struct.unpack("<hh", data[:4])
                label = data[4:]
                playerName = self.players[playerNum] or ""
                return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command", "x", "z", "label")
            elif command == 1:
                x, z = struct.unpack("<hh", data)
                playerName = self.players[playerNum] or ""
                return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command", "x", "z")
            elif command == 2:
                x1, z1, x2, z2 = struct.unpack("<4h", data[:8])
                playerName = self.players[playerNum] or ""
                return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command", "x1", "z1", "x2", "z2")
            playerName = self.players[playerNum] or ""
            return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command")
        elif cmd == 32:
            cmd = "mapdraw"
            size, playerNum, command = struct.unpack("<3B", data[:3])
            data = data[3:]
            if command == 0:
                x, z = struct.unpack("<ii", data[:8])
                fromLua = bool(data[8]) if len(data) > 8 else False
                label = data[9:].decode('utf-8', errors='replace').strip('\x00') if len(data) > 9 else ""
                playerName = self.players[playerNum] or ""
                return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command", "x", "z", "fromLua", "label")
            elif command == 1:
                x, z = struct.unpack("<ii", data[:8])
                playerName = self.players[playerNum] or ""
                return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command", "x", "z")
            elif command == 2:
                x1, z1, x2, z2 = struct.unpack("<4i", data[:16])
                fromLua = bool(data[16]) if len(data) > 16 else False
                playerName = self.players[playerNum] or ""
                return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command", "x1", "z1", "x2", "z2", "fromLua")
            playerName = self.players[playerNum] or ""
            return self.write(locals(), "cmd", "size", "playerNum", "playerName", "command")
        elif cmd == 33:
            cmd = "syncresponse"
            playerNum, frameNum, checksum = struct.unpack("<BiI", data)
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName", "frameNum", "checksum"
            )
        elif cmd == 35:
            cmd = "systemmsg"
            size, playerNum = struct.unpack("<HHB", data[:5])[:2]
            message = data[2:]
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "message"
            )
        elif cmd == 36:
            cmd = "startpos"
            playerNum, team, ready, x, y, z = struct.unpack(
                "<3B3f", data
            )
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd",
                "playerNum",
                "playerName",
                "team",
                "ready",
                "x",
                "y",
                "z",
            )
        elif cmd == 38:
            cmd = "playerinfo"
            playerNum, cpuUsage, ping = struct.unpack(
                "<BfI", data
            )
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName", "cpuUsage", "ping"
            )
        elif cmd == 39:
            cmd = "playerleft"
            playerNum, bIntended = struct.unpack(
                "<BB", data
            )
            readableIntended = {0: "lost connection", 1: "left", 2: "forced (kicked)"}[
                bIntended
            ]
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd",
                "playerNum",
                "playerName",
                "bIntended",
                "readableIntended",
            )
        elif cmd == 41:
            cmd = "sd_chkrequest"
            playerNum = data[0] if len(data) > 0 else 0
            frameNum = struct.unpack("<i", data[1:5])[0] if len(data) >= 5 else 0
            playerName = self.players.get(playerNum, "") or ""
            return self.write(locals(), "cmd", "playerNum", "playerName", "frameNum")
        elif cmd == 42:
            cmd = "sd_chkresponse"
            size = struct.unpack("<H", data[:2])[0] if len(data) >= 2 else 0
            playerNum = data[2] if len(data) > 2 else 0
            inSync = data[3] if len(data) > 3 else 0
            frameNum = struct.unpack("<i", data[4:8])[0] if len(data) >= 8 else 0
            playerName = self.players.get(playerNum, "") or ""
            return self.write(locals(), "cmd", "size", "playerNum", "playerName", "inSync", "frameNum")
        elif cmd == 43:
            cmd = "sd_blkrequest"
            playerNum = data[0] if len(data) > 0 else 0
            frameNum = struct.unpack("<i", data[1:5])[0] if len(data) >= 5 else 0
            playerName = self.players.get(playerNum, "") or ""
            return self.write(locals(), "cmd", "playerNum", "playerName", "frameNum")
        elif cmd == 44:
            cmd = "sd_blkresponse"
            size = struct.unpack("<H", data[:2])[0] if len(data) >= 2 else 0
            playerNum = data[2] if len(data) > 2 else 0
            inSync = data[3] if len(data) > 3 else 0
            frameNum = struct.unpack("<i", data[4:8])[0] if len(data) >= 8 else 0
            numChunks = struct.unpack("<i", data[8:12])[0] if len(data) >= 12 else 0
            playerName = self.players.get(playerNum, "") or ""
            return self.write(locals(), "cmd", "size", "playerNum", "playerName", "inSync", "frameNum", "numChunks")
        elif cmd == 45:
            cmd = "sd_reset"
            return self.write(locals(), "cmd")
        elif cmd == 46:
            cmd = "gamestate_dump"
            frameNum = struct.unpack("<i", data)[0]
            return self.write(locals(), "cmd", "frameNum")
        elif cmd == 49:
            cmd = "logmsg"
            size, playerNum, logMsgLvl = struct.unpack("<HBB", data[:4])
            msgData = data[4:].decode('utf-8', errors='replace').strip('\x00')
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "logMsgLvl", "msgData"
            )
        elif cmd == 50:
            cmd = "luamsg"
            size, playerNum, script, mode = struct.unpack("<HBHB", data[:6])
            msg = data[6:]
            playerName = self.players[playerNum] or ""
            (msgid,) = struct.unpack("<B", msg[:1])
            return self.write(
                locals(),
                "cmd",
                "size",
                "playerNum",
                "playerName",
                "script",
                "mode",
                "msg",
                "msgid",
            )
        elif cmd == 51:
            cmd = "team"
            playerNum, action = struct.unpack("<BB", data[:2])
            param = data[2] if len(data) > 2 and action != 2 else None
            if action == 1:
                action = "giveaway"
            elif action == 2:
                action = "resign"
            elif action == 3:
                action = "join_team"
            elif action == 4:
                action = "team_died"
            elif action == 5:
                action = "ai_created"
            elif action == 6:
                action = "ai_destroyed"
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName", "action", "param"
            )
        elif cmd == 52:
            cmd = "gamedata"
            size, compressedSize = struct.unpack("<HH", data[:4])
            setupText = zlib.decompress(data[4:4 + compressedSize])
            remaining = data[4 + compressedSize:]
            if len(remaining) == 12:
                mapChecksum, modChecksum, randomSeed = struct.unpack("<3i", remaining)
                return self.write(
                    locals(),
                    "cmd",
                    "size",
                    "compressedSize",
                    "setupText",
                    "mapChecksum",
                    "modChecksum",
                    "randomSeed",
                )
            elif len(remaining) == 132:
                mapChecksum = remaining[:64].hex()
                modChecksum = remaining[64:128].hex()
                randomSeed = struct.unpack("<i", remaining[128:132])[0]
                return self.write(
                    locals(),
                    "cmd",
                    "size",
                    "compressedSize",
                    "setupText",
                    "mapChecksum",
                    "modChecksum",
                    "randomSeed",
                )
            else:
                data_str = "unparsed, old replay format"
                return self.write(locals(), "cmd", "data_str")
        elif cmd == 53:
            cmd = "alliance"
            playerNum, otherAllyTeam, allianceState = struct.unpack(
                "<3B", data
            )
            readableAllianceState = {0: "not allied", 1: "allied"}[allianceState]
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(),
                "cmd",
                "playerNum",
                "playerName",
                "otherAllyTeam",
                "allianceState",
                "readableAllianceState",
            )
        elif cmd == 54:
            cmd = "ccommand"
            size, playerNum = struct.unpack("<Hi", data[:6])
            command, extra = data[6:].split(b"\0", 1)
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "command", "extra"
            )
        elif cmd == 60:
            cmd = "teamstat"
            teamNum = data[0]
            (frame, metalUsed, energyUsed, metalProduced, energyProduced,
             metalExcess, energyExcess, metalReceived, energyReceived,
             metalSent, energySent, damageDealt, damageReceived,
             unitsProduced, unitsDied, unitsReceived, unitsSent,
             unitsCaptured, unitsOutCaptured, unitsKilled) = struct.unpack("<20i", data[1:81])
            return self.write(
                locals(), "cmd", "teamNum",
                "frame", "metalUsed", "energyUsed", "metalProduced", "energyProduced",
                "metalExcess", "energyExcess", "metalReceived", "energyReceived",
                "metalSent", "energySent", "damageDealt", "damageReceived",
                "unitsProduced", "unitsDied", "unitsReceived", "unitsSent",
                "unitsCaptured", "unitsOutCaptured", "unitsKilled"
            )
        elif cmd == 61:
            cmd = "clientdata"
            size = struct.unpack("<H", data[:2])[0]
            playerNum = data[2]
            compressed = data[3:size]
            setupText = zlib.decompress(compressed).decode('utf-8', errors='replace').strip('\x00')
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "setupText"
            )
        elif cmd == 65:
            cmd = "attemptconnect"
            size = struct.unpack("<H", data[:2])[0]
            netversion = struct.unpack("<H", data[2:4])[0]
            remaining = data[4:]
            parts = remaining.split(b"\0", 3)
            name = parts[0] if len(parts) > 0 else b""
            password = parts[1] if len(parts) > 1 else b""
            version = parts[2].strip(b"\0") if len(parts) > 2 else b""
            platform = parts[3].strip(b"\0") if len(parts) > 3 else b""
            reconnect = data[size - 2] if len(data) >= size - 1 else 0
            netloss = data[size - 1] if len(data) >= size else 0
            return self.write(
                locals(), "cmd", "size", "netversion", "name", "password", "version", "platform", "reconnect", "netloss"
            )
        elif cmd == 66:
            cmd = "reject_connect"
            size = struct.unpack("<H", data[:2])[0]
            reason = data[2:].decode('utf-8', errors='replace').strip('\x00')
            return self.write(locals(), "cmd", "size", "reason")
        elif cmd == 70:
            cmd = "ai_created"
            size, playerNum, whichSkirmishAI, team = struct.unpack("<4B", data[:4])
            name = data[4:].decode('utf-8', errors='replace').strip('\x00')
            playerName = self.players.get(playerNum, "") or ""
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "whichSkirmishAI", "team", "name"
            )
        elif cmd == 71:
            cmd = "ai_state_changed"
            playerNum, whichSkirmishAI, newState = struct.unpack("<3B", data)
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName", "whichSkirmishAI", "newState"
            )
        elif cmd == 72:
            cmd = "request_teamstat"
            teamNum, statFrameNum = struct.unpack("<BH", data)
            return self.write(locals(), "cmd", "teamNum", "statFrameNum")
        elif cmd == 75:
            cmd = "create_newplayer"
            size, playerNum, spectator, teamNum = struct.unpack("<hBBB", data[:5])
            playerName = data[5:].decode('utf-8', errors='replace').strip('\x00')
            if playerNum not in self.players:
                self.players[playerNum] = playerName.encode()
            return self.write(
                locals(), "cmd", "size", "playerNum", "playerName", "spectator", "teamNum"
            )
        elif cmd == 76:
            cmd = "aicommand_tracked"
            size, playerNum, aiId, unitId, commandId, options, aiCommandId = struct.unpack('<hBBhIBi', data[:15])
            remaining = len(data) - 15
            numParams = remaining // 4 if remaining > 0 else 0
            params = struct.unpack('<%if' % numParams, data[15:15 + 4 * numParams]) if numParams > 0 else ()
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), 'cmd', 'size', 'playerNum', 'playerName', 'aiId', 'unitId',
                'commandId', 'options', 'aiCommandId', 'numParams', 'params'
            )
        elif cmd == 77:
            cmd = "game_frame_progress"
            frameNum = struct.unpack("<i", data)[0]
            return self.write(locals(), "cmd", "frameNum")
        elif cmd == 78:
            cmd = "ping"
            playerNum, pingTag, localTime = struct.unpack("<BBf", data)
            playerName = self.players[playerNum] or ""
            return self.write(
                locals(), "cmd", "playerNum", "playerName", "pingTag", "localTime"
            )
        else:
            pass
