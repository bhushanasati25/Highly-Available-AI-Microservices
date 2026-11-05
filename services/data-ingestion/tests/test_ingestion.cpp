#include <gtest/gtest.h>
#include "ingestion_service.h"

TEST(DataIngestionServiceTest, InitializationAndJobCount) {
    hams::DataIngestionServiceImpl service;
    EXPECT_EQ(service.getActiveJobCount(), 0);
}

TEST(DataIngestionServiceTest, ValidateDataRPC) {
    hams::DataIngestionServiceImpl service;

    hams::ValidationRequest request;
    request.set_job_id("test-job-1");
    request.set_format(hams::DataFormat::CSV);
    request.set_data("col1,col2\nval1,val2\n");

    hams::ValidationResponse response;
    auto status = service.ValidateData(nullptr, &request, &response);

    EXPECT_TRUE(status.ok());
    EXPECT_TRUE(response.valid());
    EXPECT_EQ(response.errors_size(), 0);
}

TEST(DataIngestionServiceTest, ValidateDataRPCInvalid) {
    hams::DataIngestionServiceImpl service;

    hams::ValidationRequest request;
    request.set_job_id("test-job-2");
    request.set_format(hams::DataFormat::JSON);
    request.set_data("{broken json");

    hams::ValidationResponse response;
    auto status = service.ValidateData(nullptr, &request, &response);

    EXPECT_TRUE(status.ok());
    EXPECT_FALSE(response.valid());
    EXPECT_GT(response.errors_size(), 0);
}

TEST(DataIngestionServiceTest, GetNonExistentJobStatus) {
    hams::DataIngestionServiceImpl service;

    hams::StatusRequest req;
    req.set_job_id("non-existent-id");
    hams::StatusResponse resp;

    auto status = service.GetIngestionStatus(nullptr, &req, &resp);
    EXPECT_EQ(status.error_code(), grpc::StatusCode::NOT_FOUND);
}
