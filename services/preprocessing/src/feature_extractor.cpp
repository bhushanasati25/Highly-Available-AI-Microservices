#include "feature_extractor.h"

#include <cmath>
#include <numeric>
#include <functional>
#include <algorithm>

namespace hams {

StatisticalFeatures FeatureExtractor::computeStats(const std::vector<double>& series) {
    StatisticalFeatures stats;
    if (series.empty()) return stats;

    double n = static_cast<double>(series.size());
    double sum = std::accumulate(series.begin(), series.end(), 0.0);
    stats.mean = sum / n;

    auto [min_it, max_it] = std::minmax_element(series.begin(), series.end());
    stats.min = *min_it;
    stats.max = *max_it;

    double m2 = 0.0, m3 = 0.0, m4 = 0.0;
    for (double x : series) {
        double diff = x - stats.mean;
        double diff2 = diff * diff;
        m2 += diff2;
        m3 += diff2 * diff;
        m4 += diff2 * diff2;
    }

    double variance = (n > 1) ? m2 / (n - 1) : 0.0;
    stats.stddev = std::sqrt(variance);

    if (stats.stddev > 1e-9) {
        stats.skewness = (m3 / n) / std::pow(stats.stddev, 3);
        stats.kurtosis = ((m4 / n) / std::pow(stats.stddev, 4)) - 3.0; // Excess kurtosis
    }

    return stats;
}

std::vector<std::vector<double>> FeatureExtractor::oneHotEncode(
    const std::vector<std::string>& categories,
    const std::vector<std::string>& vocab) {

    std::unordered_map<std::string, size_t> vocab_map;
    for (size_t i = 0; i < vocab.size(); ++i) {
        vocab_map[vocab[i]] = i;
    }

    std::vector<std::vector<double>> result;
    result.reserve(categories.size());

    for (const auto& cat : categories) {
        std::vector<double> row(vocab.size(), 0.0);
        auto it = vocab_map.find(cat);
        if (it != vocab_map.end()) {
            row[it->second] = 1.0;
        }
        result.push_back(std::move(row));
    }

    return result;
}

std::vector<double> FeatureExtractor::featureHash(
    const std::vector<std::pair<std::string, double>>& features,
    size_t dimension) {

    std::vector<double> hash_vec(dimension, 0.0);
    if (dimension == 0) return hash_vec;

    std::hash<std::string> hasher;
    for (const auto& [name, val] : features) {
        size_t h = hasher(name);
        size_t idx = h % dimension;
        int sign = ((h >> 16) & 1) ? 1 : -1;
        hash_vec[idx] += sign * val;
    }

    return hash_vec;
}

std::vector<std::vector<double>> FeatureExtractor::projectDimensions(
    const std::vector<std::vector<double>>& matrix,
    size_t target_dims) {

    if (matrix.empty() || target_dims == 0) return {};

    size_t in_dims = matrix[0].size();
    if (target_dims >= in_dims) {
        return matrix;
    }

    std::vector<std::vector<double>> projected;
    projected.reserve(matrix.size());

    for (const auto& row : matrix) {
        std::vector<double> proj_row(target_dims, 0.0);
        for (size_t j = 0; j < in_dims; ++j) {
            size_t out_j = j % target_dims;
            proj_row[out_j] += row[j] / std::sqrt(static_cast<double>(in_dims) / target_dims);
        }
        projected.push_back(std::move(proj_row));
    }

    return projected;
}

}  // namespace hams
