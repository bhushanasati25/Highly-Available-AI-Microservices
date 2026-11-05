#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <mutex>
#include <chrono>
#include <memory>

#include "shard_manager.h"

namespace hams {

struct WalEntry {
    uint64_t sequence_id;
    std::string key;
    std::string operation; // PUT, DELETE
    std::string data;
    std::chrono::system_clock::time_point timestamp;
};

struct ReplicationStatus {
    std::string key;
    size_t target_replicas;
    std::vector<std::string> current_nodes;
    bool in_sync{false};
};

class ReplicationManager {
public:
    explicit ReplicationManager(std::shared_ptr<ShardManager> shard_mgr, size_t replication_factor = 3);

    bool replicateWrite(const std::string& key, const std::string& data);
    bool replicateDelete(const std::string& key);

    ReplicationStatus getStatus(const std::string& key) const;
    void handleNodeFailure(const std::string& failed_node_id);

    std::vector<WalEntry> getWalHistory() const;

private:
    std::shared_ptr<ShardManager> shard_manager_;
    size_t replication_factor_;
    mutable std::mutex mutex_;
    uint64_t next_seq_{1};
    std::vector<WalEntry> wal_;
    std::unordered_map<std::string, std::vector<std::string>> key_replicas_;
};

}  // namespace hams
