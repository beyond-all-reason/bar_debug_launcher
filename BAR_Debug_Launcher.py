import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter.messagebox import showinfo
#from ttkthemes import ThemedTk
from calendar import month_name

import os
import re
import subprocess
import shlex
import sys
import shutil
import requests
import py7zr

from parse_demo_file import Parse_demo_file

#Try to figure out the BAR install path:
barinstallpath = os.path.abspath(os.path.dirname(sys.argv[0])) 
cwd = os.getcwd()
#This is needed for double-click launches, as then the CWD is wherever the demo file is
os.chdir(barinstallpath)
print("Exe path", barinstallpath, "cwd", cwd)
print("Setting path to", barinstallpath)

def exitpause(message = ""):
    print("Terminating: ", message)
    os.system("pause")
    exit(1)

#DEBUGGINGS
#sys.argv.append("C:/Users/psarkozy/Downloads/20230112_123955_Archsimkats_Valley_V1_105.1.1-1354-g72b2d55 BAR105.sdfz")
#barinstallpath = "C:/Users/psarkozy/AppData/Local/Programs/Beyond-All-Reason"
#os.chdir(barinstallpath)

modinfos = {}
enginepaths = []
enginedirs = {}
datafolder = 'data'
enginefolder = 'data\\engine'
maps = ['Ill choose my own once ingame']


def parsemodinfo(path):
    modinfo = {}
    for line in open(path).readlines():
        line = line.partition('--')[0].strip().strip(',').replace('"', '').replace('\'', '')  # uncomment, dequote
        if '=' in line:
            line = line.partition('=')
            modinfo[line[0].strip()] = line[2].strip()
    return modinfo


def parsemaps():
    global maps
    mapdir = 'data\\maps'
    if os.path.exists(mapdir):
        for mapfile in os.listdir(mapdir):
            if mapfile.lower().endswith('.sd7') and '.' not in mapfile[
                                                               :-4] and ' ' not in mapfile and '-' not in mapfile and '_' in mapfile:
                mapfile = mapfile[:-4]
                mapfile = '_'.join([x[0].upper() + x[1:] for x in mapfile.split('_')])
                maps.append(mapfile)
                print('Found map', mapfile)


def refresh():
    global modinfos
    global enginepaths
    global enginedirs
    if os.path.exists(enginefolder):
        for file in os.listdir(enginefolder):
            enginedir = os.path.join(enginefolder, file)
            if os.path.isdir(enginedir) and os.path.exists(os.path.join(enginedir, 'spring.exe')):
                enginepath = os.path.join(enginedir, 'spring.exe')
                print("Found engine in path:", enginepath)
                enginepaths.append(enginepath)
                enginedirs[enginepath] = file
    enginepaths = sorted(enginepaths)
    if len(enginepaths) == 0:
        enginepaths.append("NO ENGINES FOUND!")
        enginedirs["NO ENGINES FOUND!"] = "NO ENGINES FOUND!"
    # check for bar.sdd
    modinfos['Spring-launcher with BYAR Chobby $VERSION'] = {'modtype': '0', 'name': 'BYAR Chobby $VERSION'}
    modinfos['Spring-launcher with rapid://byar-chobby:test'] = {'modtype': '0', 'name': 'rapid://byar-chobby:test'}
    modinfos['rapid://byar-chobby:test'] = {'name': 'rapid://byar-chobby:test', 'version': '', 'modtype': '5'}
    modinfos['rapid://byar:test'] = {'name': 'rapid://byar:test', 'version': '', 'modtype': '1'}
    # assume rapid://byar-chobby:test
    # assume rapid://byar:test

    if os.path.exists(os.path.join(datafolder, 'games')):
        gamespath = os.path.join(datafolder, 'games')
        for gamedir in os.listdir(gamespath):
            if os.path.isdir(os.path.join(gamespath)):
                gamepath = os.path.join(gamespath, gamedir)
                modinfopath = os.path.join(gamepath, 'modinfo.lua')
                if os.path.exists(modinfopath):
                    modinfo = parsemodinfo(modinfopath)
                    modinfos[modinfo['name'] + " " + modinfo['version']] = modinfo
    for k, v in modinfos.items():
        print(k, v)

    parsemaps()


refresh()

# Gather cmd args:
# https://github.com/beyond-all-reason/spring-launcher/blob/887937649014318d0da9e6e4b67f831366ce392b/src/engine_launcher.js#L149

# isolation = true
# C:\Users\Peti\AppData\Local\Programs\Beyond-All-Reason\data\engine\105.1.1-1177-gada72b4 bar\spring.exe \n
# --write-dir C:\Users\Peti\AppData\Local\Programs\Beyond-All-Reason\data --isolation --menu BYAR Chobby $VERSION

def try_start_replay(replayfilepath):
    if not replayfilepath.lower().endswith('.sdfz'):
        print ("Replay file path does not end with .sdfz", replayfilepath)
        exitpause("")
    if not os.path.exists(replayfilepath):
        print ("Path to replay file incorrect", replayfilepath)
        exitpause("")
    
    #1. Try to copy replay into demos folder
    #always assume that barpath is 
    replayfiledir, replayfilename = os.path.split(replayfilepath)
    savedreplaypath = os.path.join(barinstallpath,'data','demos', replayfilename)
    print (replayfilepath,savedreplaypath)
    if not os.path.exists(savedreplaypath):
        shutil.copy2(replayfilepath,savedreplaypath)
    
    #2. Parse demo file
    demo = Parse_demo_file(savedreplaypath)
    demo.parse_header_and_script()

    engineversion = demo.header['versionString'] # 105.1.1-1354-g72b2d55 BAR105
    mapname = demo.script.other['mapname'] # Archsimkats_Valley_V1
    modname = demo.script.other['modname'] # Beyond All Reason test-21960-4e943b5
    print ("Replay info:", engineversion, mapname, modname)

    #3. Check engine version and download if needed, compare
    # 105.1.1-1354-g72b2d55 BAR105 to 105.1.1-941-g941148f bar
    enginebaseversion = engineversion.partition(' ')[0] 
    enginedir = os.path.join('data','engine',enginebaseversion + ' bar')
    if os.path.join(enginedir,'spring.exe') in enginepaths:
        print ("Found correct engine at", enginedir)
    else:
        print ("Engine ",os.path.join(enginedir,'spring.exe') ,"not found in known engines")
        print (str(enginepaths))
        print ("Attempting to download engine from github")
        baseurl = f'https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_windows-64-minimal-portable.7z'
        archivename = f'spring_bar_.BAR105.{enginebaseversion}_windows-64-minimal-portable.7z'
        print(baseurl)
        try:
            with open(archivename,'wb') as enginearchive:
                enginearchive.write(requests.get(baseurl).content)
        except:
            print ("Unable to download engine from", baseurl)
            exitpause("")  

        try:
            os.makedirs(os.path.join(barinstallpath,enginedir))
            with py7zr.SevenZipFile(archivename,'r') as archive:
                archive.extractall(path = os.path.join(barinstallpath,enginedir))
        except:
            print ("Failed to extract engine archive", archivename)
            exitpause("")

    #4.1 Get game and map

    my_env = os.environ.copy()
    my_env['PRD_RAPID_USE_STREAMER'] = 'false'
    my_env['PRD_RAPID_REPO_MASTER'] = 'https://bar-rapid.p2004a.com/repos.gz'

    prdmodcmd = f'{os.path.join(barinstallpath, "bin", "pr-downloader.exe")} --filesystem-writepath {os.path.join(barinstallpath, "data")} --download-game "{modname}"'
    prdmapcmd = f'{os.path.join(barinstallpath, "bin", "pr-downloader.exe")} --filesystem-writepath {os.path.join(barinstallpath, "data")} --download-map "{mapname}"'
    for prdcmd in [prdmodcmd, prdmapcmd]:
        print (prdcmd)
        prdsuccess = subprocess.call(prdcmd, shell= True, env = my_env)
        if prdsuccess==0:
            print("PRD success")
        else:
            print ("PRD failed")
            exitpause("")

    #5. start the demo 
    runcmd = f'"{os.path.join(barinstallpath, enginedir,"spring.exe")}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" "{savedreplaypath}"'
    print (runcmd)
    subprocess.Popen(shlex.split(runcmd),close_fds=True )
    #print (demo.header)


if len(sys.argv) < 2: # no arguments passed, use GUI
    root = tk.Tk()
    #root = ThemedTk(theme='black')
    ttk.Label(
        text="Place this next to Beyond-All-Reason.exe to scan for contents.\nhttps://github.com/beyond-all-reason/bar_debug_launcher by Beherith").pack(
        fill=tk.X, padx=5, pady=5)


    modoptionstb = tk.Text(root, height = 5, font=("Courier", 8))

    cmdtext = tk.Text(root, height=7, font=("Courier", 8))
    # config the root window
    root.geometry('500x550')
    root.resizable(False, False)
    root.title('BAR Replay and Debug Launcher')

    #root.config(bg="#26242f")  
    try:
        root.iconbitmap('bar-icon.ico')
    except:
        print("Unable to find bar-icon.ico")
    # label
    ttk.Label(text="Select the engine version you want to use:").pack(fill=tk.X, padx=5, pady=5)

    # create a combobox
    selected_engine = tk.StringVar()
    engine_cb = ttk.Combobox(root, textvariable=selected_engine, height=min(len(enginepaths), 50))
    engine_cb['values'] = enginepaths
    engine_cb.set(enginepaths[0])
    # prevent typing a value
    engine_cb['state'] = 'readonly'
    # place the widget
    engine_cb.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(text="Select the game/menu version you want to run:").pack(fill=tk.X, padx=5, pady=5)

    # create a combobox
    selected_game = tk.StringVar()
    game_cb = ttk.Combobox(root, textvariable=selected_game)
    game_cb['values'] = list(modinfos.keys())
    game_cb.set(list(modinfos.keys())[0])
    # prevent typing a value
    game_cb['state'] = 'readonly'
    # place the widget
    game_cb.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(text="Select a map if you want to test the game directly. Not all maps will work.").pack(fill=tk.X, padx=5,
                                                                                                    pady=5)

    # create a combobox
    selected_map = tk.StringVar()
    map_cb = ttk.Combobox(root, textvariable=selected_map, height=min(len(maps), 50))
    map_cb['values'] = list(maps)
    map_cb.set(maps[0])
    # prevent typing a value
    map_cb['state'] = 'readonly'
    # place the widget
    map_cb.pack(fill=tk.X, padx=5, pady=5)

    runcmd = ""


    def genscript(map, game):
        modopts = modoptionstb.get('1.0',tk.END)
        print (modopts)
        scripttxt = """[game]
            {
            [allyteam1]
            {
            numallies=0;
            }
            [team1]
            {
            teamleader=0;
            allyteam=1;
            }
            [ai0]
            {
            shortname=NullAI;
            name=Enemy;
            version=0.1;
            team=1;
            host=0;
            }
            [modoptions]
            {
            maxspeed=20;
            %s
            }
            [allyteam0]
            {
            numallies=0;
            }
            [team0]
            {
            teamleader=0;
            allyteam=0;
            }
            [player0]
            {
            team=0;
            name=UnnamedPlayer;
            }
            mapname=%s;
            myplayername=UnnamedPlayer;
            ishost=1;
            gametype=%s;
            nohelperais=0;
            }""" % (modopts, map, game)
        scriptfile = open("bar_debug_launcher_script.txt", 'w')
        scriptfile.write(scripttxt)
        scriptfile.close()
        print('Generated script:', scripttxt)


    def gencmd(event):
        global runcmd
        mygame = selected_game.get()
        myengine = selected_engine.get()
        mymap = selected_map.get()
        if modinfos[mygame]['modtype'] == '5':
            runcmd = f'"{os.path.join(barinstallpath, myengine)}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" --menu "{mygame}"'
        elif modinfos[mygame]['modtype'] == '1':
            if mymap != maps[0]:
                genscript(mymap, mygame)
                runcmd = f'"{os.path.join(barinstallpath, myengine)}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" bar_debug_launcher_script.txt'
            else:
                runcmd = f'"{os.path.join(barinstallpath, myengine)}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}"'
        elif modinfos[mygame]['modtype'] == '0':
            configdev = "bar_debug_launcher_config.json"
            bar_debug_launcher_config_file = open(configdev, 'w')
            bar_debug_launcher_config_file.write(
                """{
                    "title": "Beyond All Reason",
                    "setups": [
                        {
                            "package": {
                                "id": "dev-lobby",
                                "display": "Dev Lobby"
                            },
                            "downloads": {
                                "engines": ["%s"]
                            },
                            "no_start_script": true,
                            "no_downloads": true,
                            "auto_start": true,
                            "launch": {
                                "start_args": ["--menu", "%s"]
                            }
                        }
                    ]
                }""" % (enginedirs[myengine], modinfos[mygame]['name']))
            bar_debug_launcher_config_file.close()

            runcmd = f'"{os.path.join(barinstallpath, "Beyond-All-Reason.exe")}" -c "{os.path.join(barinstallpath, configdev)}"'

        print(runcmd)
        cmdtext.delete('1.0', tk.END)
        cmdtext.insert('1.0', str(runcmd))


    engine_cb.bind('<<ComboboxSelected>>', gencmd)
    game_cb.bind('<<ComboboxSelected>>', gencmd)
    map_cb.bind('<<ComboboxSelected>>', gencmd)

    ttk.Label(text="This is the command that will be run:").pack(fill=tk.X, padx=5, pady=5)
    cmdtext.pack(fill=tk.X)
    ttk.Label(text="Additional modoptions:").pack(fill=tk.X, padx=5, pady=5)
    modoptionstb.pack(fill = tk.X)

    def startreplay():
        filetypes = [('BAR Replay Files', '*.sdfz'),
                    ('All files', '*.*')]
        filename = filedialog.askopenfilename(title = 'Select a replay to watch', initialdir = os.path.join(barinstallpath, 'data','demos'), filetypes = filetypes)
        print (filename)
        if filename:
            try_start_replay(filename)

    tk.Button(root, text="Open and launch a replay", command=startreplay).pack(side=tk.BOTTOM, fill=tk.X)

    def startspring():
        gencmd(None)
        print('starting spring with', runcmd)
        subprocess.Popen(shlex.split(runcmd),close_fds=True )


    tk.Button(root, text="Start with the above selected settings", command=startspring).pack(fill=tk.X)

    gencmd(None)  # init defaults
    root.mainloop()
else:
    #arg passed, it better be a replay file
    print("Arguments are:", sys.argv)
    replayfilepath = sys.argv[1]
    try_start_replay(replayfilepath)
