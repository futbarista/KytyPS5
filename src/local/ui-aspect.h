#pragma once
// KYTY_UI_ASPECT=<screen width / height>: Demon's Souls on a screen wider than 16:9 (renderDraw.cpp narrows the
// interface, loader/demonsSoulsAspect.cpp widens the camera). Shared with the presenter: while a movie plays
// (the video decoder decodes frames) the image is shown 16:9 with black bars, not stretched.
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>

namespace UiAspectShared {
// Interface-over-scene passes so far (renderDraw.cpp counts them, the presenter compares between flips).
inline std::atomic<uint32_t> g_scene_frames {0};
// The presenter shows frames 16:9 (no scene): the interface is then not narrowed either (the opening movie
// is drawn into the interface layer).
inline std::atomic<bool> g_fitting {false};

// 16:9 / the screen's ratio (1 when not wider than 16:9).
inline float Scale() {
	static const float scale = [] {
		const char* text  = std::getenv("KYTY_UI_ASPECT");
		const float ratio = text != nullptr ? std::strtof(text, nullptr) : 0.0f;
		return ratio > 16.0f / 9.0f ? (16.0f / 9.0f) / ratio : 1.0f;
	}();
	return scale;
}

// The game's movies (the opening, the logos) go through the video decoder: its last frame's time.
inline std::atomic<int64_t> g_last_video_frame {0};
inline int64_t              NowMs() {
	return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch())
	    .count();
}
inline void NoteVideoFrame() {
	g_last_video_frame.store(NowMs(), std::memory_order_relaxed);
}

// Called once per presented frame: true while a movie plays (a frame decoded in the last half second).
inline bool FitWithoutScene() {
	if (Scale() >= 1.0f) return false;
	const int64_t last = g_last_video_frame.load(std::memory_order_relaxed);
	const bool    fit  = last != 0 && NowMs() - last < 500;
	g_fitting.store(fit, std::memory_order_relaxed);
	return fit;
}
} // namespace UiAspectShared
