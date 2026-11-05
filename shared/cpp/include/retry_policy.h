#pragma once

/**
 * @file retry_policy.h
 * @brief Retry policy with exponential backoff and jitter.
 *
 * RetryPolicy wraps a callable and re-invokes it up to a configurable number
 * of times when it throws an exception, sleeping between attempts with an
 * exponentially increasing delay that is capped and jittered.
 *
 * Usage:
 *   hams::RetryPolicy policy(/*max_retries=*/5);
 *   auto result = policy.execute([&]() { return unreliable_rpc(); });
 *
 * You can subclass and override shouldRetry() to limit retries to specific
 * exception types.
 */

#include <chrono>
#include <cstdint>
#include <exception>
#include <functional>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <type_traits>

#include <spdlog/spdlog.h>

namespace hams {

/**
 * @brief Retry policy with exponential backoff, configurable cap, and jitter.
 *
 * Thread-safe: multiple threads may share one RetryPolicy instance.
 * Each call to execute() is independent.
 */
class RetryPolicy {
public:
    /**
     * @param max_retries   Maximum number of retry attempts (0 = no retries,
     *                      the function is called exactly once).
     * @param base_delay    Initial delay before the first retry.
     * @param max_delay     Upper bound on the computed delay.
     * @param jitter_factor Fraction of delay to randomize (0.0 = no jitter).
     */
    RetryPolicy(
        uint32_t max_retries = 3,
        std::chrono::milliseconds base_delay = std::chrono::milliseconds(100),
        std::chrono::milliseconds max_delay = std::chrono::milliseconds(30000),
        double jitter_factor = 0.1);

    virtual ~RetryPolicy() = default;

    // Copyable.
    RetryPolicy(const RetryPolicy& other);
    RetryPolicy& operator=(const RetryPolicy& other);

    // Movable.
    RetryPolicy(RetryPolicy&& other) noexcept;
    RetryPolicy& operator=(RetryPolicy&& other) noexcept;

    /**
     * @brief Execute @p func, retrying on exception with exponential backoff.
     *
     * @tparam F Callable type (return type is deduced).
     * @param func The operation to execute.
     * @return The return value of @p func on the first successful call.
     *
     * @throws The last exception if all retry attempts are exhausted and
     *         shouldRetry() returns false, or after max_retries failures.
     */
    template <typename F>
    auto execute(F&& func) -> decltype(func()) {
        std::exception_ptr last_exception;
        resetAttempts();

        for (uint32_t attempt = 0; attempt <= max_retries_; ++attempt) {
            try {
                incrementAttempts();
                auto result = func();
                spdlog::info("RetryPolicy: call succeeded on attempt {}/{}",
                             attempt + 1, max_retries_ + 1);
                return result;
            } catch (...) {
                last_exception = std::current_exception();

                // Check if we should retry this particular exception.
                try {
                    std::rethrow_exception(last_exception);
                } catch (const std::exception& e) {
                    if (!shouldRetry(e)) {
                        spdlog::warn("RetryPolicy: shouldRetry() returned false "
                                     "for exception '{}' – not retrying", e.what());
                        std::rethrow_exception(last_exception);
                    }
                } catch (...) {
                    // Non-std::exception – always retry.
                }

                if (attempt < max_retries_) {
                    auto delay = computeDelay(attempt);
                    spdlog::warn("RetryPolicy: attempt {}/{} failed, retrying "
                                 "in {} ms",
                                 attempt + 1, max_retries_ + 1,
                                 delay.count());
                    std::this_thread::sleep_for(delay);
                } else {
                    spdlog::error("RetryPolicy: all {} attempts exhausted",
                                  max_retries_ + 1);
                }
            }
        }

        // All retries exhausted – rethrow the last captured exception.
        std::rethrow_exception(last_exception);
    }

    /**
     * @return Number of attempts made during the most recent execute() call.
     */
    uint32_t getAttemptCount() const;

    /**
     * @brief Override point: return false to stop retrying for a particular
     *        exception.
     *
     * The default implementation always returns true (retry on any exception).
     *
     * @param ex The caught exception.
     */
    virtual bool shouldRetry(const std::exception& ex) const;

protected:
    /**
     * @brief Compute the sleep duration for a given attempt index.
     *
     * delay = min(base_delay * 2^attempt, max_delay) * (1 + jitter)
     *
     * @param attempt Zero-based attempt index.
     */
    std::chrono::milliseconds computeDelay(uint32_t attempt) const;

private:
    /** @brief Reset the per-execute attempt counter. */
    void resetAttempts();

    /** @brief Increment the per-execute attempt counter. */
    void incrementAttempts();

    uint32_t max_retries_;
    std::chrono::milliseconds base_delay_;
    std::chrono::milliseconds max_delay_;
    double jitter_factor_;

    mutable std::mutex mutex_;
    uint32_t attempt_count_{0};

    // Thread-local RNG seeded from random_device.
    mutable std::mt19937 rng_{std::random_device{}()};
};

/**
 * @brief Convenience alias – RetryPolicy already implements exponential
 *        backoff, so ExponentialBackoffPolicy is simply a typedef.
 */
using ExponentialBackoffPolicy = RetryPolicy;

}  // namespace hams
