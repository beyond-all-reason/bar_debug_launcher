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

enginepaths = []
datafolder = 'data'
enginefolder = 'data\\engine'
if os.path.exists(enginefolder) :
    for file in os.listdir(enginefolder):
        enginedir = os.path.join(enginefolder,file)
        if os.path.isdir(enginedir) and os.path.exists(os.path.join(enginedir, 'spring.exe')):
            enginepath = os.path.join(enginedir, 'spring.exe')
            print ("Found engine in path:", enginepath)
            enginepaths.append(enginepath)
enginepaths = sorted(enginepaths)
#check for bar.sdd
modinfos = {}
modinfos['rapid://byar-chobby:test'] = {'name' : 'rapid://byar-chobby:test', 'version' :'' , 'modtype' : '5'}
modinfos['rapid://byar:test'] = {'name' : 'rapid://byar:test', 'version' :'' , 'modtype' : '1'}
#assume rapid://byar-chobby:test
#assume rapid://byar:test

def parsemodinfo(path):
    modinfo = {}
    for line in open(path).readlines():
        line = line.partition('--')[0].strip().strip(',').replace('"','').replace('\'','') #uncomment, dequote
        if '=' in line:
            line = line.partition('=')
            modinfo[line[0].strip()] = line[2].strip()
    return modinfo

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

runcmd = ""

def gencmd(event):
    global runcmd
    mygame = selected_game.get()
    myengine = selected_engine.get()
    if modinfos[mygame]['modtype'] == '5':
        runcmd = f'"{os.path.join(cwd,myengine)}"  --isolation --write-dir "{os.path.join(cwd, datafolder)}" --menu "{mygame}"'
    else:
        runcmd = f'"{os.path.join(cwd,myengine)}"  --isolation --write-dir "{os.path.join(cwd, datafolder)}"'
    print (runcmd)
    cmdtext.delete('1.0', tk.END)
    cmdtext.insert('1.0', str(runcmd))

engine_cb.bind('<<ComboboxSelected>>', gencmd)
game_cb.bind('<<ComboboxSelected>>', gencmd)

ttk.Label(text="This is the command that will be run:").pack(fill=tk.X, padx=5, pady=5)
cmdtext.pack(fill=tk.X)

def startspring():
    print ('starting spring with', runcmd)
    subprocess.run(shlex.split(runcmd))


tk.Button(root,text = "Start with the selected settings", command = startspring).pack()

gencmd(None) #init defaults
root.mainloop()