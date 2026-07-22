import json
import struct
import zlib


class LuaParser:
    def __init__(self):
        self.handlers = self._setup_handlers()

    def _setup_handlers(self):
        return [
            {
                "name": "MOUSE_POS_BROADCAST",
                "validator": lambda buf, s: len(buf) > 0 and buf[0:1] == b"\xa3",
                "parse_start": 0,
                "parser": self._parse_mouse_pos,
            },
            {
                "name": "RESOURCE_STATS",
                "validator": lambda buf, s: len(buf) >= 2 and buf[0:2] == b"\xc2\xa3",
                "parse_start": 0,
                "parser": self._parse_resource_stats,
            },
            {
                "name": "FPS_BROADCAST",
                "validator": lambda buf, s: len(buf) > 0 and buf[0:1] == b"@",
                "parse_start": 0,
                "parser": self._parse_fps,
            },
            {
                "name": "AWARDS",
                "validator": lambda buf, s: len(buf) > 0 and buf[0] == 0xa1,
                "parse_start": 0,
                "parser": self._parse_awards,
            },
            {
                "name": "FACTION_PICKER",
                "validator": lambda buf, s: s.startswith("changeStartUnit"),
                "parse_start": len("changeStartUnit"),
                "parser": self._parse_faction_picker,
            },
            {
                "name": "UNIT_POSITION_LOGGER",
                "validator": lambda buf, s: len(buf) >= 3 and buf[0:3] == b"log",
                "parse_start": 5,
                "parser": self._parse_unit_position_logger,
            },
            {
                "name": "CAMERA_LOCKCAMERA",
                "validator": lambda buf, s: len(buf) > 0 and buf[0:1] == b"=",
                "parse_start": 3,
                "parser": self._parse_camera_lockcamera,
            },
            {
                "name": "ACTIVITY_BROADCAST",
                "validator": lambda buf, s: len(buf) > 0 and buf[0:1] == b"^",
                "parse_start": 0,
                "parser": self._parse_activity_broadcast,
            },
            {
                "name": "SYSTEM_INFO",
                "validator": lambda buf, s: len(buf) >= 3 and buf[0:3] == b"$y$",
                "parse_start": 5,
                "parser": self._parse_system_info,
            },
            {
                "name": "GAME_END",
                "validator": lambda buf, s: s == "pc",
                "parse_start": 0,
                "parser": self._parse_game_end,
            },
            {
                "name": "IDLE_PLAYERS",
                "validator": lambda buf, s: "idleplayers" in s,
                "parse_start": 0,
                "parser": self._parse_idle_players,
            },
            {
                "name": "ALLY_SELECTED_UNITS",
                "validator": lambda buf, s: "cosu" in s,
                "parse_start": 0,
                "parser": self._parse_ally_selected_units,
            },
            {
                "name": "XMAS",
                "validator": lambda buf, s: len(buf) >= 4 and buf[0:4] == b"xmas",
                "parse_start": 4,
                "parser": self._parse_xmas,
            },
            {
                "name": "UNITDEFS",
                "validator": lambda buf, s: len(buf) >= 8 and buf[0:8] == b"unitdefs",
                "parse_start": 9,
                "parser": self._parse_unitdefs,
            },
            {
                "name": "COLORS",
                "validator": lambda buf, s: s.startswith("AutoColors"),
                "parse_start": len("AutoColors"),
                "parser": self._parse_colors,
            },
        ]

    def parse_lua_data(self, msg):
        try:
            str_repr = msg.decode('utf-8', errors='replace')
        except Exception:
            str_repr = msg.decode('latin-1')

        for handler in self.handlers:
            if handler["validator"](msg, str_repr):
                name = handler["name"]
                try:
                    sliced = msg[handler["parse_start"]:]
                    sliced_str = sliced.decode('utf-8', errors='replace')
                    data = handler["parser"](sliced, sliced_str)
                    return {"name": name, "data": data}
                except Exception:
                    return {"name": name, "data": msg[handler["parse_start"]:].hex()}

        prefix = msg[:8].decode('utf-8', errors='replace').rstrip()
        return {"name": f"PREFIX_{prefix}", "data": msg.hex()}

    # --- Individual parsers ---

    def _parse_mouse_pos(self, buf, s):
        click = len(s) > 3 and s[3] == "1"
        positions = []
        pos = 5
        while pos + 4 <= len(buf):
            x, z = struct.unpack("<HH", buf[pos:pos + 4])
            positions.append({"x": x, "z": z})
            pos += 4
        return {"click": click, "positions": positions}

    def _parse_fps(self, buf, s):
        try:
            fps = float(s[3:]) if len(s) > 3 else 0
        except ValueError:
            fps = 0
        return {"fps": fps}

    def _parse_awards(self, buf, s):
        pairs = []
        remaining = s.lstrip("\xa1")
        current = ""
        for ch in remaining:
            if ord(ch) > 160:
                if current:
                    pairs.append(current)
                current = ""
            else:
                current += ch
        if current:
            pairs.append(current)
        return {"awards": pairs}

    def _parse_faction_picker(self, buf, s):
        try:
            unit_def_index = int(s.strip())
            factions = {
                0: "Unknown",
            }
            return {"unitDefIndex": unit_def_index}
        except ValueError:
            return {"raw": s.strip()}

    def _parse_unit_position_logger(self, buf, s):
        try:
            header_end = 0
            occurrence = 0
            for i, byte in enumerate(buf):
                if byte == 0x3b:
                    occurrence += 1
                if occurrence == 4:
                    header_end = i + 1
                    break
            compressed_data = buf[header_end:]
            uncompressed = zlib.decompress(compressed_data)
            raw_data = json.loads(uncompressed.decode('utf-8'))
            return {"positions": raw_data}
        except Exception:
            return {"raw": s[:100]}

    def _parse_camera_lockcamera(self, buf, s):
        if len(buf) >= 2:
            camera_id = buf[0]
            mode = buf[1]
            return {"cameraId": camera_id, "mode": mode}
        return {"raw": s}

    def _parse_activity_broadcast(self, buf, s):
        return {"raw": s}

    def _parse_system_info(self, buf, s):
        info = {}
        for line in s.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                info[key.strip()] = value.strip()
        return info

    def _parse_game_end(self, buf, s):
        return {"gameEnd": True}

    def _parse_idle_players(self, buf, s):
        parts = s.split()
        is_idle = len(parts) > 1 and parts[1] == "1"
        return {"isIdle": is_idle, "raw": s}

    def _parse_ally_selected_units(self, buf, s):
        return {"raw": s}

    def _parse_xmas(self, buf, s):
        is_xmas = s.strip() == "1"
        return {"isXmas": is_xmas}

    def _parse_unitdefs(self, buf, s):
        try:
            uncompressed = zlib.decompress(buf)
            unit_def_ids = json.loads(uncompressed.decode('utf-8'))
            unit_def_ids.insert(0, "")
            return {"unitDefIds": unit_def_ids}
        except Exception:
            return {"raw": s[:100]}

    def _parse_colors(self, buf, s):
        try:
            colors = json.loads(s)
            return {"colors": colors}
        except json.JSONDecodeError:
            return {"raw": s}

    def _parse_resource_stats(self, buf, s):
        pairs = {}
        current = ""
        for ch in s:
            if ord(ch) >= 0xa0:
                if current:
                    pairs.setdefault("_last_key", []).append(current)
                    current = ""
            else:
                current += ch
        if current:
            pairs.setdefault("_last_key", []).append(current)
        return {"raw": s[:100]}
