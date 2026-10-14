#!/usr/bin/env python3
# Static shader and pipeline precompile (the port of precompile-windows.ps1):
#   ./precompile.sh                 every shader and pipeline of the game into the static pipeline cache
#                                   _PipelineCache/static/<title>_<version>.*: with a driver that has
#                                   VK_KHR_pipeline_binary (RADV, NVIDIA 5xx) the pipelines' binaries,
#                                   <title>_<version>.binaries, read only when a pipeline is needed; without them,
#                                   each pipeline's own pipeline cache data, <title>_<version>.blobs
#   ./precompile.sh --jobs 8        8 processes at a time (default: 3 threads each on the allowed CPUs)
#   ./precompile.sh --coverage      no pipelines, only what the seeds compile to
#   ./precompile.sh --inputs-only   only the compiled inputs the emulator's shader prefetch translates in the
#                                   background (_PipelineCache/static/<title>_<version>.shaders; every full run
#                                   writes them too)
#   ./precompile.sh --affinity 0xF0 only these CPUs (hex mask)
# The work is split into shards, a lower-priority process each (kyty_shader_precompile --shard i/n), whose caches
# are merged into the static cache at the end; a shard that exits with code 3 runs again as two. The specialization
# hints the package ships (tools/local/static-precompile/hints-<title>_<version>.hints) are completed with the code
# of the seed file into hinted-<title>_<version>.seeds (--apply-hints) and compiled too. An interrupted run resumes:
# finished shards are merged first, and what the static cache holds is not compiled again.
import argparse
import collections
import json
import math
import os
import shutil
import signal
import struct
import subprocess
import sys
import time
from datetime import datetime

import kyty_common as kc

p = argparse.ArgumentParser(description='KytyPS5 (Linux): the full shader and pipeline precompile')
p.add_argument('--game', default='')
p.add_argument('--seeds', default='')
p.add_argument('--recorded', default='*')
p.add_argument('--jobs', type=int, default=0)
p.add_argument('--threads', type=int, default=3)
p.add_argument('--shards', type=int, default=512)
p.add_argument('--affinity', default='0')
p.add_argument('--coverage', action='store_true')
p.add_argument('--inputs-only', action='store_true')
p.add_argument('--exe', default=kc.TOOL)
a = p.parse_args()

if not os.path.isfile(a.exe):
	sys.exit(f'missing {a.exe}')


# Closing the terminal (SIGHUP) or SIGTERM stops the run as Ctrl+C does: the shards are stopped, the next run continues.
def interrupted(signum, frame):
	raise KeyboardInterrupt


signal.signal(signal.SIGINT, signal.default_int_handler)  # (also when started in the background)
signal.signal(signal.SIGHUP, interrupted)
signal.signal(signal.SIGTERM, interrupted)

last = kc.last_game()
kc.rename_title_caches(last)
game = os.path.abspath(a.game or last)
info = kc.read_game_param(game)
if not info:
	sys.exit(f'no sce_sys/param.json in {game} (--game <folder or .zar>, or start the game once to choose it)')
gid = f"{info['titleId']}_{info['contentVersion']}"
default_seeds = not a.seeds
seeds = os.path.abspath(a.seeds) if a.seeds else os.path.join(kc.ROOT, f'seeds-{gid}.seeds')
# The seed file another program made (<file>.program: its size and time) is made again, and replaced where it lists
# something else: the static cache is then older than it, out of date (--status), and the precompile compiles what is new.
stamp_now = kc.program_stamp(a.exe)
made_by = seeds + '.program'
remake = default_seeds and os.path.isfile(seeds) and (not os.path.isfile(made_by) or
                                                       kc.read_text(made_by).strip() != stamp_now)
if not os.path.isfile(seeds) or remake:
	# Every shader the game ships, with the pipelines it draws them with (from the game files, by the program).
	os.makedirs(os.path.dirname(seeds), exist_ok=True)
	made = seeds + '.new' if remake else seeds
	if subprocess.run([a.exe, '--game', game, '--make-seeds', made, '--states', kc.PASS_STATES], cwd=kc.ROOT).returncode:
		sys.exit('making the seed file failed (kyty_shader_precompile --make-seeds)')
	if remake:
		with open(made, 'rb') as f1, open(seeds, 'rb') as f2:
			same = f1.read() == f2.read()
		if same:
			os.remove(made)
		else:
			os.replace(made, seeds)
	kc.write_text(made_by, stamp_now)
recorded = a.recorded
if recorded == '*':
	recorded = os.path.join(os.path.dirname(seeds), f'recorded-{gid}.seeds')
	hints = os.path.join(kc.ROOT, 'tools', 'local', 'static-precompile', f'hints-{gid}.hints')
	if not os.path.isfile(recorded) and os.path.isfile(hints):
		# (Made again each run: the hints of this package, the code of this seed file.)
		recorded = os.path.join(os.path.dirname(seeds), f'hinted-{gid}.seeds')
		if subprocess.run([a.exe, '--game', game, '--seeds', seeds, '--apply-hints', hints, '--out', recorded],
		                  cwd=kc.ROOT).returncode:
			print('the specialization hints could not be applied (kyty_shader_precompile --apply-hints): the seeds alone')
			recorded = ''


# The pipeline recipes of a seed file (its body after the identity line and checksum: the records, each its word
# count and words, then the recipes' count).
def seed_pipelines(path):
	with open(path, 'rb') as f:
		while f.read(1) not in (b'\n', b''):
			pass
		f.read(8)
		(records,) = struct.unpack('<I', f.read(4))
		for _ in range(records):
			(words,) = struct.unpack('<I', f.read(4))
			f.seek(words * 4, os.SEEK_CUR)
		return struct.unpack('<I', f.read(4))[0]


affinity = kc.parse_mask(a.affinity)
if affinity == 0:
	config = os.path.join(kc.ROOT, 'launch.json')
	if os.path.isfile(config):
		for cpu in json.loads(kc.read_text(config)).get('cpu_affinity', []):
			affinity |= 1 << int(cpu)
every = kc.all_cpus_mask()
mask = affinity & every
if mask == 0:
	mask = every
cpu_list = kc.mask_cpus(mask)
cpus = len(cpu_list)
# A process scales to a few threads (4: 85%), and each translates the programs its share needs.
jobs = a.jobs if a.jobs > 0 else max(1, math.ceil(cpus / a.threads))
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
logs = os.path.join(kc.LOGS, f'{stamp}-precompile')
log_name = os.path.relpath(logs, kc.ROOT)
os.makedirs(logs, exist_ok=True)
begin = time.time()

# Each process gets an empty driver disk cache of its own (NVIDIA's and Mesa's), removed when it is done (on the
# disk: the system temp folder is in RAM on SteamOS).
driver_caches = os.path.join(kc.TMP, f'kyty-precompile-{stamp}')
claims = None


def lower_priority():
	os.nice(10)  # Windows' below-normal priority: the PC stays usable
	os.sched_setaffinity(0, cpu_list)


def start(name, arguments):
	cache = os.path.join(driver_caches, name)
	os.makedirs(cache, exist_ok=True)
	env = dict(os.environ)
	env['__GL_SHADER_DISK_CACHE_PATH'] = cache
	env['MESA_SHADER_CACHE_DIR'] = cache
	env['TMPDIR'] = kc.TMP
	if claims:
		env['KYTY_PRECOMPILE_CLAIMS'] = claims
	with open(os.path.join(logs, f'{name}.out.log'), 'wb') as fo, open(os.path.join(logs, f'{name}.err.log'), 'wb') as fe:
		process = subprocess.Popen([a.exe, '--game', game] + arguments, cwd=kc.ROOT, env=env, stdout=fo, stderr=fe,
		                           preexec_fn=lower_priority)
	process.driver_cache = cache
	return process


def remove_cache(process):
	shutil.rmtree(process.driver_cache, ignore_errors=True)


def wait(process, what):
	process.wait()
	remove_cache(process)
	if process.returncode != 0:
		raise RuntimeError(f'{what} failed (exit code {process.returncode}); logs: {log_name}')


def clock(seconds):
	seconds = int(seconds)
	return f'{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}'


print(f'precompile: {seeds}, {a.shards} shards, {jobs} at a time, affinity 0x{mask & 0xFFFFFFFFFFFFFFFF:X}; logs {log_name}')
running = {}
code = 0
try:
	if a.coverage:
		out = os.path.splitext(seeds)[0] + '.compiled.shaders'
		wait(start('coverage', ['--seeds', seeds, '--no-pipelines', '--threads', str(cpus), '--out', out]), 'coverage')
		print(f'wrote {out}')
		sys.exit(0)
	# The compiled inputs for the emulator's shader prefetch: the seeds translated as the full run does, without
	# pipelines (half a minute).
	inputs = ['--seeds', seeds, '--no-pipelines', '--threads', str(cpus), '--static-inputs']
	if a.inputs_only:
		wait(start('inputs', inputs), 'inputs')
		print(f'wrote _PipelineCache/static/{gid}.shaders')
		sys.exit(0)
	# The shards an interrupted run finished first: what they hold is not compiled again.
	wait(start('merge-before', ['--merge']), 'merge')
	# The plan: every pipeline of the run with the work item that makes it first (a dry run of each seed file on all
	# CPUs, a minute or two); the shards then compile each pipeline once.
	plan = os.path.join(logs, 'plan.bin')
	print('  planning (a dry run of the seeds)')
	wait(start('plan-seeds', ['--seeds', seeds, '--dry-run', '--plan', plan, '--threads', str(cpus)]), 'plan')
	if recorded and os.path.isfile(recorded):
		wait(start('plan-recorded', ['--seeds', recorded, '--dry-run', '--plan', plan, '--threads', str(cpus)]), 'plan')
	pending = collections.deque((seeds, f'{i}/{a.shards}') for i in range(a.shards))
	if recorded and os.path.isfile(recorded):
		# About as many pipelines a shard as the seeds' (100: a recording of every world holds about 16000).
		count = max(1, math.ceil(seed_pipelines(recorded) / 100))
		pending.extend((recorded, f'{i}/{count}') for i in range(count))
	# The shards share the pipelines they hold: one that the seeds of several shards make is compiled once.
	claims = os.path.join(driver_caches, 'claims')
	finished = split = 0
	shown = time.time()
	total = len(pending)
	print(f'  {total} shards to compile')
	while pending or running:
		while pending and len(running) < jobs:
			seed_file, shard = pending.popleft()
			name = 'shard' + shard.replace('/', 'of') + '-' + os.path.splitext(os.path.basename(seed_file))[0]
			running[name] = (seed_file, shard, start(name, ['--seeds', seed_file, '--shard', shard, '--threads',
			                                                str(a.threads), '--plan', plan]))
		time.sleep(0.25)
		for name in list(running):
			seed_file, shard, process = running[name]
			if process.poll() is None:
				continue
			del running[name]
			remove_cache(process)
			if process.returncode == 3:
				i, n = (int(x) for x in shard.split('/'))
				if n >= 65536:
					raise RuntimeError(f'{name} cannot be split further; logs: {log_name}')
				pending.append((seed_file, f'{i}/{2 * n}'))
				pending.append((seed_file, f'{i + n}/{2 * n}'))
				split += 1
			elif process.returncode != 0:
				raise RuntimeError(f'{name} failed (exit code {process.returncode}); logs: {log_name}')
			else:
				finished += 1
		if time.time() - shown >= 60:
			shown = time.time()
			print(f'  {clock(shown - begin)} shards: {finished} done, {len(running)} running, {len(pending)} waiting '
			      f'({split} split)', flush=True)
	claims = None
	print('  merging')
	wait(start('merge', ['--merge', '--prune']), 'merge')
	print('  making the shader prefetch inputs')
	wait(start('inputs', inputs), 'inputs')
	static = os.path.join(kc.ROOT, '_PipelineCache', 'static')
	caches = [os.path.join(static, gid + ext) for ext in ('.bin', '.binaries', '.blobs')]
	caches = sorted((c for c in caches if os.path.isfile(c)), key=os.path.getmtime)
	if caches:
		print(f'done in {clock(time.time() - begin)}: {caches[-1]} ({os.path.getsize(caches[-1]) / (1 << 20):,.0f} MB; '
		      f'{split} shards split)')
	else:
		print(f'done in {clock(time.time() - begin)} ({split} shards split)')
except KeyboardInterrupt:
	print('\nstopped: running it again continues where it stopped')
	code = 130
except RuntimeError as e:
	print(e)
	code = 1
finally:
	# A failed shard ends the run: the others are stopped too.
	for _, _, process in running.values():
		if process.poll() is None:
			process.kill()
			process.wait()
	shutil.rmtree(driver_caches, ignore_errors=True)
sys.exit(code)
