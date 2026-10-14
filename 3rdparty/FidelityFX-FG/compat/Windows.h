// The Win32 calls the FidelityFX SDK v1.1.4 Vulkan frame interpolation swapchain makes (events, threads, critical
// sections, the performance counter), on C++ threads for Linux (FSR 3.1 frame generation in KytyPS5).
#pragma once
#include <pthread.h>
#include <time.h>
#include <unistd.h>

#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cwchar>
#include <mutex>
#include <new>
#include <thread>

typedef void*          HANDLE;
typedef void*          HMODULE;
typedef void*          LPVOID;
typedef void           VOID;
typedef int32_t        HRESULT;
typedef uint32_t       DWORD;
typedef int            BOOL;
typedef uint64_t       UINT64;
typedef unsigned int   UINT;
typedef DWORD (*LPTHREAD_START_ROUTINE)(LPVOID);
#define WINAPI
#define INFINITE        0xFFFFFFFFu
#define WAIT_OBJECT_0   0u
#define WAIT_TIMEOUT    258u
#define WAIT_FAILED     0xFFFFFFFFu
#define S_OK            ((HRESULT)0)
#define E_FAIL          ((HRESULT)0x80004005)
#define SUCCEEDED(hr)   (((HRESULT)(hr)) >= 0)
#define FAILED(hr)      (((HRESULT)(hr)) < 0)
#define TRUE            1
#define FALSE           0
#define THREAD_PRIORITY_HIGHEST 2
#define THREAD_PRIORITY_NORMAL  0
#define CP_UTF8         65001

typedef union _LARGE_INTEGER {
	struct {
		uint32_t LowPart;
		int32_t  HighPart;
	};
	int64_t QuadPart;
} LARGE_INTEGER;

inline BOOL QueryPerformanceCounter(LARGE_INTEGER* value) {
	timespec t {};
	clock_gettime(CLOCK_MONOTONIC, &t);
	value->QuadPart = static_cast<int64_t>(t.tv_sec) * 1000000000 + t.tv_nsec;
	return TRUE;
}
inline BOOL QueryPerformanceFrequency(LARGE_INTEGER* value) {
	value->QuadPart = 1000000000;
	return TRUE;
}
inline void Sleep(DWORD ms) {
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

struct CRITICAL_SECTION {
	alignas(std::recursive_mutex) unsigned char storage[sizeof(std::recursive_mutex)];
};
inline std::recursive_mutex& KytyCs(CRITICAL_SECTION* cs) {
	return *std::launder(reinterpret_cast<std::recursive_mutex*>(cs->storage));
}
inline void InitializeCriticalSection(CRITICAL_SECTION* cs) { new (cs->storage) std::recursive_mutex(); }
inline void DeleteCriticalSection(CRITICAL_SECTION* cs) { KytyCs(cs).~recursive_mutex(); }
inline void EnterCriticalSection(CRITICAL_SECTION* cs) { KytyCs(cs).lock(); }
inline void LeaveCriticalSection(CRITICAL_SECTION* cs) { KytyCs(cs).unlock(); }

// Events and threads share HANDLE: each object says what it is.
struct KytyWin32Object {
	enum Kind { Event, Thread } kind;
	std::mutex              mutex;
	std::condition_variable changed;
	bool                    signaled = false;
	bool                    manual   = false;
	std::thread             thread;
	explicit KytyWin32Object(Kind k): kind(k) {}
};

inline HANDLE CreateEventW(void*, BOOL manual_reset, BOOL initial_state, const wchar_t*) {
	auto* e     = new KytyWin32Object(KytyWin32Object::Event);
	e->manual   = manual_reset != 0;
	e->signaled = initial_state != 0;
	return e;
}
inline HANDLE CreateEventA(void* a, BOOL m, BOOL i, const char*) { return CreateEventW(a, m, i, nullptr); }
#define CreateEvent CreateEventW
inline BOOL SetEvent(HANDLE h) {
	auto* e = static_cast<KytyWin32Object*>(h);
	{
		std::lock_guard lock(e->mutex);
		e->signaled = true;
	}
	e->changed.notify_all();
	return TRUE;
}
inline BOOL ResetEvent(HANDLE h) {
	auto* e = static_cast<KytyWin32Object*>(h);
	std::lock_guard lock(e->mutex);
	e->signaled = false;
	return TRUE;
}

inline HANDLE CreateThread(void*, size_t, LPTHREAD_START_ROUTINE start, LPVOID parameter, DWORD, DWORD* id) {
	auto* t   = new KytyWin32Object(KytyWin32Object::Thread);
	t->thread = std::thread([t, start, parameter] {
		start(parameter);
		{
			std::lock_guard lock(t->mutex);
			t->signaled = true;
		}
		t->changed.notify_all();
	});
	if (id != nullptr) *id = 0;
	return t;
}

inline DWORD WaitForSingleObject(HANDLE h, DWORD ms) {
	auto* o = static_cast<KytyWin32Object*>(h);
	if (o == nullptr) return WAIT_FAILED;
	std::unique_lock lock(o->mutex);
	if (ms == INFINITE) {
		o->changed.wait(lock, [o] { return o->signaled; });
	} else if (!o->changed.wait_for(lock, std::chrono::milliseconds(ms), [o] { return o->signaled; })) {
		return WAIT_TIMEOUT;
	}
	if (o->kind == KytyWin32Object::Event && !o->manual) o->signaled = false;  // auto-reset
	return WAIT_OBJECT_0;
}

inline BOOL CloseHandle(HANDLE h) {
	auto* o = static_cast<KytyWin32Object*>(h);
	if (o == nullptr) return FALSE;
	if (o->kind == KytyWin32Object::Thread && o->thread.joinable()) {
		// A thread handle is closed after its thread was waited for (or the thread keeps running on its own).
		if (o->signaled) o->thread.join(); else o->thread.detach();
	}
	delete o;
	return TRUE;
}

inline HANDLE GetCurrentThread() { return nullptr; }
inline BOOL SetThreadPriority(HANDLE, int) { return TRUE; }
inline HRESULT SetThreadDescription(HANDLE, const wchar_t* name) {
	char buffer[16] {};
	for (int i = 0; i < 15 && name != nullptr && name[i] != 0; i++) buffer[i] = static_cast<char>(name[i] < 128 ? name[i] : '?');
	pthread_setname_np(pthread_self(), buffer);
	return S_OK;
}
inline void OutputDebugStringA(const char* text) { fputs(text, stderr); }
inline void OutputDebugStringW(const wchar_t* text) { fprintf(stderr, "%ls", text); }
#define OutputDebugString OutputDebugStringW
#define TEXT(x) L##x
