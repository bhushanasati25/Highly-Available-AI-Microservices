#include "health_check.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>

namespace hams {

HealthChecker::HealthChecker()
    : start_time_(std::chrono::steady_clock::now()) {}

HealthChecker::~HealthChecker() {
    stop();
}

void HealthChecker::registerCheck(const std::string& name, std::function<bool()> check) {
    std::lock_guard<std::mutex> lock(mutex_);
    checks_[name] = std::move(check);
    results_[name] = HealthCheckResult{true, std::chrono::system_clock::now()};
    spdlog::info("Registered health check: {}", name);
}

void HealthChecker::start(uint32_t interval_seconds) {
    if (running_.exchange(true)) {
        return; // Already running
    }
    check_thread_ = std::thread(&HealthChecker::runChecks, this, interval_seconds);
    spdlog::info("HealthChecker background worker started with interval {}s", interval_seconds);
}

void HealthChecker::stop() {
    if (running_.exchange(false)) {
        cv_.notify_all();
        if (check_thread_.joinable()) {
            check_thread_.join();
        }
    }

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

bool HealthChecker::isHealthy() const {
    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto& [name, result] : results_) {
        if (!result.passed) {
            return false;
        }
    }
    return true;
}

std::string HealthChecker::formatTimestamp(std::chrono::system_clock::time_point tp) {
    auto time_t_val = std::chrono::system_clock::to_time_t(tp);
    std::tm tm_buf{};
#if defined(_WIN32)
    gmtime_s(&tm_buf, &time_t_val);
#else
    gmtime_r(&time_t_val, &tm_buf);
#endif
    std::ostringstream ss;
    ss << std::put_time(&tm_buf, "%Y-%m-%dT%H:%M:%SZ");
    return ss.str();
}

std::string HealthChecker::getStatus() const {
    std::lock_guard<std::mutex> lock(mutex_);
    bool overall_healthy = true;
    nlohmann::json checks_json = nlohmann::json::object();

    for (const auto& [name, result] : results_) {
        if (!result.passed) {
            overall_healthy = false;
        }
        checks_json[name] = {
            {"status", result.passed ? "pass" : "fail"},
            {"timestamp", formatTimestamp(result.timestamp)}
        };
    }

    auto now_steady = std::chrono::steady_clock::now();
    auto uptime_sec = std::chrono::duration_cast<std::chrono::seconds>(now_steady - start_time_).count();

    nlohmann::json doc = {
        {"status", overall_healthy ? "healthy" : "unhealthy"},
        {"checks", checks_json},
        {"uptime_seconds", uptime_sec}
    };

    return doc.dump(2);
}

void HealthChecker::executeChecks() {
    std::map<std::string, std::function<bool()>> checks_copy;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        checks_copy = checks_;
    }

    auto now = std::chrono::system_clock::now();
    for (const auto& [name, check_fn] : checks_copy) {
        bool passed = false;
        try {
            passed = check_fn();
        } catch (const std::exception& e) {
            spdlog::error("Health check '{}' threw exception: {}", name, e.what());
            passed = false;
        } catch (...) {
            spdlog::error("Health check '{}' threw unknown error", name);
            passed = false;
        }

        std::lock_guard<std::mutex> lock(mutex_);
        results_[name] = HealthCheckResult{passed, now};
    }
}

void HealthChecker::runChecks(uint32_t interval_seconds) {
    while (running_) {
        executeChecks();
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait_for(lock, std::chrono::seconds(interval_seconds), [this]() {
            return !running_.load();
        });
    }
}

void HealthChecker::startHttpServer(uint16_t port) {
    if (http_running_.exchange(true)) {
        return;
    }
    http_thread_ = std::thread(&HealthChecker::runHttpServer, this, port);
    spdlog::info("HealthChecker HTTP server listening on port {}", port);
}

void HealthChecker::runHttpServer(uint16_t port) {
    server_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        spdlog::error("HealthChecker failed to create socket on port {}", port);
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
        spdlog::error("HealthChecker failed to bind to port {}", port);
        ::close(server_fd_);
        server_fd_ = -1;
        http_running_ = false;
        return;
    }

    if (::listen(server_fd_, 16) < 0) {
        spdlog::error("HealthChecker listen failed on port {}", port);
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
            buffer[bytes_read] = '\0';
            std::string req(buffer);

            bool is_healthy = this->isHealthy();
            std::string status_body = this->getStatus();

            std::ostringstream response;
            if (req.rfind("GET /health", 0) == 0 || req.rfind("GET /ready", 0) == 0 || req.rfind("GET / ", 0) == 0) {
                int code = is_healthy ? 200 : 503;
                std::string status_line = is_healthy ? "200 OK" : "503 Service Unavailable";
                response << "HTTP/1.1 " << status_line << "\r\n"
                         << "Content-Type: application/json\r\n"
                         << "Content-Length: " << status_body.size() << "\r\n"
                         << "Connection: close\r\n\r\n"
                         << status_body;
            } else {
                std::string not_found = "{\"error\": \"Not Found\"}";
                response << "HTTP/1.1 404 Not Found\r\n"
                         << "Content-Type: application/json\r\n"
                         << "Content-Length: " << not_found.size() << "\r\n"
                         << "Connection: close\r\n\r\n"
                         << not_found;
            }

            std::string resp_str = response.str();
            ::send(client_fd, resp_str.c_str(), resp_str.size(), 0);
        }
        ::close(client_fd);
    }
}

}  // namespace hams
