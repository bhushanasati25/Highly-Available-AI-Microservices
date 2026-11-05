#include <gtest/gtest.h>
#include "shard_manager.h"

TEST(ShardManagerTest, ConsistentHashingDistribution) {
    hams::ShardManager sm(50);
    sm.addNode({"node-1", "10.0.0.1", 8001, true});
    sm.addNode({"node-2", "10.0.0.2", 8002, true});
    sm.addNode({"node-3", "10.0.0.3", 8003, true});

    EXPECT_EQ(sm.getNodeCount(), 3);

    std::string n1 = sm.getNodeForKey("dataset_2026_01.csv");
    std::string n2 = sm.getNodeForKey("dataset_2026_01.csv");
    EXPECT_EQ(n1, n2); // Deterministic mapping
    EXPECT_FALSE(n1.empty());

    auto replicas = sm.getReplicaNodes("dataset_2026_01.csv", 2);
    EXPECT_EQ(replicas.size(), 2);
    EXPECT_NE(replicas[0], replicas[1]);
}

TEST(ShardManagerTest, NodeFailureHandling) {
    hams::ShardManager sm(50);
    sm.addNode({"node-1", "10.0.0.1", 8001, true});
    sm.addNode({"node-2", "10.0.0.2", 8002, true});

    std::string key = "critical_tensor_weights.bin";
    std::string original = sm.getNodeForKey(key);

    // Mark that node inactive
    sm.setNodeStatus(original, false);
    std::string failover = sm.getNodeForKey(key);

    EXPECT_NE(original, failover);
    EXPECT_FALSE(failover.empty());
}
