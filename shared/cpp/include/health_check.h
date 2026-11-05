#pragma once

/**
 * @file health_check.h
 * @brief Periodic health-check runner with a built-in HTTP server.
 *
 * HealthChecker allows microservices to register named check functions,
 * runs them on a configurable interval, and exposes the aggregated status
 * over HTTP (GET /health) for use by load balancers and orchestrators.
 *
 * Usage:
 *   hams::HealthChecker hc;
 *   hc.registerCheck("database", [&]() { return db.ping(); });
 *   hc.start(10);            // run checks every 10 s
 *   hc.startHttpServer(8080);
 *   // ... service runs ...
 *   hc.stop();               // tears down background threads
 */

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <thread>

namespace hams {

/**
 * @brief Result of a single named health check.
 */
struct HealthCheckResult {
    bool passed{false};
    std::chrono::system_clock::time_point timestamp{};
};

/**
 * @brief Runs registered health-check functions periodically and exposes
 *        their aggregated status over a minimal HTTP endpoint.
 *
 * Thread safety: all public methods are safe to call from any thread.
 */
class HealthChecker {
public:
    /** @brief Constructs an idle HealthChecker (no checks, not running). */
    HealthChecker();

    /** @brief Stops background threads if still running. */
    ~HealthChecker();

    // Non-copyable, non-movable.
    HealthChecker(const HealthChecker&) = delete;
    HealthChecker& operator=(const HealthChecker&) = delete;
    HealthChecker(HealthChecker&&) = delete;
    HealthChecker& operator=(HealthChecker&&) = delete;

    /**
     * @brief Register a named health check.
     *
     * @param name  Unique descriptive name (e.g. "database", "redis").
     * @param check Callable returning true if healthy.
     *
     * May be called before or after start().  Adding a check while the
     * checker is running is safe – it will be evaluated on the next cycle.
     */
    void registerCheck(const std::string& name, std::function<bool()> check);

    /**
     * @brief Start the background thread that periodically runs all checks.
     *
     * @param interval_seconds Seconds between successive check cycles.
     *
     * Calling start() when already started is a no-op.
     */
    void start(uint32_t interval_seconds);

    /**
     * @brief Stop the background check thread and the HTTP server (if running).
     *
     * Blocks until both threads have joined.  Safe to call multiple times.
     */
    void stop();

    /**
     * @return true if every registered check last passed, false otherwise.
     *         Returns true (vacuously healthy) when no checks are registered.
     */
    bool isHealthy() const;

    /**
     * @return JSON string describing overall status and per-check results.
     *
     * Format:
     * @code
     * {
     *   "status": "healthy" | "unhealthy",
     *   "checks": {
     *     "name": { "status": "pass"|"fail", "timestamp": "ISO-8601" }
     *   },
     *   "uptime_seconds": 42
     * }
     * @endcode
     */
    std::string getStatus() const;

    /**
     * @brief Start a minimal HTTP server in a background thread.
     *
     * Responds to:
     *  - GET /health  → 200 OK  + JSON status body
     *  - Anything else → 404 Not Found
     *
     * @param port TCP port to listen on.
     */
    void startHttpServer(uint16_t port);

private:
    /** @brief Background loop that runs registered checks. */
    void runChecks(uint32_t interval_seconds);

    /** @brief Background loop that serves HTTP requests. */
    void runHttpServer(uint16_t port);

    /** @brief Execute all checks once (called under lock). */
    void executeChecks();

    /** @brief Format an ISO-8601 UTC timestamp. */
    static std::string formatTimestamp(std::chrono::system_clock::time_point tp);

    // ── Registered checks ──
    mutable std::mutex mutex_;
    std::map<std::string, std::function<bool()>> checks_;
    std::map<std::string, HealthCheckResult> results_;

    // ── Background thread state ──
    std::atomic<bool> running_{false};
    std::condition_variable cv_;
    std::thread check_thread_;

    // ── HTTP server state ──
    std::atomic<bool> http_running_{false};
    std::thread http_thread_;
    int server_fd_{-1};  ///< Listening socket file descriptor.

    // ── Uptime tracking ──
    std::chrono::steady_clock::time_point start_time_{std::chrono::steady_clock::now()};
};

}  // namespace hams
