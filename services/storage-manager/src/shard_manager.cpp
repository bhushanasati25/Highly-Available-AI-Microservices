#include "shard_manager.h"

#include <functional>
#include <spdlog/spdlog.h>

namespace hams {

ShardManager::ShardManager(size_t virtual_nodes_per_node)
    : virtual_nodes_per_node_(virtual_nodes_per_node) {}

uint32_t ShardManager::hash(const std::string& str) const {
    // 32-bit FNV-1a hash for fast and uniform distribution
    uint32_t h = 2166136261u;
    for (char c : str) {
        h ^= static_cast<uint8_t>(c);
        h *= 16777619u;
    }
    return h;
}

void ShardManager::addNode(const StorageNode& node) {
    std::lock_guard<std::mutex> lock(mutex_);
    nodes_[node.node_id] = node;

    for (size_t i = 0; i < virtual_nodes_per_node_; ++i) {
        std::string vnode_key = node.node_id + "#vnode#" + std::to_string(i);
        uint32_t vnode_hash = hash(vnode_key);
        ring_[vnode_hash] = node.node_id;
    }

    spdlog::info("ShardManager: added node {} with {} virtual replicas",
                 node.node_id, virtual_nodes_per_node_);
}

void ShardManager::removeNode(const std::string& node_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    nodes_.erase(node_id);

    for (auto it = ring_.begin(); it != ring_.end();) {
        if (it->second == node_id) {
            it = ring_.erase(it);
        } else {
            ++it;
        }
    }

    spdlog::info("ShardManager: removed node {}", node_id);
}

void ShardManager::setNodeStatus(const std::string& node_id, bool active) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = nodes_.find(node_id);
    if (it != nodes_.end()) {
        it->second.active = active;
        spdlog::info("ShardManager: node {} active={}", node_id, active);
    }
}

std::string ShardManager::getNodeForKey(const std::string& key) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (ring_.empty()) return "";

    uint32_t key_hash = hash(key);
    auto it = ring_.lower_bound(key_hash);
    if (it == ring_.end()) {
        it = ring_.begin();
    }

    // Ensure node is active
    auto start_it = it;
    do {
        auto node_it = nodes_.find(it->second);
        if (node_it != nodes_.end() && node_it->second.active) {
            return it->second;
        }
        ++it;
        if (it == ring_.end()) it = ring_.begin();
    } while (it != start_it);

    return "";
}

std::vector<std::string> ShardManager::getReplicaNodes(const std::string& key, size_t replication_factor) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (ring_.empty() || replication_factor == 0) return {};

    uint32_t key_hash = hash(key);
    auto it = ring_.lower_bound(key_hash);
    if (it == ring_.end()) it = ring_.begin();

    std::vector<std::string> selected;
    std::set<std::string> unique_nodes;

    auto start_it = it;
    do {
        const std::string& node_id = it->second;
        auto node_info = nodes_.find(node_id);
        if (node_info != nodes_.end() && node_info->second.active) {
            if (unique_nodes.insert(node_id).second) {
                selected.push_back(node_id);
                if (selected.size() >= replication_factor) {
                    break;
                }
            }
        }
        ++it;
        if (it == ring_.end()) it = ring_.begin();
    } while (it != start_it && unique_nodes.size() < nodes_.size());

    return selected;
}

size_t ShardManager::getNodeCount() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return nodes_.size();
}

std::vector<StorageNode> ShardManager::getAllNodes() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<StorageNode> res;
    for (const auto& [_, node] : nodes_) {
        res.push_back(node);
    }
    return res;
}

}  // namespace hams
