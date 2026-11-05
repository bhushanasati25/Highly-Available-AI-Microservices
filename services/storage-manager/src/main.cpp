#include <csignal>
#include <cstdlib>
#include <iostream>
#include <spdlog/spdlog.h>
#include <thread>
#include <chrono>

#include "storage_service.h"
#include "health_check.h"
#include "metrics.h"

static std::atomic<bool> g_running{true};

void handle_signal(int signal) {
    spdlog::info("Storage Manager received signal {}, shutting down...", signal);
    g_running = false;
}

int main(int /*argc*/, char** /*argv*/) {
    spdlog::set_level(spdlog::level::info);
    spdlog::info("Starting Highly Available AI Microservices - Storage Manager...");

    std::string root_dir = "/tmp/hams_storage";
    const char* env_dir = std::getenv("HAMS_STORAGE_ROOT");
    if (env_dir) root_dir = env_dir;

    uint16_t health_port = 8083;
    const char* env_health = std::getenv("HAMS_HEALTH_PORT");
    if (env_health) health_port = static_cast<uint16_t>(std::atoi(env_health));

    uint16_t metrics_port = 9093;
    const char* env_metrics = std::getenv("HAMS_METRICS_PORT");
    if (env_metrics) metrics_port = static_cast<uint16_t>(std::atoi(env_metrics));

    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);

    hams::StorageService storage(root_dir, 3);

    hams::HealthChecker health_checker;
    health_checker.registerCheck("storage_engine", [&]() {
        return storage.getShardManager()->getNodeCount() > 0;
    });
    health_checker.start(5);
    health_checker.startHttpServer(health_port);

    hams::MetricsCollector::getInstance().startHttpServer(metrics_port);

    spdlog::info("Storage Manager running. Health on :{}, Metrics on :{}", health_port, metrics_port);

    while (g_running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    health_checker.stop();
    hams::MetricsCollector::getInstance().stopHttpServer();
    spdlog::info("Storage Manager shutdown complete.");
    return 0;
}
