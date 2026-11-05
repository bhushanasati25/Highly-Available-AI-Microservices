###############################################################################
# CMakeLists.txt - hams_shared static library
#
# Builds the shared utility library for the Highly Available AI Microservices
# project. Provides circuit-breaker, health-check, metrics, and retry-policy
# components that every microservice links against.
#
# Usage from a downstream service:
#   add_subdirectory(${CMAKE_SOURCE_DIR}/shared/cpp shared_cpp)
#   target_link_libraries(my_service PRIVATE hams_shared)
###############################################################################
cmake_minimum_required(VERSION 3.16)
project(hams_shared
    VERSION 1.0.0
    DESCRIPTION "Shared utilities for Highly Available AI Microservices"
    LANGUAGES CXX
)

# ── C++17 ────────────────────────────────────────────────────────────────────
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Sources ──────────────────────────────────────────────────────────────────
file(GLOB_RECURSE HAMS_SHARED_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")

# ── Static library ───────────────────────────────────────────────────────────
add_library(hams_shared STATIC ${HAMS_SHARED_SOURCES})

target_include_directories(hams_shared
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# ── Pthreads ─────────────────────────────────────────────────────────────────
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(hams_shared PUBLIC Threads::Threads)

# ── spdlog (header-only fallback if not found via find_package) ──────────────
find_package(spdlog QUIET)
if(spdlog_FOUND)
    target_link_libraries(hams_shared PUBLIC spdlog::spdlog)
else()
    message(STATUS "spdlog not found via find_package – assuming header-only availability")
    # Users must ensure spdlog headers are on the include path.
    target_compile_definitions(hams_shared PUBLIC SPDLOG_HEADER_ONLY)
endif()

# ── nlohmann/json (header-only fallback if not found via find_package) ───────
find_package(nlohmann_json QUIET)
if(nlohmann_json_FOUND)
    target_link_libraries(hams_shared PUBLIC nlohmann_json::nlohmann_json)
else()
    message(STATUS "nlohmann_json not found via find_package – assuming header-only availability")
endif()

# ── Compiler warnings ───────────────────────────────────────────────────────
target_compile_options(hams_shared PRIVATE
    $<$<CXX_COMPILER_ID:GNU>:-Wall -Wextra -Wpedantic>
    $<$<CXX_COMPILER_ID:Clang>:-Wall -Wextra -Wpedantic>
    $<$<CXX_COMPILER_ID:AppleClang>:-Wall -Wextra -Wpedantic>
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
)

# ── Export targets for downstream use ────────────────────────────────────────
install(TARGETS hams_shared
    EXPORT hams_shared_targets
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)

install(EXPORT hams_shared_targets
    FILE hams_shared_targets.cmake
    NAMESPACE hams::
    DESTINATION lib/cmake/hams_shared
)

# ── Package config (allows find_package(hams_shared)) ────────────────────────
include(CMakePackageConfigHelpers)

configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/hams_shared-config.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/hams_shared-config.cmake"
    INSTALL_DESTINATION lib/cmake/hams_shared
    NO_CHECK_REQUIRED_COMPONENTS_MACRO
)

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/hams_shared-config-version.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/hams_shared-config.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/hams_shared-config-version.cmake"
    DESTINATION lib/cmake/hams_shared
)

# ── Convenience alias ────────────────────────────────────────────────────────
add_library(hams::shared ALIAS hams_shared)
