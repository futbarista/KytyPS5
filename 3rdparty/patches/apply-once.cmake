# Applies PATCH to the current directory unless it is applied already (a CMake re-run re-runs FetchContent's patch step
# over the patched checkout, which `git apply` alone refuses).
execute_process(COMMAND "${GIT}" apply --ignore-whitespace --reverse --check "${PATCH}" RESULT_VARIABLE applied
                OUTPUT_QUIET ERROR_QUIET)
if(NOT applied EQUAL 0)
	execute_process(COMMAND "${GIT}" apply --ignore-whitespace "${PATCH}" RESULT_VARIABLE result)
	if(NOT result EQUAL 0)
		message(FATAL_ERROR "patch failed: ${PATCH}")
	endif()
endif()
