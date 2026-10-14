#!/usr/bin/env python3
# Linux launcher (the port of run-windows.ps1): runs the Linux build with the switches of a launch config.
#   ./run.sh                          the release package's switches (launch.json), 2560x1440
#   ./run.sh --precompile             compile every recorded shader and pipeline, then exit
#                                     (every shader of the game: precompile.sh)
#   ./run.sh --baseline               no performance switches
#   ./run.sh --config <launch.json>   another checkpoint's switches
#   ./run.sh --width 1920 --height 1080 --fullscreen
#   ./run.sh --patch <cheat.json>     apply an etaHEN-style game patch
#   ./run.sh --fullscreen --aspect-fit keep the game's 16:9 (black bars) instead of stretching
#   ./run.sh --language 11            the console language (0-29 as the PS5 numbers them: 1 English (US), 16 Polish)
#   ./run.sh --set KEY=VALUE          override a switch of the config (KEY= removes it)
#   ./run.sh --fps120                 the game's frame rate up to 120 fps instead of 60 (movies play faster)
#   ./run.sh --vblank 240             another virtual vblank rate (default 60, the console's)
#   ./run.sh --render-height 1080     Demon's Souls renders its 3D at 1920x1080 instead of 2560x1440 (720-1440)
#   ./run.sh --game <folder>          the game (the folder with eboot.bin); remembered in game-path.txt, a folder
#                                     dialog when none is known
#   ./run.sh --game <file.zar>        the game folder packed into a ZArchive (read without extracting it)
#   ./run.sh --affinity FFFFCF        only these CPUs (hex mask; default: the config's list, else all)
#   ./run.sh --prompt                 a dialog first when the game version is untested or the shaders are not
#                                     precompiled for this GPU (run.sh passes it)
#   ./run.sh --follow                 stay open showing the run log until the game exits, then its exit code
#   ./run.sh --fps-hud                the game's frames a second in the corner of the window
#   ./run.sh --dry-run                print environment and command only
# --no-redzone is accepted and does nothing: the red-zone protection is for Windows, whose exception dispatch
# writes over the guest's SysV red zone; Linux signal delivery skips it (the emulator has the option on Windows only).
import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime

import kyty_common as kc

p = argparse.ArgumentParser(description='KytyPS5 (Linux): starts the game')
p.add_argument('--config', default=os.path.join(kc.ROOT, 'launch.json'))
p.add_argument('--game', default='')
p.add_argument('--exe', default=kc.EXE)
p.add_argument('--width', type=int, default=0)
p.add_argument('--height', type=int, default=0)
p.add_argument('--fullscreen', action='store_true')
p.add_argument('--baseline', action='store_true')
p.add_argument('--precompile', action='store_true')
p.add_argument('--threads', type=int, default=0)
p.add_argument('--no-redzone', action='store_true')
p.add_argument('--no-aot', action='store_true')
p.add_argument('--present-mode', default='')
p.add_argument('--vblank', type=int, default=0)
p.add_argument('--fps120', action='store_true')
p.add_argument('--render-height', type=int, default=0)
p.add_argument('--set', action='append', default=[])
p.add_argument('--patch', default='')
p.add_argument('--aspect-fit', action='store_true')
p.add_argument('--fps-hud', action='store_true')
p.add_argument('--language', type=int, default=-1)
p.add_argument('--affinity', default='')
p.add_argument('--prompt', action='store_true')
p.add_argument('--follow', action='store_true')
p.add_argument('--dry-run', action='store_true')
a = p.parse_args()

if not os.path.isfile(a.exe):
	sys.exit(f'missing {a.exe}')

# The game: --game, else the last one given, else the default folder; a folder dialog when that has no eboot.bin.
remember = bool(a.game)
last = kc.last_game()
if not a.dry_run:
	kc.rename_title_caches(last)
game = a.game or last
if not remember and not kc.test_game(game):
	chosen = kc.choose_folder('Choose the game folder (the one with eboot.bin and sce_sys)', os.path.dirname(game))
	if chosen:
		game = chosen
		remember = True
if not kc.test_game(game):
	sys.exit(f'no eboot.bin in {game} (nor a .zar archive)')
game = os.path.abspath(game)
if remember:
	kc.write_text(kc.GAME_FILE, game)
# Its title and version (sce_sys/param.json): the emulator is tested with one of them.
param = kc.read_game_param(game)
title_id = param.get('titleId', '') if param else ''
version = f"{title_id} {param.get('contentVersion')}" if param else 'unknown'
title_name = kc.title_name(param) if param else None
tested = version in kc.TESTED_VERSIONS

launch = json.loads(kc.read_text(a.config))

# Emulator options: everything after the binary in the command, minus --game.
command = list(launch.get('command', []))
start = command.index('--') + 2 if '--' in command else 1
options = []
i = start
while i < len(command):
	if command[i] == '--game':
		i += 2
		continue
	options.append(command[i])
	i += 1


def set_option(name, value):
	if name in options:
		options[options.index(name) + 1] = value
	else:
		options.extend([name, value])


if a.width > 0:
	set_option('--screen-width', str(a.width))
if a.height > 0:
	set_option('--screen-height', str(a.height))
if a.fullscreen:
	options.append('--fullscreen')
if a.present_mode:
	set_option('--present-mode', a.present_mode)
if a.language >= 0:
	set_option('--console-language', str(a.language))
# The flip queue, one flip per vblank, caps the game's frame rate: at the console's 60 Hz the game runs at most
# 60 fps. --fps120: a 120 Hz vblank, the game's own frames up to 120 fps; play keeps its speed, movies play faster.
set_option('--vblank-frequency', str(a.vblank if a.vblank > 0 else 120 if a.fps120 else 60))
if a.patch:
	set_option('--game-patch', os.path.abspath(a.patch))

# Environment switches.
env = {}
if not a.baseline:
	for key, value in launch.get('environment', {}).items():
		if key == 'KYTY_SRT_AOT_LIBRARY':
			# A Linux config's ahead-of-time SRT library (a .so of the build tree); a release has none.
			if not a.no_aot and os.path.isfile(str(value)):
				env[key] = str(value)
			continue
		env[key] = str(value)

# CPU affinity: --affinity, else the config's list, else every CPU; only CPUs this PC has.
every = kc.all_cpus_mask()
mask = kc.parse_mask(a.affinity) if a.affinity else 0
if not a.affinity:
	for cpu in launch.get('cpu_affinity', []):
		mask |= 1 << int(cpu)
mask &= every
if mask == 0:
	mask = every
cpus = len(kc.mask_cpus(mask))

# The render thread on the recording worker's CPUs; "auto" (the package's config) picks the performance cores of
# a hybrid CPU (below), else leaves both to Linux.
if 'KYTY_RENDER_CPUS' not in env and 'KYTY_RECORDING_CPUS' in env:
	env['KYTY_RENDER_CPUS'] = env['KYTY_RECORDING_CPUS']
# Image staging copies on the upload worker too.
if env.get('KYTY_ASYNC_UPLOAD') == '1':
	env['KYTY_ASYNC_UPLOAD'] = '2'
# The same defaults run-windows.ps1 adds over the config (see its comments for the measurements).
if not a.baseline:
	for key, value in (('KYTY_BUFFER_RECLAIM', '1'), ('KYTY_DRAW_PACKETS', '1'), ('KYTY_PARTIAL_IMAGE_DIRTY', '1'),
	                   ('KYTY_PARTIAL_ROW_BANDS', '1'), ('KYTY_ASYNC_XPR_PIPELINES', '1'),
	                   ('KYTY_NATIVE_XPR_RELOCATE', '1'), ('KYTY_NATIVE_XPR_STORE_BUDGET', '256'),
	                   ('KYTY_NATIVE_XPR_KEEP_FRAMES', '600'), ('KYTY_NATIVE_XPR_INSTANCES', '1')):
		env.setdefault(key, value)
	# Demon's Souls' own engine settings: no XPR index-buffer culling (the PC GPU draws the triangles instead).
	if title_id == 'PPSA01341':
		env.setdefault('KYTY_GAME_CONVARS', 'doIndexBufferCulling=false')
if a.render_height > 0 and a.render_height != 1440:
	env['KYTY_RENDER_HEIGHT'] = str(a.render_height)
if not a.baseline:
	env.setdefault('KYTY_UNMAP_PROTECT_SKIP', '1')
# The key of the driver pipeline cache (_PipelineCache/local/<key>), one for every build (as on Windows).
env['KYTY_DRIVER_CACHE_KEY'] = '1f3c29b70e536c8f5a5e812e793b33ac2eb6858b4810ed98ca2a51b9fa5eed97'
if a.precompile:
	env['KYTY_SHADER_WARMUP'] = '1'
	env['KYTY_SHADER_WARMUP_ONLY'] = '1'
	env['KYTY_SHADER_WARMUP_THREADS'] = str(cpus)
	env.pop('KYTY_SHADER_WARMUP_SECONDS', None)
else:
	os.environ.pop('KYTY_SHADER_WARMUP_ONLY', None)
	# At most a minute of start-up warmup; the rest are built at their first use and cached from then on.
	env.setdefault('KYTY_SHADER_WARMUP_SECONDS', '60')
if a.threads > 0:
	env['KYTY_SHADER_WARMUP_THREADS'] = str(a.threads)
# Stutters in the log: frames, shader translations and pipeline creations of 100 ms or more.
env.setdefault('KYTY_HITCH_LOG_MS', '100')
if a.aspect_fit:
	env['KYTY_PRESENT_ASPECT'] = 'fit'
# --fps-hud: the emulator's own frame counter in the corner (the game's frames a second, KYTY_FPS_HUD).
if a.fps_hud:
	env['KYTY_FPS_HUD'] = '1'
# --set KEY=VALUE overrides a switch of the config; KEY= drops it. Several: --set A=1,B=2.
for item in a.set:
	for pair in re.split(r',(?=[A-Za-z_][A-Za-z0-9_]*=)', item):
		key, _, value = pair.partition('=')
		if value:
			env[key] = value
		else:
			env.pop(key, None)
			os.environ.pop(key, None)
if 'auto' in (env.get('KYTY_RECORDING_CPUS'), env.get('KYTY_RENDER_CPUS')):
	performance = kc.performance_cpus(mask)
	for key in ('KYTY_RECORDING_CPUS', 'KYTY_RENDER_CPUS'):
		if env.get(key) != 'auto':
			continue
		if performance:
			env[key] = performance
		else:
			env.pop(key)

quoted = ['--game', game] + options
stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
untested = '' if tested else f" (untested: the emulator is tested with {' and '.join(kc.TESTED_VERSIONS)})"
print(f"game:     {title_name + ', ' if title_name else ''}{version}{untested}")
print(f"config:   {a.config}{' (baseline: no switches)' if a.baseline else ''}{' (precompile)' if a.precompile else ''}")
render = f"; render threads on CPUs {env['KYTY_RENDER_CPUS']}" if env.get('KYTY_RENDER_CPUS') else ''
print(f'affinity: 0x{mask & 0xFFFFFFFFFFFFFFFF:X} ({cpus} CPUs){render}')
print(f'switches: {len(env)}')
print(f"command:  {a.exe} {' '.join(repr(x) if ' ' in x else x for x in quoted)}")
if a.dry_run:
	for key, value in env.items():
		print(f'  {key}={value}')
	sys.exit(0)


def set_affinity():
	if mask != every:
		os.sched_setaffinity(0, kc.mask_cpus(mask))


# Shaders, from the seed file (every shader of the game) by the precompile program: the shader prefetch's inputs
# for this GPU and driver (_PipelineCache/static/<title>_<version>.shaders), made when missing or stale; and the
# static pipeline cache, the whole game compiled ahead by precompile.sh, offered by --prompt.
tool = os.path.join(os.path.dirname(a.exe), 'kyty_shader_precompile')
seed_name = f"seeds-{title_id}_{param['contentVersion']}.seeds" if param and title_id and param.get('contentVersion') else 'seeds.seeds'
seeds = os.path.join(kc.ROOT, seed_name)
seeds = seeds if os.path.isfile(seeds) else ''
stamp_now = kc.program_stamp(tool) if os.path.isfile(tool) else ''
stale_seeds = bool(seeds and stamp_now and (not os.path.isfile(seeds + '.program') or
                                           kc.read_text(seeds + '.program').strip() != stamp_now))
if (not seeds or stale_seeds) and not a.precompile and os.path.isfile(tool) and os.path.isfile(kc.PASS_STATES):
	target = seeds or os.path.join(kc.ROOT, seed_name)
	made = target + '.new' if stale_seeds else target
	print(f"shaders:  listing the game's shaders from its files {'again (another precompile program)' if stale_seeds else '(once)'}")
	r = subprocess.run([tool, '--game', game, '--make-seeds', made, '--states', kc.PASS_STATES], cwd=kc.ROOT,
	                   stdout=subprocess.DEVNULL)
	if r.returncode == 0 and os.path.isfile(made):
		if stale_seeds:
			with open(made, 'rb') as f1, open(target, 'rb') as f2:
				same = f1.read() == f2.read()
			if same:
				os.remove(made)
			else:
				os.replace(made, target)
		kc.write_text(target + '.program', stamp_now)
		seeds = target
	elif not stale_seeds:
		print('shaders:  listing failed: the game compiles its shaders when they first appear')
shaders = not a.precompile and bool(seeds) and os.path.isfile(tool)


# The precompile program on the launch's CPUs, its output in the console or a file: its exit code.
def invoke_tool(arguments, output=None):
	r = subprocess.run([tool, '--game', game, '--seeds', seeds] + arguments, cwd=kc.ROOT, preexec_fn=set_affinity,
	                   stdout=output)
	return r.returncode


inputs_ready = cache_ready = cache_outdated = False
if shaders:
	with tempfile.TemporaryFile(mode='w+') as status_file:
		shaders = invoke_tool(['--status'], status_file) == 0
		status_file.seek(0)
		status = status_file.read()
	inputs_ready = 'inputs current' in status
	# Outdated: made from the seeds of an older precompile program, which listed fewer of the game's shaders.
	cache_outdated = 'static cache outdated' in status
	static = os.path.join(kc.ROOT, '_PipelineCache', 'static')
	# A precompile that stopped before its last merge keeps its shards' checkpoints.
	shard_left = os.path.isdir(static) and any('.shard' in n and os.path.getsize(os.path.join(static, n)) > 1 << 20
	                                           for n in os.listdir(static))
	cache_ready = 'static cache current' in status and not shard_left
	state = 'ready' if cache_ready else 'out of date (precompile.sh compiles what is new)' if cache_outdated else 'not made (precompile.sh)'
	print(f"shaders:  prefetch inputs {'ready' if inputs_ready else 'to be made'}, static pipeline cache {state}")

# --prompt: the game version and the precompile, before anything starts.
no_prompt = os.path.join(kc.ROOT, 'no-precompile-prompt.txt')
offer = shaders and not cache_ready and not os.path.exists(no_prompt)
if a.prompt and (offer or not tested):
	info = f"Game: {title_name or 'unknown'} ({version})"
	info += ', a tested version.' if tested else (f"\n⚠ This version is untested (the emulator was tested with "
	                                             f"{' and '.join(kc.TESTED_VERSIONS)}): it may not run or may fail.")
	if offer:
		minutes = math.ceil(55 * 22 / cpus / 10) * 10
		duration = f'about {minutes} minutes' if minutes < 90 else f'about {minutes / 60:.1f} hours'
		if cache_outdated:
			message = (f"{info}\n\nThis version of the emulator precompiles more of the game's shaders than the one that "
			           f"made the precompiled shaders on this PC: the new ones would stutter the first time they appear.\n"
			           f"Precompiling again compiles only what is new (minutes; at most {duration} on this PC, with the CPU "
			           f"fully loaded; closing its window stops it, and the next run continues).")
		else:
			message = (f"{info}\n\nThe shaders are not precompiled for this graphics card yet: scenes and effects stutter "
			           f"the first time they appear in the game (a fraction of a second to a few seconds).\n"
			           f"The precompile compiles every shader of the game once: {duration} on this PC (with the CPU fully "
			           f"loaded; closing its window stops it, and the next run continues). It is needed only once, and "
			           f"again after a graphics driver (Mesa) update.")
		choice, never = kc.show_choice(message, ['Precompile first, then start the game', 'Start the game now', 'Quit'],
		                               "Don't ask about precompiling again")
		if never:
			kc.write_text(no_prompt, 'run.sh --prompt: no precompile dialog (delete this file to get it back)\n')
		if choice not in (0, 1):
			print('cancelled')
			sys.exit(0)
		if choice == 0:
			r = subprocess.run([sys.executable, os.path.join(kc.ROOT, 'precompile-linux.py'), '--game', game,
			                    '--affinity', hex(mask & 0xFFFFFFFFFFFFFFFF)])
			if r.returncode == 0:
				inputs_ready = True  # the full run ends with them
			else:
				print(f'precompile failed (exit code {r.returncode}); starting the game anyway')
	else:
		choice, _ = kc.show_choice(info, ['Start the game', 'Quit'])
		if choice != 0:
			print('cancelled')
			sys.exit(0)

# Memory: the emulator takes about 20 GB of RAM while a save loads and uses about 4 GB of it in play; with less
# RAM Linux swaps the rest out and loading is slower. What it maps in all is about 34 GB (RAM plus swap).
meminfo = {}
with open('/proc/meminfo') as f:
	for line in f:
		key, value = line.split(':', 1)
		meminfo[key] = int(value.split()[0]) * 1024
ram = meminfo.get('MemTotal', 0)
room = meminfo.get('MemAvailable', 0) + meminfo.get('SwapFree', 0)
GB = 1 << 30
memory = []
if ram < 24 * GB:
	memory.append(f'This PC has {ram / GB:.0f} GB of RAM: the game runs, but loading takes longer (the emulator takes '
	              f'about 20 GB while a save loads and uses about 4 GB in play; 32 GB recommended).')
if room < 34 * GB:
	memory.append(f'Only {room / GB:.0f} GB of memory (free RAM plus swap) is available and the emulator may use about '
	              f'34 GB: it may be closed in the middle of the game. Close other programs, or add swap.')
for line in memory:
	print(f'memory:   {line}')
if memory and a.prompt:
	choice, _ = kc.show_choice('\n\n'.join(memory), ['Start the game anyway', 'Quit'])
	if choice != 0:
		print('cancelled')
		sys.exit(0)

if shaders and not inputs_ready:
	print('shaders:  making the background shader preparation inputs for this graphics card (first run or after a '
	      'driver update: about a minute)')
	if invoke_tool(['--no-pipelines', '--static-inputs', '--threads', str(cpus)]) != 0:
		print('shaders:  making them failed; no background shader preparation this time')

child_env = dict(os.environ)
child_env.update(env)
os.makedirs(kc.TMP, exist_ok=True)
child_env['TMPDIR'] = kc.TMP
os.makedirs(kc.LOGS, exist_ok=True)
out = os.path.join(kc.LOGS, f'{stamp}.out.log')
err = os.path.join(kc.LOGS, f'{stamp}.err.log')
with open(out, 'wb') as fo, open(err, 'wb') as fe:
	process = subprocess.Popen([a.exe] + quoted, cwd=kc.ROOT, env=child_env, stdout=fo, stderr=fe,
	                           preexec_fn=set_affinity)
print(f'pid {process.pid}; logs: logs/{stamp}.*.log')


def describe(code):
	if code < 0:
		try:
			return f'{code} ({signal.Signals(-code).name})'
		except ValueError:
			return str(code)
	return str(code)


def tail(path, count):
	try:
		with open(path, 'rb') as f:
			return f.read().decode('utf-8', 'replace').splitlines()[-count:]
	except OSError:
		return []


if not a.precompile and a.follow:
	# The run log in this window as it is written; the exit code (and the error log's end) when the game ends.
	try:
		with open(out, 'rb') as reader:
			while True:
				exited = process.poll() is not None
				text = reader.read()
				if text:
					sys.stdout.write(text.decode('utf-8', 'replace'))
					sys.stdout.flush()
				if exited:
					break
				time.sleep(0.25)
	except KeyboardInterrupt:
		process.terminate()
		process.wait()
	code = process.returncode
	print()
	print(f'The game exited with code {describe(code)}; logs: {kc.LOGS}/{stamp}.*.log')
	if code != 0:
		for line in tail(err, 20):
			print(line)
	sys.exit(code if code >= 0 else 128 - code)
if not a.precompile:
	sys.exit(0)

# Precompile: follow the warmup progress until the emulator exits.
begin = time.time()
shown = 0
pattern = re.compile('warmup|precompile|pipeline cache')
while True:
	exited = process.poll() is not None
	lines = [line for line in tail(out, 1 << 30) if pattern.search(line)]
	for line in lines[shown:]:
		print(f'  {line}')
	shown = len(lines)
	if exited:
		break
	time.sleep(0.5)
print(f'exit code {describe(process.returncode)} after {time.time() - begin:.0f} s')
sys.exit(process.returncode if process.returncode >= 0 else 1)
