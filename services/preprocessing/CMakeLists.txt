cmake_minimum_required(VERSION 3.16)
project(preprocessing_service VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

# Include shared library
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../../shared/cpp ${CMAKE_CURRENT_BINARY_DIR}/shared_cpp)

set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../proto)
set(COMMON_PROTO ${PROTO_DIR}/common.proto)
set(PREPROCESS_PROTO ${PROTO_DIR}/preprocessing.proto)

set(PROTO_SRCS
    ${CMAKE_CURRENT_BINARY_DIR}/common.pb.cc
    ${CMAKE_CURRENT_BINARY_DIR}/common.pb.h
    ${CMAKE_CURRENT_BINARY_DIR}/preprocessing.pb.cc
    ${CMAKE_CURRENT_BINARY_DIR}/preprocessing.pb.h
    ${CMAKE_CURRENT_BINARY_DIR}/preprocessing.grpc.pb.cc
    ${CMAKE_CURRENT_BINARY_DIR}/preprocessing.grpc.pb.h
)

find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin)

add_custom_command(
    OUTPUT ${PROTO_SRCS}
    COMMAND ${PROTOBUF_PROTOC_EXECUTABLE}
    ARGS --proto_path=${PROTO_DIR}
         --cpp_out=${CMAKE_CURRENT_BINARY_DIR}
         --grpc_out=${CMAKE_CURRENT_BINARY_DIR}
         --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
         ${COMMON_PROTO} ${PREPROCESS_PROTO}
    DEPENDS ${COMMON_PROTO} ${PREPROCESS_PROTO}
)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../shared/cpp/include
)

add_library(preprocessing_lib STATIC
    ${PROTO_SRCS}
    src/preprocessor.cpp
    src/feature_extractor.cpp
    src/pipeline.cpp
    src/server.cpp
)
target_link_libraries(preprocessing_lib PUBLIC
    hams_shared
    gRPC::grpc++
    protobuf::libprotobuf
    Threads::Threads
)

add_executable(preprocessing_service src/main.cpp)
target_link_libraries(preprocessing_service PRIVATE preprocessing_lib)

option(BUILD_TESTING "Build testing tree" OFF)
if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
