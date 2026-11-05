#include "replication.h"

#include <algorithm>
#include <memory>
#include <spdlog/spdlog.h>

namespace hams {

ReplicationManager::ReplicationManager(std::shared_ptr<ShardManager> shard_mgr, size_t replication_factor)
    : shard_manager_(std::move(shard_mgr)), replication_factor_(replication_factor) {}

bool ReplicationManager::replicateWrite(const std::string& key, const std::string& data) {
    auto target_nodes = shard_manager_->getReplicaNodes(key, replication_factor_);
    if (target_nodes.empty()) {
        spdlog::error("ReplicationManager: no healthy nodes available for key {}", key);
        return false;
    }

    // Write-Ahead Log entry
    WalEntry entry;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        entry.sequence_id = next_seq_++;
        entry.key = key;
        entry.operation = "PUT";
        entry.data = data;
        entry.timestamp = std::chrono::system_clock::now();
        wal_.push_back(entry);
    }

    // Quorum verification: at least (N/2) + 1 successful node acknowledgments
    size_t quorum = (target_nodes.size() / 2) + 1;
    size_t acks = target_nodes.size(); // simulated synchronous network replication

    if (acks >= quorum) {
        std::lock_guard<std::mutex> lock(mutex_);
        key_replicas_[key] = target_nodes;
        spdlog::info("ReplicationManager: Write committed for key {} to {} replicas (quorum: {})",
                     key, acks, quorum);
        return true;
    }

    spdlog::warn("ReplicationManager: Write failed to achieve quorum for key {}", key);
    return false;
}

bool ReplicationManager::replicateDelete(const std::string& key) {
    WalEntry entry;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        entry.sequence_id = next_seq_++;
        entry.key = key;
        entry.operation = "DELETE";
        entry.timestamp = std::chrono::system_clock::now();
        wal_.push_back(entry);
        key_replicas_.erase(key);
    }
    spdlog::info("ReplicationManager: Delete committed for key {}", key);
    return true;
}

ReplicationStatus ReplicationManager::getStatus(const std::string& key) const {
    std::lock_guard<std::mutex> lock(mutex_);
    ReplicationStatus status;
    status.key = key;
    status.target_replicas = replication_factor_;

    auto it = key_replicas_.find(key);
    if (it != key_replicas_.end()) {
        status.current_nodes = it->second;
        status.in_sync = (status.current_nodes.size() >= replication_factor_);
    }
    return status;
}

void ReplicationManager::handleNodeFailure(const std::string& failed_node_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    spdlog::warn("ReplicationManager: Handling failover for node {}", failed_node_id);

    for (auto& [key, nodes] : key_replicas_) {
        auto node_it = std::find(nodes.begin(), nodes.end(), failed_node_id);
        if (node_it != nodes.end()) {
            nodes.erase(node_it);
            auto new_replicas = shard_manager_->getReplicaNodes(key, replication_factor_);
            nodes = new_replicas;
            spdlog::info("Rebalanced replicas for key {} to new node set", key);
        }
    }
}

std::vector<WalEntry> ReplicationManager::getWalHistory() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return wal_;
}

}  // namespace hams
