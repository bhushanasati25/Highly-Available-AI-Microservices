#include "pipeline.h"

#include <algorithm>
#include <spdlog/spdlog.h>

namespace hams {

Pipeline::Pipeline(std::string job_id)
    : job_id_(std::move(job_id)) {
    status_record_.set_job_id(job_id_);
    status_record_.set_status(Status::PENDING);
    status_record_.set_overall_progress(0.0);
}

void Pipeline::addStage(StageDefinition stage) {
    std::lock_guard<std::mutex> lock(mutex_);
    stages_.push_back(std::move(stage));
    std::sort(stages_.begin(), stages_.end(), [](const auto& a, const auto& b) {
        return a.order < b.order;
    });

    auto* st = status_record_.add_stages();
    st->set_name(stages_.back().name);
    st->set_status(Status::PENDING);
    st->set_progress(0.0);
}

void Pipeline::cancel() {
    cancelled_ = true;
    std::lock_guard<std::mutex> lock(mutex_);
    status_record_.set_status(Status::ERROR);
}

bool Pipeline::isCancelled() const {
    return cancelled_.load();
}

bool Pipeline::run(std::function<void(const std::string& stage_name, double progress, Status status)> progress_callback) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        status_record_.set_status(Status::PROCESSING);
    }

    size_t total_stages = stages_.size();
    if (total_stages == 0) {
        std::lock_guard<std::mutex> lock(mutex_);
        status_record_.set_status(Status::OK);
        status_record_.set_overall_progress(1.0);
        return true;
    }

    for (size_t i = 0; i < total_stages; ++i) {
        if (cancelled_) {
            spdlog::warn("Pipeline {} was cancelled during execution", job_id_);
            return false;
        }

        const auto& stage = stages_[i];
        spdlog::info("Executing pipeline {} stage {}: {}", job_id_, i + 1, stage.name);

        {
            std::lock_guard<std::mutex> lock(mutex_);
            status_record_.mutable_stages(static_cast<int>(i))->set_status(Status::PROCESSING);
        }

        if (progress_callback) {
            progress_callback(stage.name, 0.0, Status::PROCESSING);
        }

        double stage_prog = 0.0;
        std::string err_msg;
        bool success = true;

        if (stage.execute_fn) {
            success = stage.execute_fn(stage_prog, err_msg);
        } else {
            stage_prog = 1.0;
        }

        if (!success || cancelled_) {
            std::lock_guard<std::mutex> lock(mutex_);
            auto* s = status_record_.mutable_stages(static_cast<int>(i));
            s->set_status(Status::ERROR);
            if (!err_msg.empty()) s->add_errors(err_msg);
            status_record_.set_status(Status::ERROR);

            if (progress_callback) {
                progress_callback(stage.name, stage_prog, Status::ERROR);
            }
            return false;
        }

        double overall = static_cast<double>(i + 1) / static_cast<double>(total_stages);
        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto* s = status_record_.mutable_stages(static_cast<int>(i));
            s->set_status(Status::OK);
            s->set_progress(1.0);
            status_record_.set_overall_progress(overall);
        }

        if (progress_callback) {
            progress_callback(stage.name, 1.0, Status::OK);
        }
    }

    {
        std::lock_guard<std::mutex> lock(mutex_);
        status_record_.set_status(Status::OK);
        status_record_.set_overall_progress(1.0);
    }
    return true;
}

PipelineStatusResponse Pipeline::getStatus() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return status_record_;
}

}  // namespace hams
