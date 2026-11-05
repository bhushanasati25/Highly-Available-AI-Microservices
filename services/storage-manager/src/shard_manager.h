#pragma once

#include <string>
#include <vector>
#include <map>
#include <set>
#include <mutex>
#include <cstdint>

namespace hams {

struct StorageNode {
    std::string node_id;
    std::string address;
    uint16_t port{0};
    bool active{true};
};

class ShardManager {
public:
    explicit ShardManager(size_t virtual_nodes_per_node = 100);

    void addNode(const StorageNode& node);
    void removeNode(const std::string& node_id);
    void setNodeStatus(const std::string& node_id, bool active);

    std::string getNodeForKey(const std::string& key) const;
    std::vector<std::string> getReplicaNodes(const std::string& key, size_t replication_factor) const;

    size_t getNodeCount() const;
    std::vector<StorageNode> getAllNodes() const;

private:
    uint32_t hash(const std::string& str) const;

    size_t virtual_nodes_per_node_;
    mutable std::mutex mutex_;
    std::map<uint32_t, std::string> ring_; // hash -> node_id
    std::map<std::string, StorageNode> nodes_; // node_id -> StorageNode
};

}  // namespace hams
