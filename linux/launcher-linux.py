#!/usr/bin/env python3
# A small settings window in front of run-linux.py and precompile-linux.py (the port of launcher.ps1; launcher.sh
# opens it). The settings and the console language names follow the KytyPS5 launcher (src/launcher, by the KytyPS5
# developers); they are kept in launcher-settings.json next to this script. --dry-run prints the commands.
import json
import os
import shlex
import shutil
import subprocess
import sys

import kyty_common as kc

ROOT = kc.ROOT
SETTINGS = os.path.join(ROOT, 'launcher-settings.json')
LANGUAGES = ['Japanese', 'English (United States)', 'French (France)', 'Spanish (Spain)', 'German', 'Italian', 'Dutch',
             'Portuguese (Portugal)', 'Russian', 'Korean', 'Chinese (Traditional)', 'Chinese (Simplified)', 'Finnish',
             'Swedish', 'Danish', 'Norwegian', 'Polish', 'Portuguese (Brazil)', 'English (United Kingdom)', 'Turkish',
             'Spanish (Latin America)', 'Arabic', 'French (Canada)', 'Czech', 'Hungarian', 'Greek', 'Romanian', 'Thai',
             'Vietnamese', 'Indonesian']
RESOLUTIONS = ['1280x720', '1920x1080', '2560x1440', '3840x2160']
# The height Demon's Souls renders its 3D at (run.sh --render-height); its output and UI stay 3840x2160.
RENDER_HEIGHTS = ['1440 (PS5)', '1296', '1152', '1080', '900']

settings = {'game': '', 'resolution': '2560x1440', 'fullscreen': False, 'aspect': True, 'language': 1,
            'redzone': True, 'ecores': False, 'fps120': False, 'render': 1440}
if os.path.isfile(SETTINGS):
	try:
		saved = json.loads(kc.read_text(SETTINGS))
		settings.update({k: v for k, v in saved.items() if k in settings})
	except ValueError:
		pass
if not settings['game'] and os.path.isfile(kc.GAME_FILE):
	settings['game'] = kc.read_text(kc.GAME_FILE).strip()
efficiency = kc.efficiency_mask()


def play_command():
	width, height = settings['resolution'].split('x')
	args = [sys.executable, os.path.join(ROOT, 'run-linux.py'), '--prompt', '--follow', '--width', width,
	        '--height', height, '--language', str(settings['language'])]
	if settings['fullscreen']:
		args.append('--fullscreen')
		if settings['aspect']:
			args.append('--aspect-fit')
	if settings['fps120']:
		args.append('--fps120')
	if int(settings['render']) > 0 and int(settings['render']) != 1440:
		args += ['--render-height', str(int(settings['render']))]
	if settings['game']:
		args += ['--game', settings['game']]
	return args


def precompile_command():
	args = [sys.executable, os.path.join(ROOT, 'precompile-linux.py')]
	if settings['ecores'] and efficiency:
		args += ['--affinity', hex(efficiency)]
	if settings['game']:
		args += ['--game', settings['game']]
	return args


# A terminal window (Konsole in Desktop Mode) for the live log; after a crash (play) or always (precompile) it
# waits for Enter, as the Windows console does. Without a terminal the command runs on its own.
def in_terminal(args, pause_always, title):
	pause = 'echo; read -rp "Press Enter to close..."'
	script = f'cd {shlex.quote(ROOT)}; {shlex.join(args)}; rc=$?; ' + (f'{pause}' if pause_always else f'if [ $rc -ne 0 ]; then {pause}; fi')
	if shutil.which('konsole'):
		return ['konsole', '-p', f'tabtitle={title}', '-e', 'bash', '-c', script]
	for terminal in ('gnome-terminal', 'xfce4-terminal', 'xterm'):
		if shutil.which(terminal):
			return [terminal, '-e', 'bash -c ' + shlex.quote(script)] if terminal != 'gnome-terminal' else [terminal, '--', 'bash', '-c', script]
	return args


def save_settings():
	kc.write_text(SETTINGS, json.dumps(settings, indent=4) + '\n')


if '--dry-run' in sys.argv:
	print('play:      ', shlex.join(in_terminal(play_command(), False, 'KytyPS5')))
	print('precompile:', shlex.join(in_terminal(precompile_command(), True, 'KytyPS5 precompile')))
	print(f'efficiency cores: 0x{efficiency:X}')
	sys.exit(0)

import tkinter as tk
from tkinter import ttk

form = tk.Tk()
form.title('KytyPS5 launcher')
form.resizable(False, False)
grid = ttk.Frame(form, padding=(12, 12, 12, 8))
grid.pack(fill='both')
row_index = [0]


# A row: a label, then the controls side by side.
def add_row(label, make):
	ttk.Label(grid, text=label).grid(row=row_index[0], column=0, sticky='w', padx=(0, 8), pady=4)
	row = ttk.Frame(grid)
	row.grid(row=row_index[0], column=1, sticky='w')
	make(row)
	row_index[0] += 1


game = tk.StringVar(value=settings['game'])
title = tk.StringVar()


def browse():
	folder = kc.choose_folder('The game folder (eboot.bin, sce_sys)', game.get() if os.path.isdir(game.get()) else '')
	if folder:
		game.set(folder)


# The game folder packed into a ZArchive (zarchive <folder> <file.zar>): read without extracting it.
def browse_zar():
	path = kc.choose_file('The game folder packed into a ZArchive', os.path.dirname(game.get()))
	if path:
		game.set(path)


def game_row(row):
	ttk.Entry(row, textvariable=game, width=60).pack(side='left')
	ttk.Button(row, text='Browse...', command=browse).pack(side='left', padx=(4, 0))
	ttk.Button(row, text='.zar...', command=browse_zar).pack(side='left', padx=(4, 0))


add_row('Game folder', game_row)
add_row('', lambda row: ttk.Label(row, textvariable=title, foreground='gray').pack(side='left'))


def update_title(*_):
	title.set('Choose the folder with eboot.bin and sce_sys (the game dump), or a .zar archive of it.')
	try:
		info = kc.read_game_param(game.get().strip())
		if info:
			title.set(f"{kc.title_name(info)} ({info.get('titleId')} {info.get('contentVersion')})")
	except Exception:
		pass


game.trace_add('write', update_title)
update_title()

resolution = tk.StringVar(value=settings['resolution'] if settings['resolution'] in RESOLUTIONS else '2560x1440')
add_row('Resolution', lambda row: ttk.Combobox(row, textvariable=resolution, values=RESOLUTIONS, state='readonly',
                                               width=14).pack(side='left'))
fullscreen = tk.BooleanVar(value=bool(settings['fullscreen']))
aspect = tk.BooleanVar(value=bool(settings['aspect']))
aspect_box = []


def fullscreen_row(row):
	ttk.Checkbutton(row, text='Fullscreen', variable=fullscreen,
	                command=lambda: aspect_box[0].state(['!disabled'] if fullscreen.get() else ['disabled'])).pack(side='left')
	box = ttk.Checkbutton(row, text='Keep 16:9 (black bars)', variable=aspect)
	box.pack(side='left', padx=(10, 0))
	box.state(['!disabled'] if fullscreen.get() else ['disabled'])
	aspect_box.append(box)


add_row('', fullscreen_row)
language = tk.StringVar(value=LANGUAGES[max(0, min(len(LANGUAGES) - 1, int(settings['language'])))])
add_row('Console language', lambda row: ttk.Combobox(row, textvariable=language, values=LANGUAGES, state='readonly',
                                                     width=30).pack(side='left'))
redzone = tk.BooleanVar(value=bool(settings['redzone']))


def redzone_row(row):
	# Windows only: Linux signal delivery skips the guest's red zone, so there is nothing to protect here.
	box = ttk.Checkbutton(row, text='Red-zone protection (Windows only: not needed on Linux)', variable=redzone)
	box.state(['disabled'])
	box.pack(side='left')


add_row('', redzone_row)
fps120 = tk.BooleanVar(value=bool(settings['fps120']))
add_row('', lambda row: ttk.Checkbutton(row, text="Up to 120 fps (the game's own frames; movies play faster)",
                                        variable=fps120).pack(side='left'))
render = tk.StringVar(value=next((h for h in RENDER_HEIGHTS if h.split(' ')[0] == str(int(settings['render']))),
                                 RENDER_HEIGHTS[0]))


def render_row(row):
	ttk.Combobox(row, textvariable=render, values=RENDER_HEIGHTS, state='readonly', width=11).pack(side='left')
	ttk.Label(row, text="Demon's Souls 3D; lower = faster, less sharp", foreground='gray').pack(side='left', padx=(6, 0))


add_row('Render height', render_row)
ecores = tk.BooleanVar(value=bool(settings['ecores']) and efficiency != 0)


def ecores_row(row):
	box = ttk.Checkbutton(row, text='Precompile on the efficiency cores only (slower, the PC stays responsive)',
	                      variable=ecores)
	if not efficiency:
		box.state(['disabled'])
	box.pack(side='left')


add_row('', ecores_row)


def read_form():
	settings['game'] = game.get().strip()
	settings['resolution'] = resolution.get()
	settings['fullscreen'] = fullscreen.get()
	settings['aspect'] = aspect.get()
	settings['language'] = LANGUAGES.index(language.get())
	settings['redzone'] = redzone.get()
	settings['fps120'] = fps120.get()
	settings['render'] = int(render.get().split(' ')[0])
	settings['ecores'] = ecores.get()
	save_settings()


def play():
	read_form()
	subprocess.Popen(in_terminal(play_command(), False, 'KytyPS5'), cwd=ROOT, start_new_session=True)
	form.destroy()


def precompile():
	read_form()
	subprocess.Popen(in_terminal(precompile_command(), True, 'KytyPS5 precompile'), cwd=ROOT, start_new_session=True)


def open_logs():
	os.makedirs(kc.LOGS, exist_ok=True)
	subprocess.Popen(['xdg-open', kc.LOGS], start_new_session=True)


def open_readme():
	for name in ('README-LINUX.md', 'README.md'):
		path = os.path.join(ROOT, name)
		if os.path.isfile(path):
			subprocess.Popen(['xdg-open', path], start_new_session=True)
			return


buttons = ttk.Frame(grid)
buttons.grid(row=row_index[0], column=0, columnspan=2, sticky='w', pady=(10, 0))
row_index[0] += 1
style = ttk.Style()
style.configure('Bold.TButton', font=('TkDefaultFont', 10, 'bold'))
play_button = ttk.Button(buttons, text='Play', style='Bold.TButton', command=play)
play_button.pack(side='left')
ttk.Button(buttons, text='Precompile shaders', command=precompile).pack(side='left', padx=(6, 0))
ttk.Button(buttons, text='Logs folder', command=open_logs).pack(side='left', padx=(6, 0))
ttk.Button(buttons, text='README', command=open_readme).pack(side='left', padx=(6, 0))
ttk.Label(grid, text='Settings follow the KytyPS5 launcher (src/launcher) by the KytyPS5 developers.',
          foreground='gray').grid(row=row_index[0], column=0, columnspan=2, sticky='w', pady=(8, 0))
form.bind('<Return>', lambda _: play())


def closing():
	read_form()
	form.destroy()


form.protocol('WM_DELETE_WINDOW', closing)
form.update_idletasks()
form.geometry(f'+{(form.winfo_screenwidth() - form.winfo_reqwidth()) // 2}+{(form.winfo_screenheight() - form.winfo_reqheight()) // 3}')
form.mainloop()
