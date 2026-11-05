#include "circuit_breaker.h"

namespace hams {

CircuitBreaker::CircuitBreaker(
    std::string name,
    uint32_t failure_threshold,
    std::chrono::seconds recovery_timeout,
    uint32_t half_open_max_calls)
    : name_(std::move(name)),
      failure_threshold_(failure_threshold),
      recovery_timeout_(recovery_timeout),
      half_open_max_calls_(half_open_max_calls) {
    spdlog::info("CircuitBreaker '{}' initialized: threshold={}, timeout={}s, half_open_calls={}",
                 name_, failure_threshold_, recovery_timeout_.count(), half_open_max_calls_);
}

void CircuitBreaker::preExecute() {
    std::lock_guard<std::mutex> lock(mutex_);
    auto now = std::chrono::steady_clock::now();

    switch (state_) {
        case CircuitBreakerState::CLOSED:
            return;

        case CircuitBreakerState::OPEN: {
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - last_failure_time_);
            if (elapsed >= recovery_timeout_) {
                spdlog::info("CircuitBreaker '{}' transitioning from OPEN to HALF_OPEN (timeout elapsed)", name_);
                state_ = CircuitBreakerState::HALF_OPEN;
                half_open_calls_ = 1;
                half_open_successes_ = 0;
                return;
            }
            auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(recovery_timeout_ - elapsed);
            throw CircuitBreakerOpenException(name_, remaining);
        }

        case CircuitBreakerState::HALF_OPEN:
            if (half_open_calls_ < half_open_max_calls_) {
                half_open_calls_++;
                return;
            }
            throw CircuitBreakerOpenException(name_, std::chrono::milliseconds(500));
    }
}

void CircuitBreaker::onSuccess() {
    std::lock_guard<std::mutex> lock(mutex_);
    switch (state_) {
        case CircuitBreakerState::CLOSED:
            failure_count_ = 0;
            break;

        case CircuitBreakerState::HALF_OPEN:
            half_open_successes_++;
            if (half_open_successes_ >= half_open_max_calls_) {
                spdlog::info("CircuitBreaker '{}' recovered: HALF_OPEN -> CLOSED", name_);
                state_ = CircuitBreakerState::CLOSED;
                failure_count_ = 0;
                half_open_calls_ = 0;
                half_open_successes_ = 0;
            }
            break;

        case CircuitBreakerState::OPEN:
            break;
    }
}

void CircuitBreaker::onFailure() {
    std::lock_guard<std::mutex> lock(mutex_);
    last_failure_time_ = std::chrono::steady_clock::now();

    switch (state_) {
        case CircuitBreakerState::CLOSED:
            failure_count_++;
            spdlog::warn("CircuitBreaker '{}' failure {}/{}", name_, failure_count_, failure_threshold_);
            if (failure_count_ >= failure_threshold_) {
                tripOpen();
            }
            break;

        case CircuitBreakerState::HALF_OPEN:
            spdlog::warn("CircuitBreaker '{}' call failed while HALF_OPEN -> tripping back to OPEN", name_);
            tripOpen();
            break;

        case CircuitBreakerState::OPEN:
            break;
    }
}

void CircuitBreaker::tripOpen() {
    state_ = CircuitBreakerState::OPEN;
    last_failure_time_ = std::chrono::steady_clock::now();
    spdlog::error("CircuitBreaker '{}' TRIPPED to OPEN state!", name_);
}

CircuitBreakerState CircuitBreaker::getState() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return state_;
}

uint32_t CircuitBreaker::getFailureCount() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return failure_count_;
}

void CircuitBreaker::reset() {
    std::lock_guard<std::mutex> lock(mutex_);
    state_ = CircuitBreakerState::CLOSED;
    failure_count_ = 0;
    half_open_calls_ = 0;
    half_open_successes_ = 0;
    spdlog::info("CircuitBreaker '{}' manually reset to CLOSED", name_);
}

const std::string& CircuitBreaker::getName() const noexcept {
    return name_;
}

}  // namespace hams
