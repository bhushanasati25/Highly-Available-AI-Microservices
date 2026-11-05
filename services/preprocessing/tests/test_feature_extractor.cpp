#include <gtest/gtest.h>
#include "feature_extractor.h"

TEST(FeatureExtractorTest, StatisticalFeatures) {
    std::vector<double> data = {2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0};
    auto stats = hams::FeatureExtractor::computeStats(data);

    EXPECT_DOUBLE_EQ(stats.mean, 5.0);
    EXPECT_DOUBLE_EQ(stats.min, 2.0);
    EXPECT_DOUBLE_EQ(stats.max, 9.0);
    EXPECT_GT(stats.stddev, 2.0);
}

TEST(FeatureExtractorTest, OneHotEncoding) {
    std::vector<std::string> cats = {"red", "blue", "green", "unknown"};
    std::vector<std::string> vocab = {"red", "green", "blue"};

    auto encoded = hams::FeatureExtractor::oneHotEncode(cats, vocab);

    ASSERT_EQ(encoded.size(), 4);
    // "red" -> [1, 0, 0]
    EXPECT_DOUBLE_EQ(encoded[0][0], 1.0);
    EXPECT_DOUBLE_EQ(encoded[0][1], 0.0);
    EXPECT_DOUBLE_EQ(encoded[0][2], 0.0);

    // "unknown" -> [0, 0, 0]
    EXPECT_DOUBLE_EQ(encoded[3][0], 0.0);
    EXPECT_DOUBLE_EQ(encoded[3][1], 0.0);
    EXPECT_DOUBLE_EQ(encoded[3][2], 0.0);
}

TEST(FeatureExtractorTest, FeatureHashing) {
    std::vector<std::pair<std::string, double>> feats = {
        {"feature_a", 1.5},
        {"feature_b", 2.5}
    };

    auto hashed = hams::FeatureExtractor::featureHash(feats, 10);
    EXPECT_EQ(hashed.size(), 10);
}
