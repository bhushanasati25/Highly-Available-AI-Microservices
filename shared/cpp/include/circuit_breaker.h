#pragma once

/**
 * @file circuit_breaker.h
 * @brief Thread-safe circuit breaker pattern implementation.
 *
 * The circuit breaker prevents cascading failures in distributed systems by
 * wrapping calls to external services and monitoring their failure rate.
 *
 * State machine:
 *   CLOSED  ──(failures >= threshold)──▶  OPEN
 *   OPEN    ──(recovery timeout elapsed)──▶  HALF_OPEN
 *   HALF_OPEN ──(enough successes)──▶  CLOSED
 *   HALF_OPEN ──(any failure)──▶  OPEN
 *
 * Usage:
 *   CircuitBreaker cb("my-service", 5, std::chrono::seconds(30));
 *   auto result = cb.execute([&]() { return call_remote_service(); });
 */

#include <chrono>
#include <cstdint>
#include <exception>
#include <functional>
#include <mutex>
#include <string>
#include <stdexcept>

#include <spdlog/spdlog.h>

namespace hams {

/**
 * @brief Exception thrown when the circuit breaker is in the OPEN state and
 *        the recovery timeout has not yet elapsed.
 */
class CircuitBreakerOpenException : public std::runtime_error {
public:
    /**
     * @param breaker_name Name of the circuit breaker that rejected the call.
     * @param remaining    Approximate time remaining before the breaker
     *                     transitions to HALF_OPEN.
     */
    explicit CircuitBreakerOpenException(
        const std::string& breaker_name,
        std::chrono::milliseconds remaining)
        : std::runtime_error(
              "Circuit breaker '" + breaker_name + "' is OPEN – call rejected. "
              "Recovery in ~" + std::to_string(remaining.count()) + " ms"),
          breaker_name_(breaker_name),
          remaining_(remaining) {}

    /** @return The name of the circuit breaker. */
    const std::string& getBreakerName() const noexcept { return breaker_name_; }

    /** @return Approximate duration until the breaker enters HALF_OPEN. */
    std::chrono::milliseconds getRemaining() const noexcept { return remaining_; }

private:
    std::string breaker_name_;
    std::chrono::milliseconds remaining_;
};

/**
 * @brief Possible states of the circuit breaker.
 */
enum class CircuitBreakerState : uint8_t {
    CLOSED,    ///< Normal operation – calls are forwarded.
    OPEN,      ///< Failing – calls are rejected immediately.
    HALF_OPEN  ///< Testing recovery – limited calls are allowed.
};

/**
 * @brief Returns a human-readable string for a CircuitBreakerState value.
 */
inline const char* to_string(CircuitBreakerState state) noexcept {
    switch (state) {
        case CircuitBreakerState::CLOSED:    return "CLOSED";
        case CircuitBreakerState::OPEN:      return "OPEN";
        case CircuitBreakerState::HALF_OPEN: return "HALF_OPEN";
    }
    return "UNKNOWN";
}

/**
 * @brief Thread-safe circuit breaker that wraps function calls and monitors
 *        their success/failure rate.
 *
 * All public methods are safe to call from multiple threads concurrently.
 */
class CircuitBreaker {
public:
    /**
     * @param name               Human-readable name (used in logs & exceptions).
     * @param failure_threshold   Number of consecutive failures before tripping
     *                            to OPEN.
     * @param recovery_timeout    Duration to stay in OPEN before trying HALF_OPEN.
     * @param half_open_max_calls Maximum trial calls allowed in HALF_OPEN before
     *                            deciding to close or re-open.
     */
    CircuitBreaker(
        std::string name,
        uint32_t failure_threshold = 5,
        std::chrono::seconds recovery_timeout = std::chrono::seconds(30),
        uint32_t half_open_max_calls = 3);

    ~CircuitBreaker() = default;

    // Non-copyable, non-movable (contains mutex).
    CircuitBreaker(const CircuitBreaker&) = delete;
    CircuitBreaker& operator=(const CircuitBreaker&) = delete;
    CircuitBreaker(CircuitBreaker&&) = delete;
    CircuitBreaker& operator=(CircuitBreaker&&) = delete;

    /**
     * @brief Execute @p func through the circuit breaker.
     *
     * @tparam F Callable type whose return type is deduced automatically.
     * @param func The operation to protect.
     * @return The return value of @p func.
     *
     * @throws CircuitBreakerOpenException if the breaker is OPEN and recovery
     *         timeout has not elapsed.
     * @throws Any exception thrown by @p func (after internal bookkeeping).
     */
    template <typename F>
    auto execute(F&& func) -> decltype(func()) {
        preExecute();  // may throw CircuitBreakerOpenException

        try {
            auto result = func();
            onSuccess();
            return result;
        } catch (...) {
            onFailure();
            throw;  // re-throw the original exception
        }
    }

    /** @return The current state of the circuit breaker. */
    CircuitBreakerState getState() const;

    /** @return The current consecutive failure count. */
    uint32_t getFailureCount() const;

    /** @brief Reset the breaker to CLOSED with zero failures. */
    void reset();

    /** @return The human-readable name of this breaker. */
    const std::string& getName() const noexcept;

private:
    /**
     * @brief Pre-call gate logic.  Must be called before invoking the
     *        protected function.
     *
     * - CLOSED: always allows the call.
     * - OPEN:   checks recovery timeout; transitions to HALF_OPEN or throws.
     * - HALF_OPEN: allows up to half_open_max_calls_; throws if exceeded.
     */
    void preExecute();

    /** @brief Record a successful call. */
    void onSuccess();

    /** @brief Record a failed call. */
    void onFailure();

    /** @brief Trip the breaker to OPEN (must be called under lock). */
    void tripOpen();

    // ── Configuration ──
    const std::string name_;
    const uint32_t failure_threshold_;
    const std::chrono::seconds recovery_timeout_;
    const uint32_t half_open_max_calls_;

    // ── Mutable state (protected by mutex_) ──
    mutable std::mutex mutex_;
    CircuitBreakerState state_{CircuitBreakerState::CLOSED};
    uint32_t failure_count_{0};
    uint32_t half_open_successes_{0};
    uint32_t half_open_calls_{0};
    std::chrono::steady_clock::time_point last_failure_time_{};
};

}  // namespace hams
