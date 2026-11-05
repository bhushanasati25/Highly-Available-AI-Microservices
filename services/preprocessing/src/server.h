#pragma once

#include <grpcpp/grpcpp.h>
#include <memory>
#include <unordered_map>
#include <mutex>
#include <string>

#include "preprocessing.grpc.pb.h"
#include "pipeline.h"
#include "health_check.h"
#include "metrics.h"
#include "circuit_breaker.h"

namespace hams {

class PreprocessingServiceImpl final : public PreprocessingService::Service {
public:
    PreprocessingServiceImpl();

    grpc::Status ProcessData(
        grpc::ServerContext* context,
        const ProcessRequest* request,
        grpc::ServerWriter<ProcessResponse>* writer) override;

    grpc::Status ExtractFeatures(
        grpc::ServerContext* context,
        const FeatureRequest* request,
        FeatureResponse* response) override;

    grpc::Status GetPipelineStatus(
        grpc::ServerContext* context,
        const PipelineStatusRequest* request,
        PipelineStatusResponse* response) override;

private:
    mutable std::mutex mutex_;
    std::unordered_map<std::string, std::shared_ptr<Pipeline>> pipelines_;
    CircuitBreaker circuit_breaker_;
};

struct PreprocessingServerConfig {
    std::string host{"0.0.0.0"};
    uint16_t grpc_port{50052};
    uint16_t health_port{8082};
    uint16_t metrics_port{9092};
};

class PreprocessingServer {
public:
    explicit PreprocessingServer(PreprocessingServerConfig config);
    ~PreprocessingServer();

    void start();
    void wait();
    void shutdown();

private:
    PreprocessingServerConfig config_;
    std::unique_ptr<grpc::Server> grpc_server_;
    PreprocessingServiceImpl service_;
    HealthChecker health_checker_;
};

}  // namespace hams
