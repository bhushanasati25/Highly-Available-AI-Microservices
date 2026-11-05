#pragma once

/**
 * @file metrics.h
 * @brief Thread-safe metrics collector with Prometheus exposition format.
 *
 * MetricsCollector is a singleton that microservices use to register and
 * update counters, gauges, and histograms.  It can serialize all metrics
 * in the Prometheus text exposition format and serve them over HTTP.
 *
 * Usage:
 *   auto& m = hams::MetricsCollector::getInstance();
 *   m.registerMetric("http_requests_total", MetricType::COUNTER, "Total HTTP requests");
 *   m.incrementCounter("http_requests_total");
 *   m.startHttpServer(9090);  // GET /metrics
 */

#include <atomic>
#include <cstdint>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

namespace hams {

/**
 * @brief Kind of metric tracked by the collector.
 */
enum class MetricType : uint8_t {
    COUNTER,   ///< Monotonically increasing value.
    GAUGE,     ///< Value that can go up or down.
    HISTOGRAM  ///< Observations bucketed by configurable boundaries.
};

/**
 * @brief Returns the Prometheus type name for a MetricType.
 */
inline const char* to_prometheus_type(MetricType type) noexcept {
    switch (type) {
        case MetricType::COUNTER:   return "counter";
        case MetricType::GAUGE:     return "gauge";
        case MetricType::HISTOGRAM: return "histogram";
    }
    return "untyped";
}

/**
 * @brief Snapshot of a single metric's current value.
 */
struct MetricValue {
    MetricType type{MetricType::COUNTER};
    double value{0.0};                           ///< Current value (counter / gauge).
    std::vector<double> histogram_values;         ///< Raw observations (histogram).
    std::vector<double> bucket_boundaries;        ///< Upper bounds for histogram buckets.
};

/**
 * @brief Thread-safe, singleton metrics collector with Prometheus exposition
 *        format serialization and a built-in HTTP endpoint.
 *
 * All public methods are safe to call from any thread.
 */
class MetricsCollector {
public:
    /**
     * @brief Access the singleton instance.
     * @return Reference to the global MetricsCollector.
     */
    static MetricsCollector& getInstance();

    // Non-copyable, non-movable.
    MetricsCollector(const MetricsCollector&) = delete;
    MetricsCollector& operator=(const MetricsCollector&) = delete;
    MetricsCollector(MetricsCollector&&) = delete;
    MetricsCollector& operator=(MetricsCollector&&) = delete;

    /**
     * @brief Register a new metric.
     *
     * @param name              Prometheus-style metric name (e.g. "http_requests_total").
     * @param type              COUNTER, GAUGE, or HISTOGRAM.
     * @param help_string       Human-readable description.
     * @param bucket_boundaries Optional upper-bound list for histogram buckets.
     *                          Ignored for non-histogram types.  If empty for a
     *                          histogram, default boundaries are used.
     *
     * Registering the same name twice is a no-op (logged as a warning).
     */
    void registerMetric(
        const std::string& name,
        MetricType type,
        const std::string& help_string,
        const std::vector<double>& bucket_boundaries = {});

    /**
     * @brief Increment a COUNTER metric by @p amount.
     *
     * @param name   Previously registered counter name.
     * @param amount Positive increment (default 1.0).
     */
    void incrementCounter(const std::string& name, double amount = 1.0);

    /**
     * @brief Set the value of a GAUGE metric.
     *
     * @param name  Previously registered gauge name.
     * @param value New gauge value.
     */
    void setGauge(const std::string& name, double value);

    /**
     * @brief Record an observation for a HISTOGRAM metric.
     *
     * @param name  Previously registered histogram name.
     * @param value Observed value.
     */
    void observeHistogram(const std::string& name, double value);

    /**
     * @brief Retrieve the current value snapshot for a metric.
     *
     * @param name Metric name.
     * @return MetricValue if found, std::nullopt otherwise.
     */
    std::optional<MetricValue> getMetricValue(const std::string& name) const;

    /**
     * @brief Serialize all registered metrics in Prometheus text exposition
     *        format (text/plain; version=0.0.4).
     */
    std::string serialize() const;

    /**
     * @brief Start an HTTP server that responds to GET /metrics with the
     *        serialized Prometheus output.
     *
     * @param port TCP port to bind.
     */
    void startHttpServer(uint16_t port);

    /**
     * @brief Stop the HTTP server if running.
     */
    void stopHttpServer();

    /** @brief Destructor – stops server if running. */
    ~MetricsCollector();

private:
    /** @brief Private constructor for singleton. */
    MetricsCollector() = default;

    /**
     * @brief Internal metric record including metadata.
     */
    struct MetricRecord {
        MetricType type{MetricType::COUNTER};
        std::string help;
        double value{0.0};
        std::vector<double> histogram_values;
        std::vector<double> bucket_boundaries;
    };

    /** @brief HTTP server loop. */
    void runHttpServer(uint16_t port);

    mutable std::mutex mutex_;
    std::map<std::string, MetricRecord> metrics_;

    // ── HTTP server state ──
    std::atomic<bool> http_running_{false};
    std::thread http_thread_;
    int server_fd_{-1};
};

}  // namespace hams
