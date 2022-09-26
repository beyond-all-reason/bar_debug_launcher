import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showinfo
from calendar import month_name

import os
import re
import subprocess
import shlex

#Grab all engine versions
cwd = os.getcwd()

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
			if mapfile.lower().endswith('.sd7') and '.' not in mapfile[:-4] and ' ' not in mapfile:
				maps.append(mapfile)

				
				
def refresh():
	global modinfos
	global enginepaths
	global enginedirs
	if os.path.exists(enginefolder) :
		for file in os.listdir(enginefolder):
			enginedir = os.path.join(enginefolder,file)
			if os.path.isdir(enginedir) and os.path.exists(os.path.join(enginedir, 'spring.exe')):
				enginepath = os.path.join(enginedir, 'spring.exe')
				print ("Found engine in path:", enginepath)
				enginepaths.append(enginepath)
				enginedirs[enginepath] = file
	enginepaths = sorted(enginepaths)
	if len(enginepaths) == 0:
		enginepaths.append("NO ENGINES FOUND!")
	#check for bar.sdd
	modinfos['Spring-launcher with BYAR Chobby $VERSION'] = {'modtype': '0', 'name':'BYAR Chobby $VERSION'}
	modinfos['Spring-launcher with rapid://byar-chobby:test'] = {'modtype': '0', 'name':'rapid://byar-chobby:test'}
	modinfos['rapid://byar-chobby:test'] = {'name' : 'rapid://byar-chobby:test', 'version' :'' , 'modtype' : '5'}
	modinfos['rapid://byar:test'] = {'name' : 'rapid://byar:test', 'version' :'' , 'modtype' : '1'}
	#assume rapid://byar-chobby:test
	#assume rapid://byar:test



	if os.path.exists(os.path.join(datafolder,'games')):
		gamespath = os.path.join(datafolder,'games')
		for gamedir in os.listdir(gamespath):
			if os.path.isdir(os.path.join(gamespath)):
				gamepath = os.path.join(gamespath, gamedir)
				modinfopath = os.path.join(gamepath,'modinfo.lua')
				if os.path.exists(modinfopath):
					modinfo = parsemodinfo(modinfopath)
					modinfos[modinfo['name'] + " " + modinfo['version']] = modinfo
	for k, v in modinfos.items():
		print (k,v)

refresh()


# Gather cmd args:
# https://github.com/beyond-all-reason/spring-launcher/blob/887937649014318d0da9e6e4b67f831366ce392b/src/engine_launcher.js#L149

# isolation = true
# C:\Users\Peti\AppData\Local\Programs\Beyond-All-Reason\data\engine\105.1.1-1177-gada72b4 bar\spring.exe \n
# --write-dir C:\Users\Peti\AppData\Local\Programs\Beyond-All-Reason\data --isolation --menu BYAR Chobby $VERSION

root = tk.Tk()

cmdtext = tk.Text(root, height = 7, font = ("Courier", 8))
# config the root window
root.geometry('500x300')
root.resizable(False, False)
root.title('BAR Debug Launcher')

# label
ttk.Label(text="Select the engine version you want to use:").pack(fill=tk.X, padx=5, pady=5)


# create a combobox
selected_engine = tk.StringVar()
engine_cb = ttk.Combobox(root, textvariable=selected_engine)
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
game_cb['values'] =  list(modinfos.keys())
game_cb.set(list(modinfos.keys())[0])
# prevent typing a value
game_cb['state'] = 'readonly'
# place the widget
game_cb.pack(fill=tk.X, padx=5, pady=5)

ttk.Label(text="Select a map if you want to test the game directly:").pack(fill=tk.X, padx=5, pady=5)

# create a combobox
selected_map = tk.StringVar()
map_cb = ttk.Combobox(root, textvariable=selected_map)
map_cb['values'] =  list(maps)
map_cb.set(maps[0])
# prevent typing a value
map_cb['state'] = 'readonly'
# place the widget
map_cb.pack(fill=tk.X, padx=5, pady=5)

runcmd = ""

def genscript(map,game):
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
		}"""%(map,game)
	scriptfile = open("bar_debug_launcher_script.txt",'w')
	scriptfile.write(scripttxt)
	scriptfile.close()
	print('Generated script:",scripttxt)

def gencmd(event):
	global runcmd
	mygame = selected_game.get()
	myengine = selected_engine.get()
	mymap = selected_map.get()
	if modinfos[mygame]['modtype'] == '5':
		runcmd = f'"{os.path.join(cwd,myengine)}"  --isolation --write-dir "{os.path.join(cwd, datafolder)}" --menu "{mygame}"'
	elif modinfos[mygame]['modtype'] == '1':
		if mymap != maps[0]:
			genscript(mygame,mymap)
			runcmd = f'"{os.path.join(cwd,myengine)}"  --isolation --write-dir "{os.path.join(cwd, datafolder)}" bar_debug_launcher_script.txt'
		else:
			runcmd = f'"{os.path.join(cwd,myengine)}"  --isolation --write-dir "{os.path.join(cwd, datafolder)}"'
	elif modinfos[mygame]['modtype'] == '0':
		configdev = "bar_debug_launcher_config.json"
		bar_debug_launcher_config_file = open(configdev,'w')
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
		}"""%(enginedirs[myengine], modinfos[mygame]['name']))
		bar_debug_launcher_config_file.close()

		runcmd = f'"{os.path.join(cwd,"Beyond-All-Reason.exe")}" -c "{os.path.join(cwd,configdev)}"'

	print (runcmd)
	cmdtext.delete('1.0', tk.END)
	cmdtext.insert('1.0', str(runcmd))
	

engine_cb.bind('<<ComboboxSelected>>', gencmd)
game_cb.bind('<<ComboboxSelected>>', gencmd)
map_cb.bind('<<ComboboxSelected>>', gencmd)

ttk.Label(text="This is the command that will be run:").pack(fill=tk.X, padx=5, pady=5)
cmdtext.pack(fill=tk.X)

def startspring():
	print ('starting spring with', runcmd)
	subprocess.run(shlex.split(runcmd))

tk.Button(root,text = "Start with the selected settings", command = startspring).pack()

gencmd(None) #init defaults
root.mainloop()
