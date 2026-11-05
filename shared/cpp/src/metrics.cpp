#include "metrics.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cmath>
#include <sstream>
#include <spdlog/spdlog.h>

namespace hams {

MetricsCollector& MetricsCollector::getInstance() {
    static MetricsCollector instance;
    return instance;
}

MetricsCollector::~MetricsCollector() {
    stopHttpServer();
}

void MetricsCollector::registerMetric(
    const std::string& name,
    MetricType type,
    const std::string& help_string,
    const std::vector<double>& bucket_boundaries) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (metrics_.find(name) != metrics_.end()) {
        spdlog::debug("Metric '{}' is already registered", name);
        return;
    }

    MetricRecord record;
    record.type = type;
    record.help = help_string;
    record.value = 0.0;

    if (type == MetricType::HISTOGRAM) {
        if (bucket_boundaries.empty()) {
            record.bucket_boundaries = {0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0};
        } else {
            record.bucket_boundaries = bucket_boundaries;
            std::sort(record.bucket_boundaries.begin(), record.bucket_boundaries.end());
        }
    }

    metrics_[name] = record;
}

void MetricsCollector::incrementCounter(const std::string& name, double amount) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = metrics_.find(name);
    if (it == metrics_.end()) {
        MetricRecord rec;
        rec.type = MetricType::COUNTER;
        rec.help = name;
        rec.value = amount;
        metrics_[name] = rec;
        return;
    }
    if (it->second.type == MetricType::COUNTER) {
        it->second.value += amount;
    }
}

void MetricsCollector::setGauge(const std::string& name, double value) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = metrics_.find(name);
    if (it == metrics_.end()) {
        MetricRecord rec;
        rec.type = MetricType::GAUGE;
        rec.help = name;
        rec.value = value;
        metrics_[name] = rec;
        return;
    }
    it->second.value = value;
}

void MetricsCollector::observeHistogram(const std::string& name, double value) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = metrics_.find(name);
    if (it == metrics_.end()) {
        MetricRecord rec;
        rec.type = MetricType::HISTOGRAM;
        rec.help = name;
        rec.bucket_boundaries = {0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0};
        rec.histogram_values.push_back(value);
        metrics_[name] = rec;
        return;
    }
    if (it->second.type == MetricType::HISTOGRAM) {
        it->second.histogram_values.push_back(value);
    }
}

std::optional<MetricValue> MetricsCollector::getMetricValue(const std::string& name) const {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = metrics_.find(name);
    if (it == metrics_.end()) {
        return std::nullopt;
    }
    MetricValue val;
    val.type = it->second.type;
    val.value = it->second.value;
    val.histogram_values = it->second.histogram_values;
    val.bucket_boundaries = it->second.bucket_boundaries;
    return val;
}

std::string MetricsCollector::serialize() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::ostringstream ss;

    for (const auto& [name, rec] : metrics_) {
        ss << "# HELP " << name << " " << rec.help << "\n";
        ss << "# TYPE " << name << " " << to_prometheus_type(rec.type) << "\n";

        if (rec.type == MetricType::COUNTER || rec.type == MetricType::GAUGE) {
            ss << name << " " << rec.value << "\n";
        } else if (rec.type == MetricType::HISTOGRAM) {
            double sum = 0.0;
            std::map<double, uint64_t> counts;
            for (double b : rec.bucket_boundaries) {
                counts[b] = 0;
            }

            for (double val : rec.histogram_values) {
                sum += val;
                for (double b : rec.bucket_boundaries) {
                    if (val <= b) {
                        counts[b]++;
                    }
                }
            }

            for (double b : rec.bucket_boundaries) {
                ss << name << "_bucket{le=\"" << b << "\"} " << counts[b] << "\n";
            }
            ss << name << "_bucket{le=\"+Inf\"} " << rec.histogram_values.size() << "\n";
            ss << name << "_sum " << sum << "\n";
            ss << name << "_count " << rec.histogram_values.size() << "\n";
        }
    }

    return ss.str();
}

void MetricsCollector::startHttpServer(uint16_t port) {
    if (http_running_.exchange(true)) {
        return;
    }
    http_thread_ = std::thread(&MetricsCollector::runHttpServer, this, port);
    spdlog::info("MetricsCollector HTTP server listening on port {}", port);
}

void MetricsCollector::stopHttpServer() {
    if (http_running_.exchange(false)) {
        if (server_fd_ >= 0) {
            ::shutdown(server_fd_, SHUT_RDWR);
            ::close(server_fd_);
            server_fd_ = -1;
        }
        if (http_thread_.joinable()) {
            http_thread_.join();
        }
    }
}

void MetricsCollector::runHttpServer(uint16_t port) {
    server_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        http_running_ = false;
        return;
    }

    int opt = 1;
    ::setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    if (::bind(server_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        ::close(server_fd_);
        server_fd_ = -1;
        http_running_ = false;
        return;
    }

    if (::listen(server_fd_, 16) < 0) {
        ::close(server_fd_);
        server_fd_ = -1;
        http_running_ = false;
        return;
    }

    while (http_running_) {
        sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);
        int client_fd = ::accept(server_fd_, reinterpret_cast<sockaddr*>(&client_addr), &client_len);
        if (client_fd < 0) {
            if (!http_running_) break;
            continue;
        }

        char buffer[1024];
        ssize_t bytes_read = ::recv(client_fd, buffer, sizeof(buffer) - 1, 0);
        if (bytes_read > 0) {
            std::string body = serialize();
            std::ostringstream response;
            response << "HTTP/1.1 200 OK\r\n"
                     << "Content-Type: text/plain; version=0.0.4\r\n"
                     << "Content-Length: " << body.size() << "\r\n"
                     << "Connection: close\r\n\r\n"
                     << body;
            std::string resp_str = response.str();
            ::send(client_fd, resp_str.c_str(), resp_str.size(), 0);
        }
        ::close(client_fd);
    }
}

}  // namespace hams
