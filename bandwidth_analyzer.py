from collections import defaultdict


PACKET_DIRECTIONS = {
    "keyframe": "server_to_client",
    "newframe": "server_to_client",
    "quit": "client_to_server",
    "startplaying": "server_to_client",
    "setplayernum": "client_to_server",
    "setplayername": "client_to_server",
    "chat": "broadcast",
    "randseed": "server_to_client",
    "gameid": "server_to_client",
    "path_checksum": "client_to_server",
    "command": "client_to_server",
    "select": "client_to_server",
    "pause": "client_to_server",
    "aicommand": "server_to_client",
    "aicommands": "server_to_client",
    "aishare": "server_to_client",
    "memdump": "unknown",
    "user_speed": "client_to_server",
    "internal_speed": "server_to_client",
    "cpu_usage": "server_to_client",
    "direct_control": "client_to_server",
    "dc_update": "client_to_server",
    "attemptconnect_legacy": "client_to_server",
    "share": "client_to_server",
    "setshare": "client_to_server",
    "sendself_playerstat": "client_to_server",
    "playerstat": "server_to_client",
    "gameover": "server_to_client",
    "mapdraw_old": "client_to_server",
    "mapdraw": "client_to_server",
    "syncresponse": "server_to_client",
    "systemmsg": "server_to_client",
    "startpos": "client_to_server",
    "playerinfo": "server_to_client",
    "playerleft": "server_to_client",
    "sd_chkrequest": "sync_debug",
    "sd_chkresponse": "sync_debug",
    "sd_blkrequest": "sync_debug",
    "sd_blkresponse": "sync_debug",
    "sd_reset": "sync_debug",
    "gamestate_dump": "server_to_client",
    "logmsg": "server_to_client",
    "luamsg": "broadcast",
    "team": "broadcast",
    "gamedata": "server_to_client",
    "alliance": "broadcast",
    "ccommand": "client_to_server",
    "teamstat": "server_to_client",
    "clientdata": "server_to_client",
    "attemptconnect": "client_to_server",
    "reject_connect": "server_to_client",
    "ai_created": "server_to_client",
    "ai_state_changed": "server_to_client",
    "request_teamstat": "client_to_server",
    "create_newplayer": "server_to_client",
    "aicommand_tracked": "server_to_client",
    "game_frame_progress": "server_to_client",
    "ping": "bidirectional",
}


class BandwidthAnalyzer:
    def __init__(self):
        self.packet_stats = defaultdict(lambda: {
            "count": 0,
            "total_bytes": 0,
            "min_bytes": float("inf"),
            "max_bytes": 0,
        })
        self.player_outbound = defaultdict(lambda: defaultdict(int))
        self.player_inbound = defaultdict(int)
        self.player_types_outbound = defaultdict(lambda: defaultdict(lambda: {"bytes": 0, "count": 0}))
        self.player_names = {}
        self.total_packets = 0
        self.total_bytes = 0
        self.lua_stats = defaultdict(lambda: {"count": 0, "total_bytes": 0})
        self.game_duration = 0

    def record_packet(self, parsed, raw_size, player_num=None):
        cmd = parsed.get("cmd", "unknown") if parsed else "unknown"
        direction = PACKET_DIRECTIONS.get(cmd, "unknown")

        stats = self.packet_stats[cmd]
        stats["count"] += 1
        stats["total_bytes"] += raw_size
        stats["min_bytes"] = min(stats["min_bytes"], raw_size)
        stats["max_bytes"] = max(stats["max_bytes"], raw_size)
        stats["direction"] = direction

        self.total_packets += 1
        self.total_bytes += raw_size

        if player_num is not None:
            player_num = int(player_num)
            self.player_outbound[player_num][cmd] += raw_size
            self.player_types_outbound[player_num][cmd]["bytes"] += raw_size
            self.player_types_outbound[player_num][cmd]["count"] += 1

            if direction in ("server_to_client", "broadcast", "bidirectional"):
                for other_player in self.player_names:
                    try:
                        op = int(other_player)
                    except (ValueError, TypeError):
                        continue
                    if op != player_num:
                        self.player_inbound[op] += raw_size

        if cmd == "setplayername" and "playerNum" in parsed and "playerName" in parsed:
            pn = parsed["playerNum"]
            name = parsed["playerName"]
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace").strip("\x00")
            self.player_names[int(pn)] = name

        if cmd == "luamsg":
            msg = parsed.get("msg", b"")
            self.lua_stats["raw_luamsg"]["count"] += 1
            self.lua_stats["raw_luamsg"]["total_bytes"] += raw_size

    def record_lua_classification(self, lua_type, raw_size):
        self.lua_stats[lua_type]["count"] += 1
        self.lua_stats[lua_type]["total_bytes"] += raw_size

    def set_game_duration(self, duration_seconds):
        self.game_duration = duration_seconds if duration_seconds > 0 else 1

    def generate_report(self):
        bps_scale = 8.0 / self.game_duration if self.game_duration > 0 else 0

        per_packet_type = {}
        for pkt_type, stats in sorted(self.packet_stats.items(), key=lambda x: x[1]["total_bytes"], reverse=True):
            avg_bytes = stats["total_bytes"] / stats["count"] if stats["count"] > 0 else 0
            per_packet_type[pkt_type] = {
                "count": stats["count"],
                "total_bytes": stats["total_bytes"],
                "avg_bytes": round(avg_bytes, 2),
                "min_bytes": stats["min_bytes"] if stats["min_bytes"] != float("inf") else 0,
                "max_bytes": stats["max_bytes"],
                "direction": stats["direction"],
                "bandwidth_bps": round(stats["total_bytes"] * bps_scale, 2),
                "bandwidth_pct": round(stats["total_bytes"] / self.total_bytes * 100, 2) if self.total_bytes > 0 else 0,
            }

        per_player = {}
        all_players = set(list(self.player_outbound.keys()) + list(self.player_inbound.keys()))
        for pn in sorted(all_players, key=lambda x: int(x)):
            outbound_bytes = sum(self.player_outbound[pn].values())
            inbound_bytes = self.player_inbound.get(pn, 0)
            top_types = sorted(
                self.player_types_outbound.get(pn, {}).items(),
                key=lambda x: x[1]["bytes"],
                reverse=True,
            )[:5]
            per_player[str(pn)] = {
                "playerName": self.player_names.get(pn, "unknown"),
                "outbound_bytes": outbound_bytes,
                "inbound_bytes": inbound_bytes,
                "outbound_bps": round(outbound_bytes * bps_scale, 2),
                "inbound_bps": round(inbound_bytes * bps_scale, 2),
                "top_outbound_types": [
                    {"type": t, "bytes": d["bytes"], "count": d["count"]}
                    for t, d in top_types
                ],
            }

        lua_breakdown = {}
        for lua_type, stats in sorted(self.lua_stats.items(), key=lambda x: x[1]["total_bytes"], reverse=True):
            if lua_type == "raw_luamsg":
                continue
            lua_breakdown[lua_type] = {
                "count": stats["count"],
                "total_bytes": stats["total_bytes"],
            }

        return {
            "total_demo_stream_bytes": self.total_bytes,
            "total_packets": self.total_packets,
            "game_duration_seconds": self.game_duration,
            "per_packet_type": per_packet_type,
            "per_player": per_player,
            "lua_message_breakdown": lua_breakdown,
        }
