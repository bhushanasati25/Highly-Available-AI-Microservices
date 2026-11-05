#include <gtest/gtest.h>
#include "storage_service.h"

TEST(StorageServiceTest, PutGetDeleteLifecycle) {
    hams::StorageService storage("/tmp/test_storage_root", 3);

    std::string key = "sample_dataset.csv";
    std::string content = "feature1,feature2\n0.5,1.2\n";

    bool put_ok = storage.put(key, content, "text/csv");
    EXPECT_TRUE(put_ok);

    auto retrieved = storage.get(key);
    ASSERT_TRUE(retrieved.has_value());
    EXPECT_EQ(*retrieved, content);

    auto list_all = storage.list("sample_");
    EXPECT_GE(list_all.size(), 1);
    EXPECT_EQ(list_all[0].key, key);

    bool del_ok = storage.remove(key);
    EXPECT_TRUE(del_ok);

    auto after_delete = storage.get(key);
    EXPECT_FALSE(after_delete.has_value());
}
