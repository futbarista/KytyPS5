# Saros (PPSA07631) – experimental branch

> **Status: EXPERIMENT, not a fix.** Do not merge. This branch makes Saros get further than the
> official build, but it ends in a GPU hang (`ErrorDeviceLost`). It is kept as a record of what
> was tried and what was learned.

Base: official commit `5a88080` (build `KytyPS5-2026-10-08-5a88080`).
Test machine: Windows 11 Pro, AMD Ryzen 5 9600X, AMD Radeon RX 9070 XT (driver 32.0.31041.1004), 32 GB RAM.

Related upstream issues: KytyPS5/KytyPS5#1053, KytyPS5/KytyPS5#260.

## Behaviour on the official build

The game boots fine: intro video, language/subtitle settings and the autosave notice all work.
Right after confirming the autosave notice the emulator aborts:

```
shader resource tracking: hash=0xb9da5e64f4c5b10a stage=compute pc=0x00000084
buffer descriptor is not a valid runtime value; GPU-selected access requires a scalar,
raw DWORD x1/x2/x3/x4, or formatted X load   (ResourceTracking.cpp)
```

## What was found

Extra diagnostics (op type in the error message) show the failing accesses are not loads:

| # | Shader hash | pc | Operation | Result |
|---|---|---|---|---|
| 1 | `0xb9da5e64f4c5b10a` (compute) | `0x84` | `StoreBufferU32` (32-bit, untyped, unformatted) | fatal in ResourceTracking |
| 2 | `0x26ea14a341c67c0f` (compute) | `0x1a8` | `BufferAtomicOr32` | fatal in ResourceTracking (after #1 allowed) |
| 3 | – | – | renderer: "scalar resource reads overlap a shader buffer write" (`descriptors.cpp`, `CommitBindings`) | fatal (after #2 allowed) |
| 4 | – | – | `vkQueueSubmit failed: ErrorDeviceLost` (AMD driver TDR) | GPU hang (after #3 downgraded to a warning) |

The descriptor for these accesses is selected on the GPU at runtime, so the recompiler falls back
to the generic "IndirectBuffer" path, which only supports 32-bit loads.

### Why the existing descriptor-table support does not catch it

The recompiler already has a matcher for GPU-selected *store* descriptors read from a descriptor
table (`TryMakeIndirectBuffer` in `ResourceTracking.cpp`). With per-`return false` logging
(branch `fix/saros-descriptor-table`) shader `0xb9da5e64f4c5b10a` is rejected at the very first
check of the store itself:

```cpp
if (memory.kind != ResourceKind::Buffer || memory.typed || memory.formatted ||
    memory.idxen || !memory.offen || !ImmediateU32(inst.Arg(3), scalar) || scalar != 0u)
    return false;   // <- Saros fails here
```

So the store uses an addressing form the matcher does not accept (index-enabled, no offset
register, or a non-zero/non-immediate SOFFSET). Which of these exactly is the next thing to log.
Extending this matcher is most likely the proper fix, because it keeps writes on the normal,
tracked buffer path.

## What this branch changes (the hack)

- `ShaderIR.h`: `SupportsIndirectBufferStore` / `SupportsIndirectBufferAtomic` (32-bit, untyped, unformatted).
- `ResourceTracking.cpp`, `Program.cpp`: accept those ops on `IndirectBuffer`; the failure message now includes op/kind/typed/formatted/bits/dwords.
- `spirvEmitterMemory.cpp`: `StoreBdaDword`, `StoreIndirectBuffer`, indirect path in `EmitAtomic32` – writes/atomics go **directly to guest memory through buffer device address**.
- `SpirvEmitter.cpp`: validator allows Write/Atomic users of an indirect buffer handle.
- `descriptors.cpp`: "scalar resource reads overlap a shader buffer write" downgraded from `EXIT` to a one-time warning.

## Known problems

1. **GPU writes bypass ownership tracking.** The emulator deliberately refuses writable FLAT/GLOBAL
   addresses ("require GPU ownership tracking"). This branch writes to guest memory anyway, so the
   CPU side and the buffer cache do not know the memory changed.
2. **Overlap check disabled.** Shaders are specialised on scalar reads of memory that the same
   submission writes; with the check downgraded, specialisation can use stale data.
3. **GPU hang.** Shortly after the overlap warning the GPU hangs (AMD TDR, `ErrorDeviceLost`).
   The desktop wallpaper may disappear after the driver reset.
4. Only 32-bit untyped/unformatted stores and atomics are handled; 64-bit and float atomics are not.

## Suggested next steps

- Log which sub-condition of the store check fails for `0xb9da5e64f4c5b10a` (idxen / offen / SOFFSET)
  and extend `TryMakeIndirectBuffer` / `MatchDescriptorTable` to accept it.
- Do the same for the atomic in `0x26ea14a341c67c0f` (the matcher currently only allows `StoreBufferU32`).
- Drop the BDA write path and the overlap downgrade once the matcher handles these shaders.
