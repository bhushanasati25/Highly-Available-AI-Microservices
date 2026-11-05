#include <gtest/gtest.h>
#include "preprocessor.h"

TEST(PreprocessorTest, MinMaxNormalization) {
    std::vector<double> data = {10.0, 20.0, 30.0, 40.0, 50.0};
    auto normalized = hams::Preprocessor::normalizeMinMax(data, 0.0, 1.0);

    ASSERT_EQ(normalized.size(), 5);
    EXPECT_DOUBLE_EQ(normalized.front(), 0.0);
    EXPECT_DOUBLE_EQ(normalized.back(), 1.0);
    EXPECT_DOUBLE_EQ(normalized[2], 0.5);
}

TEST(PreprocessorTest, ZScoreNormalization) {
    std::vector<double> data = {1.0, 2.0, 3.0, 4.0, 5.0};
    auto z = hams::Preprocessor::normalizeZScore(data);

    ASSERT_EQ(z.size(), 5);
    EXPECT_NEAR(z[2], 0.0, 1e-6); // Mean is 3.0, so index 2 is 0.0
}

TEST(PreprocessorTest, MissingValueImputation) {
    std::vector<std::optional<double>> data = {1.0, std::nullopt, 3.0, std::nullopt, 5.0};
    // Mean of 1, 3, 5 is 3.0
    auto imputed = hams::Preprocessor::imputeMissing(data, hams::ImputationStrategy::MEAN);

    ASSERT_EQ(imputed.size(), 5);
    EXPECT_DOUBLE_EQ(imputed[1], 3.0);
    EXPECT_DOUBLE_EQ(imputed[3], 3.0);
}

TEST(PreprocessorTest, RemoveDuplicates) {
    std::vector<std::string> rows = {"rowA", "rowB", "rowA", "rowC", "rowB"};
    auto unique = hams::Preprocessor::removeDuplicates(rows);

    EXPECT_EQ(unique.size(), 3);
    EXPECT_EQ(unique[0], "rowA");
    EXPECT_EQ(unique[1], "rowB");
    EXPECT_EQ(unique[2], "rowC");
}
