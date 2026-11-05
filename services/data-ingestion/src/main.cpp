#include <csignal>
#include <cstdlib>
#include <iostream>
#include <spdlog/spdlog.h>

#include "server.h"

static std::unique_ptr<hams::DataIngestionServer> g_server;

void handle_signal(int signal) {
    spdlog::info("Received signal {}, initiating graceful shutdown...", signal);
    if (g_server) {
        g_server->shutdown();
    }
}

int main(int /*argc*/, char** /*argv*/) {
    spdlog::set_level(spdlog::level::info);
    spdlog::info("Starting Highly Available AI Microservices - Data Ingestion Service...");

    hams::ServerConfig config;

    const char* env_grpc_port = std::getenv("HAMS_INGESTION_PORT");
    if (env_grpc_port) config.grpc_port = static_cast<uint16_t>(std::atoi(env_grpc_port));

    const char* env_health_port = std::getenv("HAMS_HEALTH_PORT");
    if (env_health_port) config.health_port = static_cast<uint16_t>(std::atoi(env_health_port));

    const char* env_metrics_port = std::getenv("HAMS_METRICS_PORT");
    if (env_metrics_port) config.metrics_port = static_cast<uint16_t>(std::atoi(env_metrics_port));

    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);

    try {
        g_server = std::make_unique<hams::DataIngestionServer>(config);
        g_server->start();
        g_server->wait();
    } catch (const std::exception& e) {
        spdlog::critical("Fatal server error: {}", e.what());
        return 1;
    }

    spdlog::info("Service terminated cleanly.");
    return 0;
}
