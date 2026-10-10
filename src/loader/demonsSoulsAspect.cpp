#include "loader/demonsSoulsAspect.h"

#include "common/virtualMemory.h"
#include "graphics/host_gpu/hostMemory.h"
#include "graphics/host_gpu/renderer/demonsSouls.h"
#include "kernel/memory.h"
#include "loader/guestCode.h"
#include "loader/runtimeLinker.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace Loader::DemonsSoulsAspect {
namespace {
constexpr float SixteenByNine = 16.0f / 9.0f;

// The store of 16:9 into the renderer's settings (mov dword [rbx+4], imm32; the immediate at +3).
constexpr std::string_view StoreAspect = "c7 43 04 39 8e e3 3f";
constexpr uint64_t         StoreAspectAt = 3;

// 01.007.000's camera constants: the float's offset from the eboot's base and the bytes around it.
struct Constant {
	uint64_t                 offset;
	std::array<uint8_t, 20> bytes; // 8 before, the float, 8 after
};
constexpr std::array<Constant, 2> Constants {{
    {0x237efac, {0xdb, 0x0f, 0x49, 0xc1, 0xb5, 0x3f, 0x7d, 0x3b, 0x39, 0x8e, 0xe3, 0x3f, 0xfe, 0xff, 0xff, 0xff, 0xa5,
                 0xaa, 0x2a, 0x3d}},
    {0x24f8814, {0xcd, 0xcc, 0x4c, 0x3e, 0x37, 0x20, 0x40, 0x3f, 0x39, 0x8e, 0xe3, 0x3f, 0xcd, 0xcc, 0xcc, 0x3d, 0x00,
                 0x80, 0x3b, 0x45}},
}};

float RequestedAspect() {
	const char* text = std::getenv("KYTY_UI_ASPECT");
	return text != nullptr ? std::strtof(text, nullptr) : 0.0f;
}

// Writes a float into guest memory that may be read-only (the constants' segment), restoring its protection.
bool WriteFloat(uint64_t address, float value) {
	Common::VirtualMemory::Mode old_mode {};
	if (!Libs::LibKernel::Memory::ProtectGuestMemory(address & ~uint64_t {0x3fff}, 0x8000,
	                                                Common::VirtualMemory::Mode::ReadWrite, &old_mode)) {
		return false;
	}
	std::memcpy(reinterpret_cast<void*>(address), &value, sizeof(value));
	Libs::LibKernel::Memory::ProtectGuestMemory(address & ~uint64_t {0x3fff}, 0x8000, old_mode);
	return true;
}
} // namespace

void Install(Program* program) {
	const float aspect = RequestedAspect();
	if (aspect <= SixteenByNine + 0.01f || program == nullptr || !Libs::Graphics::DemonsSouls::IsSupportedGame() ||
	    program->file_name.filename() != "eboot.bin") {
		return;
	}
	int patched = 0;
	if (const auto site = GuestCode::FindUnique(*program, GuestCode::Pattern(StoreAspect))) {
		// Executable code stays writable for loader patches until the modules start.
		std::memcpy(reinterpret_cast<void*>(*site + StoreAspectAt), &aspect, sizeof(aspect));
		Common::VirtualMemory::FlushInstructionCache(*site + StoreAspectAt, sizeof(aspect));
		patched++;
	}
	for (const auto& constant: Constants) {
		const uint64_t start = program->base_vaddr + constant.offset - 8;
		if (constant.offset + 12 > program->mapped_size ||
		    !Libs::Graphics::HostMemoryRangeIsReadable(start, constant.bytes.size()) ||
		    std::memcmp(reinterpret_cast<const void*>(start), constant.bytes.data(), constant.bytes.size()) != 0) {
			continue;
		}
		if (WriteFloat(start + 8, aspect)) patched++;
	}
	std::printf("Demon's Souls ultrawide: camera aspect ratio %.4f in %d of 3 places%s\n", aspect, patched,
	            patched == 3 ? "" : " (not 01.007.000?)");
}
} // namespace Loader::DemonsSoulsAspect
