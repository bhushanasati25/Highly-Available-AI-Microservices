find_package(GTest REQUIRED)
include(GoogleTest)

add_executable(test_validator test_validator.cpp)
target_link_libraries(test_validator PRIVATE data_ingestion_lib GTest::gtest GTest::gtest_main)
gtest_discover_tests(test_validator)

add_executable(test_ingestion test_ingestion.cpp)
target_link_libraries(test_ingestion PRIVATE data_ingestion_lib GTest::gtest GTest::gtest_main)
gtest_discover_tests(test_ingestion)
