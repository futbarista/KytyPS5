#pragma once
// KYTY_UI_ASPECT=<screen width / height>: Demon's Souls on a screen wider than 16:9 (renderDraw.cpp narrows the
// interface, loader/demonsSoulsAspect.cpp widens the camera). Shared with the presenter: frames without the
// game's scene (logos, the opening movie: no pass blends the interface over a scene) are shown 16:9 with black
// bars, not stretched.
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

// Called once per presented frame: true once no scene was drawn for half a second (the title menu draws its
// scene at a lower rate than the screen's, and a frame presented before its scene pass was counted would
// flicker the bars), false again at the next scene.
inline bool FitWithoutScene() {
	if (Scale() >= 1.0f) return false;
	using Clock = std::chrono::steady_clock;
	static uint32_t          last = 0;
	static Clock::time_point last_scene = Clock::now();
	const uint32_t           now = g_scene_frames.load(std::memory_order_relaxed);
	const auto               time = Clock::now();
	if (now != last) {
		last       = now;
		last_scene = time;
	}
	const bool fit = time - last_scene > std::chrono::milliseconds(500);
	g_fitting.store(fit, std::memory_order_relaxed);
	return fit;
}
} // namespace UiAspectShared
