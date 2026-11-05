#pragma once

#include <string>
#include <vector>
#include <functional>
#include <memory>
#include <mutex>
#include <atomic>

#include "preprocessing.grpc.pb.h"

namespace hams {

struct StageDefinition {
    std::string name;
    std::string type;
    int32_t order{0};
    std::function<bool(double& stage_progress, std::string& err_msg)> execute_fn;
};

class Pipeline {
public:
    explicit Pipeline(std::string job_id);

    void addStage(StageDefinition stage);
    bool run(std::function<void(const std::string& stage_name, double progress, Status status)> progress_callback);

    void cancel();
    bool isCancelled() const;

    PipelineStatusResponse getStatus() const;

private:
    std::string job_id_;
    std::vector<StageDefinition> stages_;
    std::atomic<bool> cancelled_{false};
    mutable std::mutex mutex_;
    PipelineStatusResponse status_record_;
};

}  // namespace hams
