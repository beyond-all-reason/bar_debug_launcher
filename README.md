# Bar Replay and Debug Launcher
A simple debug launcher for testing engines, lobbies and games, and for playing replays. 

## Installation
Make sure you have 7zip installed into your program files at `C:\Program Files\7-Zip\7z.exe`

Get it from the releases page: https://github.com/beyond-all-reason/bar_debug_launcher/releases

And place it next to wherever your `Beyond-All-Reason.exe` is

## Associating replays to auto-start on double click

Right click any replay in your BAR/data/demos folder, and and set the "Open With" to "bar_demo_debug_launcher.exe". You can now double-click any replay and it should download all that is needed and start the replay!.

## Choosing a replay and starting it directly

Click the "Open and launch a replay" button, select it, and it should be loaded. 

## Watching replays and loading savegames in a specific engine version without opening new engine windows. 

1. Select the engine version you wish to use.
2. Use Spring-launcher with rapid://byar-chobby:test
3. Click start with the above selected settings 

## Developing the BAR Chobby lobby

1. Make sure you have git cloned https://github.com/beyond-all-reason/BYAR-Chobby into BAR/data/games/BYAR-Chobby.sdd
2. Select the engine version you want to use
3. Select BYAR Chobby $VERSION as the game/menu you want to run
4. Click start with the above selected settings 

Note that you wont have automatic downloads of game updates and maps in this mode!

## Testing and developing the BAR game

1. Make sure you have git cloned https://github.com/beyond-all-reason/Beyond-All-Reason into BAR/data/games/BAR.sdd
2. Select the engine version you want to use
3. Select the game/menu Beyond All Reason $VERSION
4. Click start with the above selected settings 

## Testing maps quickly

1. Select the engine version you want to use
2. Select the game/menu rapid://byar:test
4. Select the map you want from the dropdown, if it doesnt appear, choose your own once ingame. 
5. Choose your map in the engine splash screen, if you didnt choose above

## Testing modoptions

Same as testing and developing the BAR game, but you can can specify a list of modoptions in the Additinoal modoptions field. 

## Testing different engines
All engines should go into bar/data/engine/  

Each into their own subfolder

They will then appear in the engine selector dropdown in the BAR debug launcher

## Attaching debuggers and development tools like VSCode

1. Select all the options you want
2. Copy paste the generated command line into your IDE

![kép](https://user-images.githubusercontent.com/109391/198118232-67bb8956-d976-4c88-9ade-da48e1a735e7.png)

## Debugging the Debug Launcher itself

Use the BAR_Demo_Debug_Launcher_console.exe to get a console, open a ticket for any bug you may find. 

### Dev Notes:

Exe is built without a console:
pyinstaller --onefile --icon=bar-icon.ico --noconsole BAR_Debug_Launcher.py

## Demo Replay Packet Analyzer

Analyze `.sdfz` demo replay files from the command line to inspect packet traffic, bandwidth usage, and Lua message breakdowns.

### Usage

```bash
python parse_demo_file.py [--bandwidth] demofile.sdfz
```

`--bandwidth` — Output a JSON report with per-packet-type bandwidth stats, per-player traffic, and Lua message classification. Without this flag, the full parsed demo contents are printed.

### Example

```bash
python parse_demo_file.py --bandwidth path/to/replay.sdfz
```

The JSON report includes:
- **total_packets** / **total_demo_stream_bytes** — overall stream size
- **per_packet_type** — packet count, bytes, bandwidth %, and direction (client_to_server / server_to_client / broadcast / sync_debug) for each of the 30+ packet types
- **per_player** — outbound/inbound bytes and bps per player, with top-5 packet types per player
- **lua_message_breakdown** — classified Lua messages (CAMERA_LOCKCAMERA, RESOURCE_STATS, FPS_BROADCAST, etc.) with counts and bytes
