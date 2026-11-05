find_package(GTest REQUIRED)
include(GoogleTest)

add_executable(test_preprocessor test_preprocessor.cpp)
target_link_libraries(test_preprocessor PRIVATE preprocessing_lib GTest::gtest GTest::gtest_main)
gtest_discover_tests(test_preprocessor)

add_executable(test_feature_extractor test_feature_extractor.cpp)
target_link_libraries(test_feature_extractor PRIVATE preprocessing_lib GTest::gtest GTest::gtest_main)
gtest_discover_tests(test_feature_extractor)
