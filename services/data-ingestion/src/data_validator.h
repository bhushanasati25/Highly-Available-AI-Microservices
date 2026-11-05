#pragma once

#include <string>
#include <vector>
#include <cstdint>

namespace hams {

enum class ValidationFormat {
    CSV,
    JSON,
    PARQUET,
    BINARY,
    UNKNOWN
};

struct ValidationResult {
    bool valid{false};
    std::vector<std::string> errors;
    uint64_t records_detected{0};
};

class DataValidator {
public:
    static ValidationFormat parseFormat(const std::string& format_str);
    static ValidationResult validateCSV(const std::string& data, size_t expected_cols = 0);
    static ValidationResult validateJSON(const std::string& data);
    static ValidationResult validateParquet(const std::string& data);
    static ValidationResult validateBinary(const std::string& data, uint32_t expected_checksum = 0);

    static uint32_t calculateCRC32(const std::string& data);
};

}  // namespace hams
