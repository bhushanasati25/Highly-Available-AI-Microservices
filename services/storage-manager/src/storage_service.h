#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <mutex>
#include <optional>

#include "shard_manager.h"
#include "replication.h"
#include "health_check.h"
#include "metrics.h"

namespace hams {

struct StorageMetadata {
    std::string key;
    size_t size_bytes{0};
    std::string checksum;
    std::string content_type;
    std::string primary_node;
    std::vector<std::string> replica_nodes;
    int64_t created_at{0};
};

class StorageService {
public:
    explicit StorageService(const std::string& storage_root, size_t replication_factor = 3);

    bool put(const std::string& key, const std::string& data, const std::string& content_type = "application/octet-stream");
    std::optional<std::string> get(const std::string& key);
    bool remove(const std::string& key);
    std::vector<StorageMetadata> list(const std::string& prefix = "");

    std::shared_ptr<ShardManager> getShardManager() const { return shard_manager_; }
    std::shared_ptr<ReplicationManager> getReplicationManager() const { return replication_manager_; }

private:
    std::string storage_root_;
    std::shared_ptr<ShardManager> shard_manager_;
    std::shared_ptr<ReplicationManager> replication_manager_;
    mutable std::mutex mutex_;
    std::unordered_map<std::string, StorageMetadata> metadata_store_;
    std::unordered_map<std::string, std::string> in_memory_cache_;
};

}  // namespace hams
