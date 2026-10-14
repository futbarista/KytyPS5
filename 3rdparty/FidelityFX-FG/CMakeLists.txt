# AMD FidelityFX SDK v1.1.4 (MIT, LICENSE.txt): the part FSR 3.1 frame generation needs on Vulkan (ffx-api with its frame
# generation and Vulkan frame interpolation swapchain providers, the Vulkan backend, frame interpolation, optical flow),
# built for Linux (KYTY_FRAMEGEN=fsr, src/local/frame-gen.cpp). shaders-vk holds the SDK's Vulkan shader permutation
# headers, made by its own FidelityFX_SC.exe (linux/tools/ffx-compile-shaders.py, under Wine); compat the Win32 and MSVC
# CRT pieces the SDK uses (threads, events, critical sections, the performance counter, the _s string functions).
# The SDK's own changes for Linux: no D3D12 driver providers in ffx_provider.cpp, FFX_API_ENTRY without __declspec,
# larger opaque contexts (4-byte wchar_t), no Win32 fullscreen-exclusive structs, MSVC-only casts and temporaries.
set(FFX ${CMAKE_CURRENT_SOURCE_DIR})
add_library(ffx_framegen STATIC
	${FFX}/ffx-api/src/ffx_api.cpp ${FFX}/ffx-api/src/ffx_provider.cpp ${FFX}/ffx-api/src/ffx_provider_framegeneration.cpp
	${FFX}/ffx-api/src/validation.cpp ${FFX}/ffx-api/src/backends.cpp
	${FFX}/ffx-api/src/vk/ffx_provider_framegenerationswapchain_vk.cpp
	${FFX}/sdk/src/backends/vk/ffx_vk.cpp
	${FFX}/sdk/src/backends/vk/FrameInterpolationSwapchain/FrameInterpolationSwapchainVK.cpp
	${FFX}/sdk/src/backends/vk/FrameInterpolationSwapchain/FrameInterpolationSwapchainVK_DebugPacing.cpp
	${FFX}/sdk/src/backends/vk/FrameInterpolationSwapchain/FrameInterpolationSwapchainVK_Helpers.cpp
	${FFX}/sdk/src/backends/vk/FrameInterpolationSwapchain/FrameInterpolationSwapchainVK_UiComposition.cpp
	${FFX}/sdk/src/backends/shared/ffx_shader_blobs.cpp
	${FFX}/sdk/src/backends/shared/blob_accessors/ffx_frameinterpolation_shaderblobs.cpp
	${FFX}/sdk/src/backends/shared/blob_accessors/ffx_opticalflow_shaderblobs.cpp
	${FFX}/sdk/src/components/frameinterpolation/ffx_frameinterpolation.cpp
	${FFX}/sdk/src/components/opticalflow/ffx_opticalflow.cpp
	${FFX}/sdk/src/shared/ffx_assert.cpp ${FFX}/sdk/src/shared/ffx_message.cpp
	${FFX}/sdk/src/shared/ffx_breadcrumbs_list.cpp ${FFX}/sdk/src/shared/ffx_object_management.cpp)
target_include_directories(ffx_framegen PRIVATE ${FFX}/compat ${FFX}/shaders-vk ${FFX}/ffx-api/src ${FFX}/sdk/include/FidelityFX/host
	${FFX}/sdk/src/shared ${FFX}/sdk/src/backends/shared ${FFX}/sdk/src/backends/vk ${FFX}/sdk/src/components)
target_include_directories(ffx_framegen PUBLIC ${FFX}/ffx-api/include ${FFX}/sdk/include)
target_link_libraries(ffx_framegen PUBLIC Vulkan::Headers)
target_compile_definitions(ffx_framegen PRIVATE FFX_BACKEND_VK FFX_FI FFX_OF FFX_GCC FFXDLL_VERSION_MAJOR=1
	FFXDLL_VERSION_MINOR=0 FFXDLL_VERSION_PATCH=1 FFXDLL_VERSION_API=VK CI_PIPELINE_ID=0)
target_compile_options(ffx_framegen PRIVATE -include ${FFX}/compat/ffx_linux_compat.h -w -fno-strict-aliasing)
set_target_properties(ffx_framegen PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
# The SDK calls the Vulkan loader's exports: the libvulkan.so.1 SDL loads (the same instance of the loader).
find_library(KYTY_VULKAN_LOADER NAMES vulkan libvulkan.so.1 REQUIRED)
target_link_libraries(ffx_framegen PUBLIC ${KYTY_VULKAN_LOADER} Threads::Threads)
