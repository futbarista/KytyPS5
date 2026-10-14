#!/usr/bin/env python3
# The FidelityFX SDK v1.1.4 Vulkan shader permutation headers that FSR 3.1 frame generation needs (frame interpolation
# and optical flow), made with the SDK's own FidelityFX_SC.exe (a Windows program) under Proton's Wine: the same commands
# as sdk/include/FidelityFX/gpu/CMakeCompileShaders.txt. Usage: ffx-compile-shaders.py <sdk dir> <output dir> [wine]
import glob, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sdk, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
wine = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser(
	'~/.local/share/Steam/compatibilitytools.d/GE-Proton11-7-x86_64/files/bin/wine')
env = dict(os.environ, WINEDEBUG='-all', WINEPREFIX=os.environ.get('WINEPREFIX', os.path.join(os.path.dirname(out), 'wineprefix-ffx')))
sc = os.path.join(sdk, 'sdk/tools/binary_store/FidelityFX_SC.exe')
gpu = os.path.join(sdk, 'sdk/include/FidelityFX/gpu')
shaders = os.path.join(sdk, 'sdk/src/backends/vk/shaders')
win = lambda p: 'Z:' + p.replace('/', '\\')
api = ['-compiler=glslang', '-e', 'CS', '--target-env', 'vulkan1.2', '-S', 'comp', '-Os', '-DFFX_GLSL=1']
effects = {
	'frameinterpolation': (['-DFFX_FRAMEINTERPOLATION_OPTION_UPSAMPLE_SAMPLERS_USE_DATA_HALF=0',
	                        '-DFFX_FRAMEINTERPOLATION_OPTION_ACCUMULATE_SAMPLERS_USE_DATA_HALF=0',
	                        '-DFFX_FRAMEINTERPOLATION_OPTION_REPROJECT_SAMPLERS_USE_DATA_HALF=1',
	                        '-DFFX_FRAMEINTERPOLATION_OPTION_POSTPROCESSLOCKSTATUS_SAMPLERS_USE_DATA_HALF=0',
	                        '-DFFX_FRAMEINTERPOLATION_OPTION_UPSAMPLE_USE_LANCZOS_TYPE=2', '-reflection', '-deps=gcc', '-DFFX_GPU=1'],
	                       ['-DFFX_FRAMEINTERPOLATION_OPTION_LOW_RES_MOTION_VECTORS={0,1}',
	                        '-DFFX_FRAMEINTERPOLATION_OPTION_JITTER_MOTION_VECTORS={0,1}',
	                        '-DFFX_FRAMEINTERPOLATION_OPTION_INVERTED_DEPTH={0,1}'],
	                       sorted(glob.glob(f'{shaders}/frameinterpolation/*.glsl'))),
	'opticalflow': (['-reflection', '-deps=gcc', '-DFFX_GPU=1'], ['-DFFX_OPTICALFLOW_OPTION_HDR_COLOR_INPUT={0,1}'],
	                [f'{shaders}/opticalflow/ffx_opticalflow_{n}.glsl' for n in (
	                    'prepare_luma_pass', 'compute_luminance_pyramid_pass', 'generate_scd_histogram_pass',
	                    'compute_scd_divergence_pass', 'compute_optical_flow_advanced_pass_v5',
	                    'filter_optical_flow_pass_v5', 'scale_optical_flow_advanced_pass_v5')]),
}
os.makedirs(out, exist_ok=True)
jobs = []
for effect, (base, perms, files) in effects.items():
	includes = [f'-I{win(gpu)}', f'-I{win(gpu + "/" + effect)}']
	for f in files:
		name = os.path.splitext(os.path.basename(f))[0]
		for suffix, half in (('', 0), ('_wave64', 0), ('_16bit', 1), ('_wave64_16bit', 1)):
			jobs.append([wine, sc] + base + api + perms + [f'-name={name}{suffix}', f'-DFFX_HALF={half}'] + includes +
			            [f'-output={win(out)}', win(f)])

def run(cmd):
	r = subprocess.run(cmd, env=env, cwd=out, capture_output=True, text=True)
	return r.returncode, cmd[-1], (r.stdout + r.stderr)[-600:]

failed = 0
with ThreadPoolExecutor(3) as pool:  # (each SC uses every CPU itself)
	for code, f, log in pool.map(run, jobs):
		if code != 0:
			failed += 1
			print(f'FAILED {f}\n{log}')
print(f'{len(jobs) - failed}/{len(jobs)} permutation sets in {out}')
sys.exit(1 if failed else 0)
