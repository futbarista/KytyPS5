#!/usr/bin/env python3
# Adds (or updates) a non-Steam shortcut in every Steam user's config/shortcuts.vdf (binary VDF). Steam must be closed:
# it writes the file when it exits. Usage: steam-shortcut.py <name> <exe> <start dir> [launch options] [compat tool]
import binascii, glob, os, shutil, sys, time

def read_vdf(data, i=0):
	out = {}
	while True:
		t = data[i]; i += 1
		if t == 8:
			return out, i
		end = data.index(b'\0', i); key = data[i:end].decode('utf-8', 'replace'); i = end + 1
		if t == 0:
			out[key], i = read_vdf(data, i)
		elif t == 1:
			end = data.index(b'\0', i); out[key] = data[i:end].decode('utf-8', 'replace'); i = end + 1
		elif t == 2:
			out[key] = int.from_bytes(data[i:i + 4], 'little', signed=True); i += 4
		else:
			raise ValueError(f'type {t}')

def write_vdf(d):
	b = b''
	for k, v in d.items():
		kk = k.encode() + b'\0'
		if isinstance(v, dict):
			b += b'\0' + kk + write_vdf(v) + b'\x08'
		elif isinstance(v, int):
			b += b'\x02' + kk + (v & 0xFFFFFFFF).to_bytes(4, 'little')
		else:
			b += b'\x01' + kk + str(v).encode() + b'\0'
	return b

name, exe, start = sys.argv[1:4]
options = sys.argv[4] if len(sys.argv) > 4 else ''
compat = sys.argv[5] if len(sys.argv) > 5 else ''
quoted = f'"{exe}"'
appid = (binascii.crc32((quoted + name).encode()) | 0x80000000)
signed = appid - (1 << 32)
for config in glob.glob(os.path.expanduser('~/.local/share/Steam/userdata/*/config')):
	path = os.path.join(config, 'shortcuts.vdf')
	shortcuts = {}
	if os.path.isfile(path):
		shutil.copy2(path, path + f'.bak-{time.strftime("%Y%m%d-%H%M%S")}')
		root, _ = read_vdf(open(path, 'rb').read(), 1 + len('shortcuts') + 1)
		shortcuts = root
	entries = [e for e in shortcuts.values() if e.get('AppName', e.get('appname')) != name]
	entry = {'appid': signed, 'AppName': name, 'Exe': quoted, 'StartDir': f'"{start}"', 'icon': '', 'ShortcutPath': '',
	         'LaunchOptions': options, 'IsHidden': 0, 'AllowDesktopConfig': 1, 'AllowOverlay': 1, 'OpenVR': 0,
	         'Devkit': 0, 'DevkitGameID': '', 'DevkitOverrideAppID': 0, 'LastPlayTime': 0, 'FlatpakAppID': '', 'tags': {}}
	entries.append(entry)
	data = b'\0shortcuts\0' + write_vdf({str(i): e for i, e in enumerate(entries)}) + b'\x08\x08'
	open(path, 'wb').write(data)
	print(f'{path}: {name} (appid {appid}, steam://rungameid/{(appid << 32) | 0x02000000})')
	if compat:
		# The compatibility tool (Proton) of the shortcut: config.vdf's CompatToolMapping, a text VDF.
		cfg = os.path.join(os.path.dirname(os.path.dirname(config)), '..', 'config', 'config.vdf')
		cfg = os.path.normpath(os.path.expanduser('~/.local/share/Steam/config/config.vdf'))
		text = open(cfg, encoding='utf-8').read()
		marker = '"CompatToolMapping"'
		at = text.find(marker)
		if at >= 0 and f'"{appid}"' not in text[at:at + 200000]:
			brace = text.index('{', at) + 1
			text = text[:brace] + f'\n\t\t\t\t\t"{appid}"\n\t\t\t\t\t{{\n\t\t\t\t\t\t"name"\t\t"{compat}"\n\t\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t\t"priority"\t\t"250"\n\t\t\t\t\t}}' + text[brace:]
			shutil.copy2(cfg, cfg + f'.bak-{time.strftime("%Y%m%d-%H%M%S")}')
			open(cfg, 'w', encoding='utf-8').write(text)
			print(f'{cfg}: {appid} -> {compat}')
