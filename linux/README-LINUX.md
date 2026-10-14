# KytyPS5 v20261013 — build dla Linuksa / SteamOS

Ten sam kod co release `v20261013` z https://github.com/chenxiao07/KytyPS5 (commit `3e6ee3ec`), zbudowany
natywnie dla Linuksa, z tymi samymi ustawieniami co paczka Windows: clang 19, `-O3 -march=x86-64-v3`, ThinLTO
oraz te same przełączniki emulatora (`launch.json` = `run-windows.json` z release'u). Pełna instrukcja gry
(sterowanie, opcje, wymagania) jest w `README.md` (oryginał z paczki Windows); ten plik opisuje tylko różnice.

## Odpowiedniki plików Windows

| Windows | Linux | Co robi |
| --- | --- | --- |
| `launcher.cmd` / `launcher.ps1` | `launcher.sh` / `launcher-linux.py` lub **`KytyPS5 Launcher.desktop`** | Okno ustawień: folder gry, rozdzielczość, pełny ekran, język, 120 fps, render height, przyciski Play / Precompile shaders / Logs folder / README |
| `run.cmd` / `run-windows.ps1` | `run.sh` / `run-linux.py` lub `KytyPS5 Play.desktop` | Start gry z konsolą pokazującą log (dialogi wersji gry i prekompilacji, lista shaderów przy pierwszym starcie, wejścia do tła) |
| `precompile.cmd` / `precompile-windows.ps1` | `precompile.sh` / `precompile-linux.py` lub `KytyPS5 Precompile.desktop` | Pełna prekompilacja wszystkich shaderów i pipeline'ów do `_PipelineCache/static` (shardy, plan, hinty z paczki, scalanie, wznawianie po przerwaniu) |
| `kyty_emulator.exe`, `kyty_shader_precompile.exe` | `kyty_emulator`, `kyty_shader_precompile` | Programy |
| `zarchive.exe` (osobno) | `zarchive` | Pakowanie folderu gry do `.zar`: `./zarchive <folder> <plik.zar>` |

Opcje mają linuksowe nazwy: `-Fullscreen` → `--fullscreen`, `-AspectFit` → `--aspect-fit`, `-Width 1920` →
`--width 1920`, `-Game <folder>` → `--game <folder>`, `-Language 16` → `--language 16`, `-RenderHeight 1080` →
`--render-height 1080`, `-Fps120` → `--fps120`, `-Set K=V` → `--set K=V`, `-DryRun` → `--dry-run`. Pełna lista:
`./run.sh --help` i `./precompile.sh --help`.

## Prekompilacja shaderów

Działa tak samo jak na Windows. Sterownik RADV (Mesa) obsługuje `VK_KHR_pipeline_binary`, więc wynik to magazyn
`_PipelineCache/static/PPSA01341_01.007.000.binaries`, który gra czyta pipeline po pipeline, tak jak na NVIDII.
Uruchom ją przyciskiem „Precompile shaders”, przez `KytyPS5 Precompile.desktop` albo wybierając „Precompile first”
w dialogu przy starcie. Zamknięcie okna (lub Ctrl+C) przerywa pracę, a kolejne uruchomienie kontynuuje od miejsca
przerwania. **Po aktualizacji Mesy (aktualizacji SteamOS) trzeba ją powtórzyć**, tak jak po aktualizacji
sterownika na Windows; launcher sam o to zapyta.

Cache'y z Windows (`_PipelineCache`) nie da się użyć: należą do sterownika Windows.

## Różnice względem Windows

- **Red-zone protection** jest w launcherze wyszarzona. Na Windows obsługa wyjątków nadpisuje red zone gościa,
  natomiast na Linuksie sygnały ją omijają, a emulator ma tę opcję tylko w buildzie Windows.
- Rdzenie P/E: wykrywane przez `/sys/devices/cpu_core` (Intel hybrid). Na CPU AMD wątki zostawiamy
  schedulerowi, tak jak Windows robi to na CPU bez rdzeni E.
- Pliki tymczasowe emulatora (4–5 GB podczas gry) trafiają do `_Tmp` w tym folderze zamiast do `/tmp`, bo na
  SteamOS `/tmp` siedzi w RAM-ie.
- Każdy shard prekompilacji dostaje własny, pusty cache sterownika (`MESA_SHADER_CACHE_DIR`, jak
  `__GL_SHADER_DISK_CACHE_PATH` na Windows), który jest usuwany po zakończeniu shardu.
- DLSS Frame Generation (`-FrameGen`) działa tylko na Windows z NVIDIĄ, więc go tu nie ma.

## Tryb gry (Gaming Mode)

W Desktop Mode kliknij prawym przyciskiem `KytyPS5 Launcher.desktop` (lub `KytyPS5 Play.desktop`) i wybierz
„Add to Steam”. W trybie gry nie ma konsoli. Log jest jak zwykle w `logs/`.

## Przebudowa

Źródło: `/home/deck/Emulation/KytyPS5-src` (tag `v20261013` + `linux/linux-port.patch`, czyli linuksowe
odpowiedniki fragmentów forka, które były tylko dla Windows). Polecenie `linux/build-linux.sh` buduje wszystko
w kontenerze distrobox `kyty-build` (Ubuntu 24.04, clang 19) i aktualizuje tę paczkę.
