#include "retry_policy.h"

#include <algorithm>
#include <cmath>

namespace hams {

RetryPolicy::RetryPolicy(
    uint32_t max_retries,
    std::chrono::milliseconds base_delay,
    std::chrono::milliseconds max_delay,
    double jitter_factor)
    : max_retries_(max_retries),
      base_delay_(base_delay),
      max_delay_(max_delay),
      jitter_factor_(std::max(0.0, std::min(1.0, jitter_factor))),
      rng_(std::random_device{}()) {}

RetryPolicy::RetryPolicy(const RetryPolicy& other) {
    std::lock_guard<std::mutex> lock(other.mutex_);
    max_retries_ = other.max_retries_;
    base_delay_ = other.base_delay_;
    max_delay_ = other.max_delay_;
    jitter_factor_ = other.jitter_factor_;
    attempt_count_ = other.attempt_count_;
}

RetryPolicy& RetryPolicy::operator=(const RetryPolicy& other) {
    if (this != &other) {
        std::scoped_lock lock(mutex_, other.mutex_);
        max_retries_ = other.max_retries_;
        base_delay_ = other.base_delay_;
        max_delay_ = other.max_delay_;
        jitter_factor_ = other.jitter_factor_;
        attempt_count_ = other.attempt_count_;
    }
    return *this;
}

RetryPolicy::RetryPolicy(RetryPolicy&& other) noexcept {
    std::lock_guard<std::mutex> lock(other.mutex_);
    max_retries_ = other.max_retries_;
    base_delay_ = other.base_delay_;
    max_delay_ = other.max_delay_;
    jitter_factor_ = other.jitter_factor_;
    attempt_count_ = other.attempt_count_;
}

RetryPolicy& RetryPolicy::operator=(RetryPolicy&& other) noexcept {
    if (this != &other) {
        std::scoped_lock lock(mutex_, other.mutex_);
        max_retries_ = other.max_retries_;
        base_delay_ = other.base_delay_;
        max_delay_ = other.max_delay_;
        jitter_factor_ = other.jitter_factor_;
        attempt_count_ = other.attempt_count_;
    }
    return *this;
}

uint32_t RetryPolicy::getAttemptCount() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return attempt_count_;
}

bool RetryPolicy::shouldRetry(const std::exception& /*ex*/) const {
    return true;
}

std::chrono::milliseconds RetryPolicy::computeDelay(uint32_t attempt) const {
    double exp_backoff = static_cast<double>(base_delay_.count()) * std::pow(2.0, static_cast<double>(attempt));
    double capped_delay = std::min(exp_backoff, static_cast<double>(max_delay_.count()));

    if (jitter_factor_ > 0.0) {
        std::lock_guard<std::mutex> lock(mutex_);
        std::uniform_real_distribution<double> dist(-jitter_factor_, jitter_factor_);
        double jitter = dist(rng_);
        capped_delay *= (1.0 + jitter);
    }

    return std::chrono::milliseconds(static_cast<int64_t>(std::max(0.0, capped_delay)));
}

void RetryPolicy::resetAttempts() {
    std::lock_guard<std::mutex> lock(mutex_);
    attempt_count_ = 0;
}

void RetryPolicy::incrementAttempts() {
    std::lock_guard<std::mutex> lock(mutex_);
    attempt_count_++;
}

}  // namespace hams
