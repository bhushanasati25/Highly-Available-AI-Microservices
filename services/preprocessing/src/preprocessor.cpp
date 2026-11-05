#include "preprocessor.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <unordered_set>
#include <map>

namespace hams {

std::vector<double> Preprocessor::normalizeMinMax(const std::vector<double>& data, double target_min, double target_max) {
    if (data.empty()) return {};

    auto [min_it, max_it] = std::minmax_element(data.begin(), data.end());
    double cur_min = *min_it;
    double cur_max = *max_it;

    if (std::abs(cur_max - cur_min) < 1e-9) {
        return std::vector<double>(data.size(), target_min);
    }

    std::vector<double> result;
    result.reserve(data.size());

    double range = cur_max - cur_min;
    double target_range = target_max - target_min;

    for (double val : data) {
        double scaled = ((val - cur_min) / range) * target_range + target_min;
        result.push_back(scaled);
    }

    return result;
}

std::vector<double> Preprocessor::normalizeZScore(const std::vector<double>& data) {
    if (data.empty()) return {};

    double sum = std::accumulate(data.begin(), data.end(), 0.0);
    double mean = sum / data.size();

    double accum = 0.0;
    for (double d : data) {
        accum += (d - mean) * (d - mean);
    }
    double stddev = std::sqrt(accum / data.size());

    if (stddev < 1e-9) {
        return std::vector<double>(data.size(), 0.0);
    }

    std::vector<double> result;
    result.reserve(data.size());
    for (double d : data) {
        result.push_back((d - mean) / stddev);
    }

    return result;
}

std::vector<double> Preprocessor::imputeMissing(
    const std::vector<std::optional<double>>& data,
    ImputationStrategy strategy,
    double constant_val) {
    if (data.empty()) return {};

    std::vector<double> valid_vals;
    for (const auto& opt : data) {
        if (opt.has_value()) {
            valid_vals.push_back(*opt);
        }
    }

    double fill_val = constant_val;

    if (!valid_vals.empty()) {
        if (strategy == ImputationStrategy::MEAN) {
            fill_val = std::accumulate(valid_vals.begin(), valid_vals.end(), 0.0) / valid_vals.size();
        } else if (strategy == ImputationStrategy::MEDIAN) {
            std::sort(valid_vals.begin(), valid_vals.end());
            size_t n = valid_vals.size();
            fill_val = (n % 2 == 0) ? (valid_vals[n/2 - 1] + valid_vals[n/2]) / 2.0 : valid_vals[n/2];
        } else if (strategy == ImputationStrategy::MODE) {
            std::map<double, size_t> counts;
            for (double v : valid_vals) counts[v]++;
            size_t best_count = 0;
            for (const auto& [val, count] : counts) {
                if (count > best_count) {
                    best_count = count;
                    fill_val = val;
                }
            }
        }
    }

    std::vector<double> result;
    result.reserve(data.size());
    for (const auto& opt : data) {
        result.push_back(opt.has_value() ? *opt : fill_val);
    }
    return result;
}

std::vector<double> Preprocessor::clipOutliers(
    const std::vector<double>& data,
    double lower_quantile,
    double upper_quantile) {
    if (data.empty()) return {};

    std::vector<double> sorted = data;
    std::sort(sorted.begin(), sorted.end());

    size_t low_idx = static_cast<size_t>(lower_quantile * (sorted.size() - 1));
    size_t high_idx = static_cast<size_t>(upper_quantile * (sorted.size() - 1));

    double low_bound = sorted[low_idx];
    double high_bound = sorted[high_idx];

    std::vector<double> result;
    result.reserve(data.size());
    for (double d : data) {
        result.push_back(std::clamp(d, low_bound, high_bound));
    }
    return result;
}

std::vector<std::string> Preprocessor::removeDuplicates(const std::vector<std::string>& rows) {
    std::unordered_set<std::string> seen;
    std::vector<std::string> unique_rows;
    for (const auto& r : rows) {
        if (seen.insert(r).second) {
            unique_rows.push_back(r);
        }
    }
    return unique_rows;
}

}  // namespace hams
