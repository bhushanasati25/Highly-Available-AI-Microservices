#pragma once

#include <grpcpp/grpcpp.h>
#include <memory>
#include <string>

#include "ingestion_service.h"
#include "health_check.h"
#include "metrics.h"

namespace hams {

struct ServerConfig {
    std::string host{"0.0.0.0"};
    uint16_t grpc_port{50051};
    uint16_t health_port{8081};
    uint16_t metrics_port{9091};
};

class DataIngestionServer {
public:
    explicit DataIngestionServer(ServerConfig config);
    ~DataIngestionServer();

    void start();
    void wait();
    void shutdown();

private:
    ServerConfig config_;
    std::unique_ptr<grpc::Server> grpc_server_;
    DataIngestionServiceImpl service_;
    HealthChecker health_checker_;
};

}  // namespace hams
