#include "ingestion_service.h"

#include <spdlog/spdlog.h>
#include <random>
#include <sstream>
#include <iomanip>

namespace hams {

DataIngestionServiceImpl::DataIngestionServiceImpl()
    : circuit_breaker_("data-ingestion", 5, std::chrono::seconds(15), 3) {
    auto& m = MetricsCollector::getInstance();
    m.registerMetric("ingestion_jobs_total", MetricType::COUNTER, "Total ingestion jobs");
    m.registerMetric("ingestion_bytes_total", MetricType::COUNTER, "Total bytes ingested");
    m.registerMetric("ingestion_records_total", MetricType::COUNTER, "Total records processed");
    m.registerMetric("ingestion_active_jobs", MetricType::GAUGE, "Active ingestion jobs");
}

std::string DataIngestionServiceImpl::generateJobId() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<uint64_t> dis;

    std::stringstream ss;
    ss << "job-" << std::hex << std::setw(16) << std::setfill('0') << dis(gen);
    return ss.str();
}

grpc::Status DataIngestionServiceImpl::IngestData(
    grpc::ServerContext* /*context*/,
    grpc::ServerReader<DataChunk>* reader,
    IngestResponse* response) {

    try {
        return circuit_breaker_.execute([&]() -> grpc::Status {
            std::string job_id = generateJobId();
            auto now = std::chrono::system_clock::now();

            IngestionJobRecord record;
            record.job_id = job_id;
            record.status = Status::PROCESSING;
            record.start_time = now;

            {
                std::lock_guard<std::mutex> lock(jobs_mutex_);
                jobs_[job_id] = record;
            }

            auto& metrics = MetricsCollector::getInstance();
            metrics.incrementCounter("ingestion_jobs_total");
            metrics.setGauge("ingestion_active_jobs", getActiveJobCount());

            DataChunk chunk;
            int64_t total_bytes = 0;
            std::string accumulated;

            while (reader->Read(&chunk)) {
                total_bytes += chunk.data().size();
                accumulated.append(chunk.data());
            }

            metrics.incrementCounter("ingestion_bytes_total", total_bytes);

            // Basic validation heuristic
            ValidationResult val_res;
            if (accumulated.rfind("{", 0) == 0 || accumulated.rfind("[", 0) == 0) {
                val_res = DataValidator::validateJSON(accumulated);
            } else {
                val_res = DataValidator::validateCSV(accumulated);
            }

            {
                std::lock_guard<std::mutex> lock(jobs_mutex_);
                auto& rec = jobs_[job_id];
                rec.bytes_received = total_bytes;
                rec.records_processed = val_res.records_detected;
                rec.error_count = static_cast<int32_t>(val_res.errors.size());
                rec.progress = 1.0;
                rec.end_time = std::chrono::system_clock::now();
                rec.status = val_res.valid ? Status::OK : Status::ERROR;
            }

            metrics.incrementCounter("ingestion_records_total", val_res.records_detected);
            metrics.setGauge("ingestion_active_jobs", getActiveJobCount());

            response->set_job_id(job_id);
            response->set_status(val_res.valid ? Status::OK : Status::ERROR);
            response->set_records_processed(val_res.records_detected);
            response->set_bytes_received(total_bytes);

            for (const auto& err : val_res.errors) {
                response->add_errors(err);
            }

            spdlog::info("Completed IngestData: job_id={}, bytes={}, records={}, valid={}",
                         job_id, total_bytes, val_res.records_detected, val_res.valid);

            return grpc::Status::OK;
        });
    } catch (const CircuitBreakerOpenException& e) {
        spdlog::warn("IngestData rejected by circuit breaker: {}", e.what());
        return grpc::Status(grpc::StatusCode::UNAVAILABLE, e.what());
    } catch (const std::exception& e) {
        spdlog::error("IngestData exception: {}", e.what());
        return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
    }
}

grpc::Status DataIngestionServiceImpl::GetIngestionStatus(
    grpc::ServerContext* /*context*/,
    const StatusRequest* request,
    StatusResponse* response) {

    std::lock_guard<std::mutex> lock(jobs_mutex_);
    auto it = jobs_.find(request->job_id());
    if (it == jobs_.end()) {
        return grpc::Status(grpc::StatusCode::NOT_FOUND, "Job ID not found");
    }

    const auto& rec = it->second;
    response->set_job_id(rec.job_id);
    response->set_status(rec.status);
    response->set_progress(rec.progress);
    response->set_records_processed(rec.records_processed);
    response->set_error_count(rec.error_count);

    auto start_secs = std::chrono::duration_cast<std::chrono::seconds>(rec.start_time.time_since_epoch()).count();
    response->mutable_start_time()->set_seconds(start_secs);

    if (rec.progress >= 1.0) {
        auto end_secs = std::chrono::duration_cast<std::chrono::seconds>(rec.end_time.time_since_epoch()).count();
        response->mutable_end_time()->set_seconds(end_secs);
    }

    return grpc::Status::OK;
}

grpc::Status DataIngestionServiceImpl::ValidateData(
    grpc::ServerContext* /*context*/,
    const ValidationRequest* request,
    ValidationResponse* response) {

    ValidationResult res;
    switch (request->format()) {
        case DataFormat::CSV:
            res = DataValidator::validateCSV(request->data());
            break;
        case DataFormat::JSON:
            res = DataValidator::validateJSON(request->data());
            break;
        case DataFormat::PARQUET:
            res = DataValidator::validateParquet(request->data());
            break;
        case DataFormat::BINARY:
        default:
            res = DataValidator::validateBinary(request->data());
            break;
    }

    response->set_valid(res.valid);
    for (const auto& err_str : res.errors) {
        auto* err = response->add_errors();
        err->set_field("payload");
        err->set_message(err_str);
        err->set_severity("ERROR");
    }

    return grpc::Status::OK;
}

size_t DataIngestionServiceImpl::getActiveJobCount() const {
    std::lock_guard<std::mutex> lock(jobs_mutex_);
    size_t count = 0;
    for (const auto& [_, rec] : jobs_) {
        if (rec.status == Status::PROCESSING || rec.status == Status::PENDING) {
            count++;
        }
    }
    return count;
}

}  // namespace hams
