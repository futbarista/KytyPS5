#pragma once

#include <cstdint>

namespace Loader {
struct Program;
namespace DemonsSoulsAspect {
// KYTY_UI_ASPECT=<screen width / height> wider than 16:9 (an ultrawide screen the emulator stretches its 16:9
// image to fill): the camera's aspect ratio, 16:9 in three places of 01.007.000's eboot (an immediate the
// renderer setup stores, and two constants the camera defaults read), becomes the screen's, so the wider view
// keeps its proportions once stretched. The interface is narrowed by the renderer (renderDraw.cpp, UiAspect).
void Install(Program* program);
} // namespace DemonsSoulsAspect
} // namespace Loader
