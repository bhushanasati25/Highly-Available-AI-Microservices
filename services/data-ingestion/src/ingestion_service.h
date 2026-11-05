#pragma once

#include <grpcpp/grpcpp.h>
#include <mutex>
#include <unordered_map>
#include <string>
#include <chrono>

#include "data_ingestion.grpc.pb.h"
#include "data_validator.h"
#include "circuit_breaker.h"
#include "metrics.h"

namespace hams {

struct IngestionJobRecord {
    std::string job_id;
    Status status{Status::PENDING};
    double progress{0.0};
    int64_t records_processed{0};
    int32_t error_count{0};
    int64_t bytes_received{0};
    std::chrono::system_clock::time_point start_time;
    std::chrono::system_clock::time_point end_time;
    std::string accumulated_data;
};

class DataIngestionServiceImpl final : public DataIngestionService::Service {
public:
    DataIngestionServiceImpl();

    grpc::Status IngestData(
        grpc::ServerContext* context,
        grpc::ServerReader<DataChunk>* reader,
        IngestResponse* response) override;

    grpc::Status GetIngestionStatus(
        grpc::ServerContext* context,
        const StatusRequest* request,
        StatusResponse* response) override;

    grpc::Status ValidateData(
        grpc::ServerContext* context,
        const ValidationRequest* request,
        ValidationResponse* response) override;

    size_t getActiveJobCount() const;

private:
    std::string generateJobId();

    mutable std::mutex jobs_mutex_;
    std::unordered_map<std::string, IngestionJobRecord> jobs_;
    CircuitBreaker circuit_breaker_;
};

}  // namespace hams
