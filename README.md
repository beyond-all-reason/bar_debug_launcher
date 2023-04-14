# Bar Replay and Debug Launcher
A simple debug launcher for testing engines, lobbies and games, and for playing replays. 


## Usage
1. Install engines by downloading from `https://github.com/beyond-all-reason/spring/releases` and unzipping them into `BAR/data/engine`
2. Copy the `bar_demo_debug_launcher.exe` from this repository next to wherever your Beyond-All-Reason.exe is
3. Right click any replay in your BAR/data/demos folder, and and set the "Open With" to "bar_demo_debug_launcher.exe". You can now double-click any replay and it should download all that is needed and start the replay!.
4. On Windows, start `bar_debug_launcher.exe`, and select the engine version you would like to test from the dropdown menu
5. On Linux, open a terminal, navigate to where Beyond-All-Reason is, and type `python bar_debug_launcher.py` to start it. 
6. You can test BAR with Chobby via the launcher, by selecting the option: `Spring-launcher with rapid://byar-chobby:test`
7. You can test launching the engine directly with a game and a map, and even specify custom modoptions for your start


![kép](https://user-images.githubusercontent.com/109391/198118232-67bb8956-d976-4c88-9ade-da48e1a735e7.png)


### Dev Notes:

Exe is built without a console:
pyinstaller --onefile --icon=bar-icon.ico --noconsole BAR_Debug_Launcher.py