#pragma once

#include <vector>
#include <string>
#include <unordered_map>
#include <cstdint>

namespace hams {

struct StatisticalFeatures {
    double mean{0.0};
    double stddev{0.0};
    double min{0.0};
    double max{0.0};
    double skewness{0.0};
    double kurtosis{0.0};
};

class FeatureExtractor {
public:
    static StatisticalFeatures computeStats(const std::vector<double>& series);

    static std::vector<std::vector<double>> oneHotEncode(
        const std::vector<std::string>& categories,
        const std::vector<std::string>& vocab);

    static std::vector<double> featureHash(
        const std::vector<std::pair<std::string, double>>& features,
        size_t dimension);

    static std::vector<std::vector<double>> projectDimensions(
        const std::vector<std::vector<double>>& matrix,
        size_t target_dims);
};

}  // namespace hams
