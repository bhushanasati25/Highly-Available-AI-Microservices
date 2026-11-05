#include "data_validator.h"

#include <sstream>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

namespace hams {

ValidationFormat DataValidator::parseFormat(const std::string& format_str) {
    if (format_str == "CSV" || format_str == "csv") return ValidationFormat::CSV;
    if (format_str == "JSON" || format_str == "json") return ValidationFormat::JSON;
    if (format_str == "PARQUET" || format_str == "parquet") return ValidationFormat::PARQUET;
    if (format_str == "BINARY" || format_str == "bin") return ValidationFormat::BINARY;
    return ValidationFormat::UNKNOWN;
}

uint32_t DataValidator::calculateCRC32(const std::string& data) {
    uint32_t crc = 0xFFFFFFFF;
    for (uint8_t byte : data) {
        crc ^= byte;
        for (int i = 0; i < 8; ++i) {
            crc = (crc >> 1) ^ (0xEDB88320 & (-(crc & 1)));
        }
    }
    return ~crc;
}

ValidationResult DataValidator::validateCSV(const std::string& data, size_t expected_cols) {
    ValidationResult res;
    if (data.empty()) {
        res.errors.push_back("CSV data is empty");
        return res;
    }

    std::istringstream stream(data);
    std::string line;
    size_t line_num = 0;
    size_t header_cols = 0;

    while (std::getline(stream, line)) {
        if (line.empty() || line == "\r") continue;
        line_num++;

        std::istringstream line_stream(line);
        std::string cell;
        size_t cols = 0;
        while (std::getline(line_stream, cell, ',')) {
            cols++;
        }

        if (line_num == 1) {
            header_cols = cols;
            if (expected_cols > 0 && header_cols != expected_cols) {
                res.errors.push_back("Header column count (" + std::to_string(header_cols) +
                                    ") does not match expected (" + std::to_string(expected_cols) + ")");
            }
        } else {
            if (cols != header_cols) {
                res.errors.push_back("Line " + std::to_string(line_num) +
                                    " column count mismatch: expected " + std::to_string(header_cols) +
                                    ", got " + std::to_string(cols));
            }
            res.records_detected++;
        }
    }

    res.valid = res.errors.empty();
    return res;
}

ValidationResult DataValidator::validateJSON(const std::string& data) {
    ValidationResult res;
    if (data.empty()) {
        res.errors.push_back("JSON data is empty");
        return res;
    }

    try {
        auto parsed = nlohmann::json::parse(data);
        if (parsed.is_array()) {
            res.records_detected = parsed.size();
        } else if (parsed.is_object()) {
            res.records_detected = 1;
        } else {
            res.errors.push_back("JSON root must be an object or array");
        }
    } catch (const nlohmann::json::parse_error& e) {
        res.errors.push_back(std::string("JSON parse error: ") + e.what());
    }

    res.valid = res.errors.empty();
    return res;
}

ValidationResult DataValidator::validateParquet(const std::string& data) {
    ValidationResult res;
    // Parquet files must be at least 8 bytes long and start and end with "PAR1"
    if (data.size() < 8) {
        res.errors.push_back("Parquet file too small (< 8 bytes)");
        return res;
    }

    std::string magic_start = data.substr(0, 4);
    std::string magic_end = data.substr(data.size() - 4, 4);

    if (magic_start != "PAR1") {
        res.errors.push_back("Invalid Parquet magic header: expected 'PAR1'");
    }
    if (magic_end != "PAR1") {
        res.errors.push_back("Invalid Parquet magic footer: expected 'PAR1'");
    }

    res.valid = res.errors.empty();
    if (res.valid) {
        res.records_detected = 1; // Verified parquet payload
    }
    return res;
}

ValidationResult DataValidator::validateBinary(const std::string& data, uint32_t expected_checksum) {
    ValidationResult res;
    if (data.empty()) {
        res.errors.push_back("Binary data is empty");
        return res;
    }

    if (expected_checksum != 0) {
        uint32_t actual_crc = calculateCRC32(data);
        if (actual_crc != expected_checksum) {
            res.errors.push_back("CRC32 checksum mismatch: expected " +
                                std::to_string(expected_checksum) +
                                ", got " + std::to_string(actual_crc));
        }
    }

    res.valid = res.errors.empty();
    res.records_detected = data.size();
    return res;
}

}  // namespace hams
