find_package(GTest REQUIRED)
include(GoogleTest)

add_executable(test_shard test_shard.cpp)
target_link_libraries(test_shard PRIVATE storage_manager_lib GTest::gtest GTest::gtest_main)
gtest_discover_tests(test_shard)

add_executable(test_storage test_storage.cpp)
target_link_libraries(test_storage PRIVATE storage_manager_lib GTest::gtest GTest::gtest_main)
gtest_discover_tests(test_storage)
