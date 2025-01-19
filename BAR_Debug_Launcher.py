import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter.messagebox import showinfo
#from ttkthemes import ThemedTk
from calendar import month_name

import platform
import os
import re
import subprocess
import shlex
import sys
import shutil
import requests
try:
    import py7zr
except ImportError:
    print ("Cant find py7zr lib, no engine downloads available")
    py7zr = None


from parse_demo_file import Parse_demo_file

from slpp import slpp

#Try to figure out the BAR install path:
barinstallpath = os.path.abspath(os.path.dirname(sys.argv[0])) 
cwd = os.getcwd()
#This is needed for double-click launches, as then the CWD is wherever the demo file is
os.chdir(barinstallpath)
print("Exe path", barinstallpath, "cwd", cwd)
print("Setting path to", barinstallpath)

def exitpause(message = ""):
    print("Terminating: ", message)
    if platform.system() == 'Windows':
        os.system("pause")
    exit(1)

#DEBUGGINGS
#sys.argv.append("C:/Users/peti/Downloads/20230112_123955_Archsimkats_Valley_V1_105.1.1-1354-g72b2d55 BAR105.sdfz")
#barinstallpath = "C:/Users/Peti/AppData/Local/Programs/Beyond-All-Reason"
#os.chdir(barinstallpath)

#maps = ['Ill choose my own once ingame']

def find_linux_datadir():
    # Searches for the BAR install directory in the ~same was as launcher
    # and returns absolute path
    try:
        documents = subprocess.check_output(
            ['xdg-user-dir', 'DOCUMENTS'], encoding='utf-8').strip()
    except:
        documents = os.path.expanduser("~")  # Yep, that's fallback
    if os.path.exists(os.path.join(documents, 'Beyond All Reason')):
        return os.path.join(documents, 'Beyond All Reason')

    state_home = os.getenv('XDG_STATE_HOME',
        default=os.path.join(os.path.expanduser("~"), '.local', 'state'))
    return os.path.join(state_home, 'Beyond All Reason')

def find_linux_launcher_binary():
    # Searches for the newest AppImage file in the current directory
    for file in reversed(sorted(os.listdir())):
        if re.match(r'^Beyond-All-Reason.*\.AppImage$', file):
            return file
    return 'Beyond-All-Reason.AppImage'  # Just something to return...

if platform.system() == 'Windows':
    engine_binary = 'spring.exe'
    prd_binary = 'pr-downloader.exe'
    datafolder = 'data'
    launcher_binary_display = launcher_binary = 'Beyond-All-Reason.exe'
    engine_download_baseurl = 'https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_windows-64-minimal-portable.7z'
    engine_download_baseurl_new = 'https://github.com/beyond-all-reason/spring/releases/download/{enginebaseversion}/spring_bar_.{releaseID}.{enginebaseversion}_windows-64-minimal-portable.7z'
elif platform.system() == 'Linux':
    engine_binary = 'spring'
    prd_binary = 'pr-downloader'
    # Later we depend on that os.join(barinstallpath, datafolder) returns
    # datafolder when datafolder is absolute path.
    datafolder = find_linux_datadir()
    launcher_binary = find_linux_launcher_binary()
    launcher_binary_display= "Beyond-All-Reason AppImage"
    engine_download_baseurl = 'https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_linux-64-minimal-portable.7z'
    engine_download_baseurl_new = 'https://github.com/beyond-all-reason/spring/releases/download/{enginebaseversion}/spring_bar_.{releaseID}.{enginebaseversion}_linux-64-minimal-portable.7z'
else:
    raise Exception('Unsupported platform')


archivecache = {} # maps gamename/mapname to filename
maps = {}
games = {}
menus = {}
engines = {}
modinfos = {}

scriptbase = """
[game]
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
        name=NullAI;
        version=0.1;
        team=1;
        host=0;
    }
    [modoptions]
    {
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
        name=DebugLauncher;
    }
    mapname=%s;
    myplayername=DebugLauncher;
    ishost=1;
    gametype=%s;
    nohelperais=0;
}"""

# returns a dict of engineversion:absolutespringexepath
def findengines(enginefolder):
    engines = {}
    enginedirs  = {}
    if os.path.exists(enginefolder):
        for engineversion in os.listdir(enginefolder):
            enginedir = os.path.join(enginefolder, engineversion)
            if os.path.isdir(enginedir) and os.path.exists(os.path.join(enginedir, engine_binary)):
                enginepath = os.path.join(enginedir, engine_binary)
                print(f"Found engine version {engineversion} in path: {enginepath}")
                engines[engineversion] = enginepath
    if len(engines) == 0:
        engines["NO ENGINES FOUND!"] = "NO ENGINES FOUND!"
    return engines,enginedirs

# returns three dicts from archivecach
def parsecache(path):
    global archivecache           
    maps = {} # key archive name to value filename
    games = {}
    menus = {}
    try:
        cachefiles = []
        for cachedir in os.listdir(path):
            if os.path.isdir(os.path.join(path,cachedir)):
                for archivecachefile in os.listdir(os.path.join(path,cachedir)):
                    if 'archivecache' in archivecachefile.lower() and archivecachefile.lower().endswith('.lua'):
                        archivecachefilepath = os.path.join(path,cachedir, archivecachefile)
                        lastmodified = os.path.getmtime(archivecachefilepath)
                        print ("Found a cache file",cachedir,  archivecachefile, "last modified:", lastmodified)
                        cachefiles.append((archivecachefilepath, lastmodified))

        if len(cachefiles) > 0:
            cachefiles = sorted(cachefiles, key = lambda x:[1], reverse = True)
            archivecachefilepath = cachefiles[0][0]
            print ("Loading Archive Cache File:", archivecachefilepath)
            archivecachecontents = open(archivecachefilepath).read()
            archivetable = '{' + archivecachecontents.partition('{')[2].rpartition('}')[0] +  '}'
            archivetable = slpp.decode(archivetable)
            for archive in archivetable['archives']:
                if 'archivedata' in archive and 'modtype' in archive['archivedata']:
                    archivedata = archive['archivedata']
                    modtype = archivedata['modtype']
                    if modtype == 3: # map
                        maps[archivedata['name']] = archive['name']
                    elif modtype == 5: #menu
                        menus[archivedata['name']] = archive['name']
                    elif modtype == 1: #game
                        games[archivedata['name']] = archive['name']
            print (f"Found {len(maps)} maps, {len(games)} games, {len(menus)} menus")
    except Exception as e:
        print ("parsecache error, dont code blind!", e)
    return maps, games, menus

def refresh():
    global modinfos
    #global enginepaths
    #global enginedirs
    global maps, games, menus, engines, enginedirs
    maps, games, menus = parsecache(os.path.join(barinstallpath, datafolder, "cache"))
    engines, enginedirs = findengines(os.path.join(barinstallpath, datafolder, "engine"))

    #parsemaps()
    # check for bar.sdd
    
    modinfos['Spring-launcher with rapid://byar-chobby:test'] = {'modtype': '0', 'name': 'rapid://byar-chobby:test'}
    modinfos['Latest BYAR Chobby Lobby: rapid://byar-chobby:test'] = {'name': 'rapid://byar-chobby:test', 'version': '', 'modtype': '5'}
    modinfos['Latest BAR Game: rapid://byar:test'] = {'name': 'rapid://byar:test', 'version': '', 'modtype': '1'}
    for menuname in menus.keys():
        if '$VERSION' in menuname:
            modinfos[f'Spring-launcher with {menuname}'] = {'modtype': '0', 'name': menuname}
            modinfos[f'{menuname} (no launcher)'] = {'modtype': '5', 'name': menuname}
            break
    for gamename in games.keys():
        if '$VERSION' in gamename:
            modinfos[gamename] = {'modtype': '1', 'name': gamename}

    
    # assume rapid://byar-chobby:test
    # assume rapid://byar:test

    #check menus for $VERSION's


    '''
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
    '''

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
    savedreplaypath = os.path.join(barinstallpath, datafolder,'demos', replayfilename)
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
    if engineversion.startswith('2') and engineversion.count('.') == 2: 
        print("New engine version format found")
        subversions = engineversion.split('.') # e.g. 2025.01.3
        releaseID = f'rel{subversions[0]}{subversions[1]}'
        enginedir = f'{releaseID}.{engineversion}' # e.g. rel2501.2025.01.3

        if enginedir in engines:
            print ("Found correct engine at", enginedir)
        else:
            print ("Engine ",os.path.join(enginedir,engine_binary) ,"not found in known engines")
            print (str(engines))
            print ("Attempting to download engine from github")
            baseurl = engine_download_baseurl_new.format(releaseID=releaseID, enginebaseversion = engineversion)
            archivename = f'engine.{enginebaseversion}.7z'
            print(baseurl)
            try:
                with open(archivename,'wb') as enginearchive:
                    enginearchive.write(requests.get(baseurl).content)
            except Exception as e:
                print ("Unable to download engine from", baseurl, e)
                exitpause("")  

            try:
                newenginedir = os.path.join(barinstallpath, datafolder, 'engine' , enginedir)
                os.makedirs(newenginedir)
                with py7zr.SevenZipFile(archivename,'r') as archive:
                    archive.extractall(path = newenginedir)
            except Exception as e:
                print ("Failed to extract engine archive", archivename, e)
                exitpause("")
    else:
        
        # 105.1.1-1354-g72b2d55 BAR105 to 105.1.1-941-g941148f bar
        enginebaseversion = engineversion.partition(' ')[0] 
        enginedir = os.path.join(enginebaseversion + ' bar')
        if enginedir in engines:
            print ("Found correct engine at", enginedir)
        else:
            print ("Engine ",os.path.join(enginedir,engine_binary) ,"not found in known engines")
            print (str(engines))
            print ("Attempting to download engine from github")
            baseurl = engine_download_baseurl.format(enginebaseversion=enginebaseversion)
            archivename = f'engine.{enginebaseversion}.7z'
            print(baseurl)
            try:
                with open(archivename,'wb') as enginearchive:
                    enginearchive.write(requests.get(baseurl).content)
            except Exception as e:
                print ("Unable to download engine from", baseurl, e)
                exitpause("")  

            try:
                newenginedir = os.path.join(barinstallpath, datafolder, 'engine' , enginedir)
                os.makedirs(newenginedir)
                with py7zr.SevenZipFile(archivename,'r') as archive:
                    archive.extractall(path = newenginedir)
            except Exception as e:
                print ("Failed to extract engine archive", archivename, e)
                exitpause("")

    #4.1 Get game and map

    my_env = os.environ.copy()
    my_env['PRD_RAPID_USE_STREAMER'] = 'false'
    my_env['PRD_RAPID_REPO_MASTER'] = 'https://repos-cdn.beyondallreason.dev/repos.gz'

    prdcmds = []
    if modname not in games:
        prdcmds.append( f'"{os.path.join(barinstallpath, datafolder, "engine", enginedir, prd_binary)}" --filesystem-writepath "{os.path.join(barinstallpath, datafolder)}" --download-game "{modname}"')
    else:
        print (f"Found {modname} in archive cache")
    if mapname not in maps:
        prdcmds.append( f'"{os.path.join(barinstallpath, datafolder, "engine", enginedir, prd_binary)}" --filesystem-writepath "{os.path.join(barinstallpath, datafolder)}" --download-map "{mapname}"' )
    else:
        print (f"Found {mapname} in archive cache")

    for prdcmd in prdcmds:
        print (f"Running pr-downloader command: {prdcmd}")
        prdsuccess = subprocess.call(prdcmd, shell= True, env = my_env)
        if prdsuccess==0:
            print("PRD success")
        else:
            print ("PRD failed")
            exitpause("")

    #5. start the demo 
    runcmd = f'"{os.path.join(barinstallpath, datafolder,"engine",enginedir, engine_binary)}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" "{savedreplaypath}"'
    print (runcmd)
    subprocess.Popen(shlex.split(runcmd),close_fds=True )
    #print (demo.header)


if len(sys.argv) < 2: # no arguments passed, use GUI
    root = tk.Tk()
    #root = ThemedTk(theme='black')
    ttk.Label(
        text=f"Place this next to {launcher_binary_display} to scan for contents.\nhttps://github.com/beyond-all-reason/bar_debug_launcher by Beherith").pack(
        fill=tk.X, padx=5, pady=5)


    modoptionstb = tk.Text(root, height = 5, font=("Courier", 8))

    cmdtext = tk.Text(root, height=7, font=("Courier", 8))
    # config the root window
    root.geometry('500x550')
    root.resizable(True, True)
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
    engine_cb = ttk.Combobox(root, textvariable=selected_engine, height=min(len(engines), 40))
    engine_cb['values'] = sorted(engines.keys())
    engine_cb.set(sorted(engines.keys())[-1])
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
    map_cb['values'] = ['Ill choose my own once ingame'] + sorted(maps.keys())
    map_cb.set('Ill choose my own once ingame')
            # prevent typing a value
    map_cb['state'] = 'readonly'
    # place the widget
    map_cb.pack(fill=tk.X, padx=5, pady=5)

    runcmd = ""


    def genscript(map, game):
        modopts = modoptionstb.get('1.0',tk.END)
        print (modopts)
        scripttxt =  scriptbase % (modopts, map, game)
        scriptfile = open("bar_debug_launcher_script.txt", 'w')
        scriptfile.write(scripttxt)
        scriptfile.close()
        print('Generated script:', scripttxt)


    def gencmd(event):
        global runcmd
        mygame = selected_game.get()
        modinfo = modinfos[mygame]
        myengine = selected_engine.get()
        mymap = selected_map.get()
        if modinfo['modtype'] == '5':
            runcmd = f'"{engines[myengine]}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" --menu "{modinfo["name"]}"'
        elif modinfo['modtype'] == '1':
            if mymap != 'Ill choose my own once ingame':
                genscript(mymap, modinfo["name"])
                runcmd = f'"{engines[myengine]}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" bar_debug_launcher_script.txt'
            else:
                runcmd = f'"{engines[myengine]}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}"'
        elif modinfo['modtype'] == '0':
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
                }""" % (myengine, modinfo['name'])) # engine needs "105.1.1-941-g941148f bar" format
            bar_debug_launcher_config_file.close()

            runcmd = f'"{os.path.join(barinstallpath, launcher_binary)}" -c "{os.path.join(barinstallpath, configdev)}"'

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
        filename = filedialog.askopenfilename(title = 'Select a replay to watch', initialdir = os.path.join(barinstallpath, datafolder, 'demos'), filetypes = filetypes)
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
