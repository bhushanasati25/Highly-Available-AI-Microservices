cmake_minimum_required(VERSION 3.16)
project(storage_manager_service VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)

# Include shared library
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../shared/cpp ${CMAKE_CURRENT_BINARY_DIR}/shared_cpp)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/cpp/include
)

add_library(storage_manager_lib STATIC
    src/shard_manager.cpp
    src/replication.cpp
    src/storage_service.cpp
)
target_link_libraries(storage_manager_lib PUBLIC
    hams_shared
    Threads::Threads
)

add_executable(storage_manager_service src/main.cpp)
target_link_libraries(storage_manager_service PRIVATE storage_manager_lib)

option(BUILD_TESTING "Build testing tree" OFF)
if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
