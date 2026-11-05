#pragma once

#include <vector>
#include <string>
#include <unordered_map>
#include <optional>

namespace hams {

enum class ImputationStrategy {
    MEAN,
    MEDIAN,
    MODE,
    CONSTANT
};

enum class NormalizationStrategy {
    MIN_MAX,
    Z_SCORE
};

class Preprocessor {
public:
    static std::vector<double> normalizeMinMax(const std::vector<double>& data, double min_val = 0.0, double max_val = 1.0);
    static std::vector<double> normalizeZScore(const std::vector<double>& data);

    static std::vector<double> imputeMissing(
        const std::vector<std::optional<double>>& data,
        ImputationStrategy strategy = ImputationStrategy::MEAN,
        double constant_val = 0.0);

    static std::vector<double> clipOutliers(
        const std::vector<double>& data,
        double lower_quantile = 0.01,
        double upper_quantile = 0.99);

    static std::vector<std::string> removeDuplicates(const std::vector<std::string>& rows);
};

}  // namespace hams
