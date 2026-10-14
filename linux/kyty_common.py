# Shared by run-linux.py, precompile-linux.py and launcher-linux.py (the Linux ports of run-windows.ps1,
# precompile-windows.ps1 and launcher.ps1): the game's param.json, the title caches' names, the CPUs, dialogs.
import json
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(ROOT, 'kyty_emulator')
TOOL = os.path.join(ROOT, 'kyty_shader_precompile')
GAME_FILE = os.path.join(ROOT, 'game-path.txt')
DEFAULT_GAME = os.path.expanduser('~/Documents/PPSA01341-app0')
PASS_STATES = os.path.join(ROOT, 'tools', 'local', 'static-precompile', 'pass-states.json')
LOGS = os.path.join(ROOT, 'logs')
# The system temp folder is a tmpfs (RAM) on SteamOS: the emulator's scratch files (4-5 GB while playing) and the
# precompile's driver caches go to the disk instead.
TMP = os.path.join(ROOT, '_Tmp')
TESTED_VERSIONS = ['PPSA01341 01.007.000', 'PPSA01341 01.005.000']


def read_text(path):
	with open(path, encoding='utf-8-sig') as f:
		return f.read()


def write_text(path, text):
	with open(path, 'w', encoding='utf-8') as f:
		f.write(text)


def last_game():
	game = read_text(GAME_FILE).strip() if os.path.exists(GAME_FILE) else ''
	return game or DEFAULT_GAME


# A game: its folder (eboot.bin and sce_sys) or the folder packed into a ZArchive (a .zar file, read by the
# emulator without extracting it).
def test_game(game):
	return bool(game) and (os.path.isfile(os.path.join(game, 'eboot.bin')) or
	                       (game.lower().endswith('.zar') and os.path.isfile(game)))


# The game's sce_sys/param.json (its title and version): a .zar's is copied out by the precompile program.
def read_game_param(game):
	if not game:
		return None
	param = os.path.join(game, 'sce_sys', 'param.json')
	try:
		if os.path.isfile(param):
			return json.loads(read_text(param))
	except (OSError, ValueError):
		return None
	if not game.lower().endswith('.zar') or not os.path.isfile(game) or not os.path.isfile(TOOL):
		return None
	fd, copy = tempfile.mkstemp()
	os.close(fd)
	try:
		if subprocess.run([TOOL, '--game', game, '--param', copy], stdout=subprocess.DEVNULL,
		                  stderr=subprocess.DEVNULL).returncode == 0:
			return json.loads(read_text(copy))
	except (OSError, ValueError):
		pass
	finally:
		try:
			os.remove(copy)
		except OSError:
			pass
	return None


def title_name(param):
	try:
		names = param['localizedParameters']
		return names[names['defaultLanguage']]['titleName']
	except (KeyError, TypeError):
		return None


# Caches made from the game's files are named by its title and version (seeds-<title>_<version>.seeds,
# _PipelineCache/static/<title>_<version>.*, the warmup recordings; versions need not share shaders). Those named
# by the title alone are from before: the game's that was played last (the remembered one), so they take its name.
def rename_title_caches(game):
	info = read_game_param(game)
	if not info or not info.get('titleId') or not info.get('contentVersion'):
		return
	title = info['titleId']
	gid = f"{title}_{info['contentVersion']}"
	moves = [(os.path.join(ROOT, 'seeds.seeds'), os.path.join(ROOT, f'seeds-{gid}.seeds')),
	         (os.path.join(ROOT, 'recorded.seeds'), os.path.join(ROOT, f'recorded-{gid}.seeds'))]
	static = os.path.join(ROOT, '_PipelineCache', 'static')
	if os.path.isdir(static):
		for name in os.listdir(static):
			if name.startswith(title + '.') and os.path.isfile(os.path.join(static, name)):
				moves.append((os.path.join(static, name), os.path.join(static, gid + name[len(title):])))
	warmup = os.path.join(ROOT, '_PipelineCache', 'warmup-v2')
	if os.path.isdir(warmup):
		for sub in os.listdir(warmup):
			moves.append((os.path.join(warmup, sub, f'{title}.shaders'), os.path.join(warmup, sub, f'{gid}.shaders')))
	for source, target in moves:
		if not os.path.exists(source) or os.path.exists(target):
			continue
		shutil.move(source, target)
		print(f'caches:   {os.path.relpath(source, ROOT)} is {gid}\'s')


# A seed file another program made (<file>.program: its size and time) is made again.
def program_stamp(path):
	st = os.stat(path)
	return f'{st.st_size} {st.st_mtime_ns}'


def all_cpus_mask():
	cpus = os.cpu_count() or 1
	return -1 if cpus >= 64 else (1 << cpus) - 1


def mask_cpus(mask):
	return [cpu for cpu in range(64) if mask & (1 << cpu)]


def parse_mask(value):
	value = str(value).strip()
	if not value:
		return 0
	if value.lower().startswith('0x'):
		return int(value, 16)
	return int(value, 16) if any(c in 'abcdefABCDEF' for c in value) else int(value)


def _cpu_list(path):
	try:
		text = read_text(path).strip()
	except OSError:
		return []
	cpus = []
	for part in text.split(','):
		if '-' in part:
			a, b = part.split('-')
			cpus.extend(range(int(a), int(b) + 1))
		elif part:
			cpus.append(int(part))
	return cpus


# A hybrid CPU's performance cores (Intel: /sys/devices/cpu_core) without the core of CPU 0, within the allowed
# CPUs: a list such as "1,2,3,4,5", or '' when every core is alike (the threads are left to Linux there).
def performance_cpus(allowed):
	core = _cpu_list('/sys/devices/cpu_core/cpus')
	atom = _cpu_list('/sys/devices/cpu_atom/cpus')
	if not core or not atom:
		return ''
	interrupts = set(_cpu_list('/sys/devices/system/cpu/cpu0/topology/thread_siblings_list') or [0])
	return ','.join(str(c) for c in core if c not in interrupts and c < 64 and allowed & (1 << c))


# The efficiency cores of a hybrid CPU as an affinity mask, or 0.
def efficiency_mask():
	if not _cpu_list('/sys/devices/cpu_core/cpus'):
		return 0
	mask = 0
	for cpu in _cpu_list('/sys/devices/cpu_atom/cpus'):
		if cpu < 63:
			mask |= 1 << cpu
	return mask


# Dialogs (tkinter): a message with a button per choice and an optional check box: the chosen index (-1: closed)
# and whether the box was checked.
def show_choice(message, choices, checkbox=''):
	import tkinter as tk
	from tkinter import ttk
	result = {'choice': -1}
	root = tk.Tk()
	root.title('KytyPS5')
	root.resizable(False, False)
	root.attributes('-topmost', True)
	frame = ttk.Frame(root, padding=16)
	frame.pack()
	ttk.Label(frame, text=message, wraplength=560, justify='left').pack(anchor='w')
	checked = tk.BooleanVar(value=False)
	if checkbox:
		ttk.Checkbutton(frame, text=checkbox, variable=checked).pack(anchor='w', pady=(10, 0))
	row = ttk.Frame(frame)
	row.pack(anchor='w', pady=(12, 0))
	for i, text in enumerate(choices):
		def pick(i=i):
			result['choice'] = i
			root.destroy()
		ttk.Button(row, text=text, command=pick).pack(side='left', padx=(0, 6))
	root.update_idletasks()
	x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
	y = (root.winfo_screenheight() - root.winfo_reqheight()) // 3
	root.geometry(f'+{x}+{y}')
	root.mainloop()
	return result['choice'], checked.get()


# A folder dialog (KDE's when there is one): the chosen folder or ''.
def choose_folder(title, start=''):
	start = start if start and os.path.isdir(start) else os.path.expanduser('~')
	if shutil.which('kdialog'):
		r = subprocess.run(['kdialog', '--title', title, '--getexistingdirectory', start], capture_output=True, text=True)
		return r.stdout.strip() if r.returncode == 0 else ''
	if shutil.which('zenity'):
		r = subprocess.run(['zenity', '--file-selection', '--directory', '--title', title, '--filename', start + '/'],
		                   capture_output=True, text=True)
		return r.stdout.strip() if r.returncode == 0 else ''
	import tkinter as tk
	from tkinter import filedialog
	root = tk.Tk()
	root.withdraw()
	folder = filedialog.askdirectory(title=title, initialdir=start)
	root.destroy()
	return folder or ''


def choose_file(title, start='', pattern='*.zar'):
	start = start if start and os.path.isdir(start) else os.path.expanduser('~')
	if shutil.which('kdialog'):
		r = subprocess.run(['kdialog', '--title', title, '--getopenfilename', start, f'ZArchive ({pattern})'],
		                   capture_output=True, text=True)
		return r.stdout.strip() if r.returncode == 0 else ''
	if shutil.which('zenity'):
		r = subprocess.run(['zenity', '--file-selection', '--title', title, '--filename', start + '/',
		                    '--file-filter', f'ZArchive | {pattern}'], capture_output=True, text=True)
		return r.stdout.strip() if r.returncode == 0 else ''
	import tkinter as tk
	from tkinter import filedialog
	root = tk.Tk()
	root.withdraw()
	path = filedialog.askopenfilename(title=title, initialdir=start, filetypes=[('ZArchive', pattern)])
	root.destroy()
	return path or ''
