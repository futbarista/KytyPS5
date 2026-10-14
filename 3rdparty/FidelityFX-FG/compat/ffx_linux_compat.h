// Force-included into the FidelityFX SDK v1.1.4 sources built for Linux (FSR 3.1 frame generation in KytyPS5): the
// MSVC CRT pieces the SDK uses without including them.
#pragma once
#ifdef __cplusplus
#include <codecvt>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <cmath>
#include <locale>
#include <string>

#ifndef _countof
template <typename T, size_t N>
char (&KytyFfxCountofHelper(T (&)[N]))[N];
#define _countof(a) (sizeof(KytyFfxCountofHelper(a)))
#endif

inline int wcscpy_s(wchar_t* dst, size_t size, const wchar_t* src) {
	if (dst == nullptr || size == 0) return 22;
	if (src == nullptr) { dst[0] = 0; return 22; }
	size_t n = wcslen(src);
	if (n >= size) n = size - 1;
	wmemcpy(dst, src, n);
	dst[n] = 0;
	return 0;
}
template <size_t N>
inline int wcscpy_s(wchar_t (&dst)[N], const wchar_t* src) { return wcscpy_s(dst, N, src); }

inline int strcpy_s(char* dst, size_t size, const char* src) {
	if (dst == nullptr || size == 0) return 22;
	if (src == nullptr) { dst[0] = 0; return 22; }
	size_t n = strlen(src);
	if (n >= size) n = size - 1;
	memcpy(dst, src, n);
	dst[n] = 0;
	return 0;
}
template <size_t N>
inline int strcpy_s(char (&dst)[N], const char* src) { return strcpy_s(dst, N, src); }

inline int sprintf_s(char* dst, size_t size, const char* format, ...) {
	va_list args;
	va_start(args, format);
	const int r = vsnprintf(dst, size, format, args);
	va_end(args);
	return r;
}
template <size_t N, typename... Args>
inline int sprintf_s(char (&dst)[N], const char* format, Args... args) { return snprintf(dst, N, format, args...); }

inline int swprintf_s(wchar_t* dst, size_t size, const wchar_t* format, ...) {
	va_list args;
	va_start(args, format);
	const int r = vswprintf(dst, size, format, args);
	va_end(args);
	return r;
}
template <size_t N, typename... Args>
inline int swprintf_s(wchar_t (&dst)[N], const wchar_t* format, Args... args) { return swprintf(dst, N, format, args...); }
#endif
