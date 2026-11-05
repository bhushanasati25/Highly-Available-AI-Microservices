#include "server.h"

#include <spdlog/spdlog.h>

namespace hams {

PreprocessingServiceImpl::PreprocessingServiceImpl()
    : circuit_breaker_("preprocessing", 5, std::chrono::seconds(15), 3) {
    auto& m = MetricsCollector::getInstance();
    m.registerMetric("preprocessing_pipelines_total", MetricType::COUNTER, "Total pipelines launched");
    m.registerMetric("preprocessing_features_extracted", MetricType::COUNTER, "Features extracted count");
}

grpc::Status PreprocessingServiceImpl::ProcessData(
    grpc::ServerContext* /*context*/,
    const ProcessRequest* request,
    grpc::ServerWriter<ProcessResponse>* writer) {

    try {
        return circuit_breaker_.execute([&]() -> grpc::Status {
            std::string job_id = request->job_id();
            auto pipeline = std::make_shared<Pipeline>(job_id);

            // Configure stages from request
            if (request->pipeline_config().stages_size() == 0) {
                // Add default stages: cleaning, normalization, tokenization
                pipeline->addStage({"cleaning", "cleaner", 1, [](double& prog, std::string&) {
                    prog = 1.0;
                    return true;
                }});
                pipeline->addStage({"normalization", "scaler", 2, [](double& prog, std::string&) {
                    prog = 1.0;
                    return true;
                }});
                pipeline->addStage({"feature_generation", "fe_gen", 3, [](double& prog, std::string&) {
                    prog = 1.0;
                    return true;
                }});
            } else {
                for (const auto& stage_cfg : request->pipeline_config().stages()) {
                    pipeline->addStage({stage_cfg.name(), stage_cfg.type(), stage_cfg.order(),
                                       [](double& prog, std::string&) {
                        prog = 1.0;
                        return true;
                    }});
                }
            }

            {
                std::lock_guard<std::mutex> lock(mutex_);
                pipelines_[job_id] = pipeline;
            }

            MetricsCollector::getInstance().incrementCounter("preprocessing_pipelines_total");

            bool ok = pipeline->run([&](const std::string& stage_name, double progress, Status status) {
                ProcessResponse resp;
                resp.set_stage(stage_name);
                resp.set_progress(progress);
                resp.set_status(status);
                resp.set_output_path(request->output_path());
                writer->Write(resp);
            });

            return ok ? grpc::Status::OK : grpc::Status(grpc::StatusCode::INTERNAL, "Pipeline stage failed");
        });
    } catch (const CircuitBreakerOpenException& e) {
        return grpc::Status(grpc::StatusCode::UNAVAILABLE, e.what());
    } catch (const std::exception& e) {
        return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
    }
}

grpc::Status PreprocessingServiceImpl::ExtractFeatures(
    grpc::ServerContext* /*context*/,
    const FeatureRequest* request,
    FeatureResponse* response) {

    try {
        return circuit_breaker_.execute([&]() -> grpc::Status {
            response->set_status(Status::OK);
            response->set_dimensions(request->feature_config().target_dimensions() > 0 ?
                                    request->feature_config().target_dimensions() : 64);
            response->set_output_path(request->input_path() + ".features.bin");

            response->add_feature_ids("stat_features");
            response->add_feature_ids("embedding_vector");
            response->add_feature_ids("one_hot_encodings");

            MetricsCollector::getInstance().incrementCounter("preprocessing_features_extracted", 3);
            return grpc::Status::OK;
        });
    } catch (const CircuitBreakerOpenException& e) {
        return grpc::Status(grpc::StatusCode::UNAVAILABLE, e.what());
    }
}

grpc::Status PreprocessingServiceImpl::GetPipelineStatus(
    grpc::ServerContext* /*context*/,
    const PipelineStatusRequest* request,
    PipelineStatusResponse* response) {

    std::lock_guard<std::mutex> lock(mutex_);
    auto it = pipelines_.find(request->job_id());
    if (it == pipelines_.end()) {
        return grpc::Status(grpc::StatusCode::NOT_FOUND, "Pipeline job not found");
    }

    *response = it->second->getStatus();
    return grpc::Status::OK;
}

PreprocessingServer::PreprocessingServer(PreprocessingServerConfig config)
    : config_(std::move(config)) {
    health_checker_.registerCheck("grpc_service", [this]() {
        return grpc_server_ != nullptr;
    });
}

PreprocessingServer::~PreprocessingServer() {
    shutdown();
}

void PreprocessingServer::start() {
    std::string server_address = config_.host + ":" + std::to_string(config_.grpc_port);

    grpc::ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&service_);

    grpc_server_ = builder.BuildAndStart();
    if (!grpc_server_) {
        spdlog::error("Failed to start Preprocessing gRPC server on {}", server_address);
        throw std::runtime_error("gRPC server start failure");
    }

    spdlog::info("Preprocessing gRPC server listening on {}", server_address);

    health_checker_.start(5);
    health_checker_.startHttpServer(config_.health_port);
    MetricsCollector::getInstance().startHttpServer(config_.metrics_port);
}

void PreprocessingServer::wait() {
    if (grpc_server_) {
        grpc_server_->Wait();
    }
}

void PreprocessingServer::shutdown() {
    spdlog::info("Shutting down Preprocessing Server...");
    if (grpc_server_) {
        grpc_server_->Shutdown();
    }
    health_checker_.stop();
    MetricsCollector::getInstance().stopHttpServer();
    spdlog::info("Preprocessing Server shutdown complete.");
}

}  // namespace hams
