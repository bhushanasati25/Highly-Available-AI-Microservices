#include "storage_service.h"

#include <chrono>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <spdlog/spdlog.h>

namespace hams {

namespace fs = std::filesystem;

StorageService::StorageService(const std::string& storage_root, size_t replication_factor)
    : storage_root_(storage_root),
      shard_manager_(std::make_shared<ShardManager>(50)),
      replication_manager_(std::make_shared<ReplicationManager>(shard_manager_, replication_factor)) {

    // Bootstrap default storage nodes for local cluster simulation
    for (int i = 1; i <= 5; ++i) {
        shard_manager_->addNode({
            "storage-node-" + std::to_string(i),
            "10.0.1." + std::to_string(10 + i),
            static_cast<uint16_t>(9000 + i),
            true
        });
    }

    std::error_code ec;
    fs::create_directories(storage_root_, ec);

    auto& m = MetricsCollector::getInstance();
    m.registerMetric("storage_objects_total", MetricType::GAUGE, "Current stored objects count");
    m.registerMetric("storage_bytes_total", MetricType::GAUGE, "Current storage bytes");
    m.registerMetric("storage_writes_total", MetricType::COUNTER, "Total write operations");
    m.registerMetric("storage_reads_total", MetricType::COUNTER, "Total read operations");
}

bool StorageService::put(const std::string& key, const std::string& data, const std::string& content_type) {
    if (key.empty()) return false;

    bool repl_ok = replication_manager_->replicateWrite(key, data);
    if (!repl_ok) return false;

    std::string primary = shard_manager_->getNodeForKey(key);
    auto replicas = shard_manager_->getReplicaNodes(key, 3);

    auto now_epoch = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    // Persist to local disk simulation
    try {
        fs::path file_path = fs::path(storage_root_) / key;
        fs::create_directories(file_path.parent_path());
        std::ofstream ofs(file_path, std::ios::binary);
        if (ofs.is_open()) {
            ofs.write(data.data(), data.size());
        }
    } catch (const std::exception& e) {
        spdlog::warn("StorageService: disk write failed, caching in memory: {}", e.what());
    }

    {
        std::lock_guard<std::mutex> lock(mutex_);
        in_memory_cache_[key] = data;

        StorageMetadata meta;
        meta.key = key;
        meta.size_bytes = data.size();
        meta.content_type = content_type;
        meta.primary_node = primary;
        meta.replica_nodes = replicas;
        meta.created_at = now_epoch;
        metadata_store_[key] = meta;
    }

    auto& m = MetricsCollector::getInstance();
    m.incrementCounter("storage_writes_total");
    m.setGauge("storage_objects_total", metadata_store_.size());

    spdlog::info("Stored object '{}' size={} bytes, primary={}", key, data.size(), primary);
    return true;
}

std::optional<std::string> StorageService::get(const std::string& key) {
    auto& m = MetricsCollector::getInstance();
    m.incrementCounter("storage_reads_total");

    std::lock_guard<std::mutex> lock(mutex_);
    auto it = in_memory_cache_.find(key);
    if (it != in_memory_cache_.end()) {
        return it->second;
    }

    fs::path file_path = fs::path(storage_root_) / key;
    if (fs::exists(file_path)) {
        std::ifstream ifs(file_path, std::ios::binary);
        if (ifs.is_open()) {
            std::stringstream ss;
            ss << ifs.rdbuf();
            return ss.str();
        }
    }

    return std::nullopt;
}

bool StorageService::remove(const std::string& key) {
    replication_manager_->replicateDelete(key);

    std::lock_guard<std::mutex> lock(mutex_);
    in_memory_cache_.erase(key);
    metadata_store_.erase(key);

    std::error_code ec;
    fs::remove(fs::path(storage_root_) / key, ec);

    MetricsCollector::getInstance().setGauge("storage_objects_total", metadata_store_.size());
    return true;
}

std::vector<StorageMetadata> StorageService::list(const std::string& prefix) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<StorageMetadata> res;
    for (const auto& [k, meta] : metadata_store_) {
        if (prefix.empty() || k.rfind(prefix, 0) == 0) {
            res.push_back(meta);
        }
    }
    return res;
}

}  // namespace hams
