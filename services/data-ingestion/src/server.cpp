#include "server.h"

#include <spdlog/spdlog.h>

namespace hams {

DataIngestionServer::DataIngestionServer(ServerConfig config)
    : config_(std::move(config)) {
    health_checker_.registerCheck("grpc_service", [this]() {
        return grpc_server_ != nullptr;
    });
}

DataIngestionServer::~DataIngestionServer() {
    shutdown();
}

void DataIngestionServer::start() {
    std::string server_address = config_.host + ":" + std::to_string(config_.grpc_port);

    grpc::ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&service_);

    grpc_server_ = builder.BuildAndStart();
    if (!grpc_server_) {
        spdlog::error("Failed to start gRPC server on {}", server_address);
        throw std::runtime_error("gRPC server start failure");
    }

    spdlog::info("Data Ingestion gRPC server listening on {}", server_address);

    health_checker_.start(5);
    health_checker_.startHttpServer(config_.health_port);

    MetricsCollector::getInstance().startHttpServer(config_.metrics_port);
}

void DataIngestionServer::wait() {
    if (grpc_server_) {
        grpc_server_->Wait();
    }
}

void DataIngestionServer::shutdown() {
    spdlog::info("Shutting down Data Ingestion Server...");
    if (grpc_server_) {
        grpc_server_->Shutdown();
    }
    health_checker_.stop();
    MetricsCollector::getInstance().stopHttpServer();
    spdlog::info("Data Ingestion Server shutdown complete.");
}

}  // namespace hams
