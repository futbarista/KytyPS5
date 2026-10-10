#pragma once
// KYTY_SHADER_PREFETCH_WAIT=1: the game starts only once the shader prefetch (pipelineCache.cpp, the whole game's
// shaders translated in the background) is done, its progress on the start-up screen, all CPU threads on it;
// else the game starts at once and stutters on the shaders not translated yet. The prefetch publishes its state
// here for the loader (runtimeLinker.cpp), which waits before the game's modules start.
#include <atomic>
#include <cstdint>
#include <cstdlib>

namespace PrefetchWait {
enum : uint32_t { NotStarted = 0, Loading = 1, Running = 2, Finished = 3 };
inline std::atomic<uint32_t> g_state {NotStarted};
inline std::atomic<uint64_t> g_done {0}, g_total {0};

inline bool Requested() {
	static const bool requested = [] {
		const char* value = std::getenv("KYTY_SHADER_PREFETCH_WAIT");
		return value != nullptr && *value != '\0' && *value != '0';
	}();
	return requested;
}
} // namespace PrefetchWait
