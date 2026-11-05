#include <gtest/gtest.h>
#include "data_validator.h"

TEST(DataValidatorTest, ValidCSV) {
    std::string csv_data = "id,name,val\n1,alpha,10.5\n2,beta,20.1\n";
    auto res = hams::DataValidator::validateCSV(csv_data, 3);
    EXPECT_TRUE(res.valid);
    EXPECT_EQ(res.records_detected, 2);
    EXPECT_TRUE(res.errors.empty());
}

TEST(DataValidatorTest, MismatchedCSVColumns) {
    std::string bad_csv = "id,name,val\n1,alpha\n";
    auto res = hams::DataValidator::validateCSV(bad_csv);
    EXPECT_FALSE(res.valid);
    EXPECT_FALSE(res.errors.empty());
}

TEST(DataValidatorTest, ValidJSON) {
    std::string json_data = "[{\"id\": 1, \"name\": \"sample\"}, {\"id\": 2, \"name\": \"sample2\"}]";
    auto res = hams::DataValidator::validateJSON(json_data);
    EXPECT_TRUE(res.valid);
    EXPECT_EQ(res.records_detected, 2);
}

TEST(DataValidatorTest, InvalidJSON) {
    std::string bad_json = "{\"broken\": json";
    auto res = hams::DataValidator::validateJSON(bad_json);
    EXPECT_FALSE(res.valid);
    EXPECT_FALSE(res.errors.empty());
}

TEST(DataValidatorTest, ParquetMagicBytes) {
    std::string mock_parquet = "PAR1" + std::string(100, '\x00') + "PAR1";
    auto res = hams::DataValidator::validateParquet(mock_parquet);
    EXPECT_TRUE(res.valid);

    std::string bad_parquet = "BAD1" + std::string(100, '\x00') + "PAR1";
    auto bad_res = hams::DataValidator::validateParquet(bad_parquet);
    EXPECT_FALSE(bad_res.valid);
}

TEST(DataValidatorTest, BinaryChecksum) {
    std::string bin_data = "DistributedSystemsRobustDataPayload";
    uint32_t expected_crc = hams::DataValidator::calculateCRC32(bin_data);

    auto res = hams::DataValidator::validateBinary(bin_data, expected_crc);
    EXPECT_TRUE(res.valid);

    auto bad_res = hams::DataValidator::validateBinary(bin_data, expected_crc + 1);
    EXPECT_FALSE(bad_res.valid);
}
