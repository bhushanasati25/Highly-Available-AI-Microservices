#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "HAMS: Running Native C++17 Unit Test Suites"
echo "=========================================================="

CXX="${CXX:-clang++}"
CPP_FLAGS="-std=c++17 -Wall -Wextra -Ishared/cpp/include"
BUILD_TMP="/tmp/hams_cpp_tests"
mkdir -p "$BUILD_TMP"

FAILED=0

# 1. Data Validator Tests
echo ""
echo "--- [1/5] Testing Data Validator (CSV, JSON, Parquet, CRC32) ---"
if $CXX $CPP_FLAGS -Iservices/data-ingestion/src \
    services/data-ingestion/src/data_validator.cpp \
    services/data-ingestion/tests/test_validator.cpp \
    -o "$BUILD_TMP/test_validator"; then
    "$BUILD_TMP/test_validator"
    echo "[+] Data Validator suite passed!"
else
    echo "[-] Data Validator build failed!"
    FAILED=$((FAILED + 1))
fi

# 2. Preprocessor Tests
echo ""
echo "--- [2/5] Testing Preprocessor (MinMax, ZScore, Imputation) ---"
if $CXX $CPP_FLAGS -Iservices/preprocessing/src \
    services/preprocessing/src/preprocessor.cpp \
    services/preprocessing/tests/test_preprocessor.cpp \
    -o "$BUILD_TMP/test_preprocessor"; then
    "$BUILD_TMP/test_preprocessor"
    echo "[+] Preprocessor suite passed!"
else
    echo "[-] Preprocessor build failed!"
    FAILED=$((FAILED + 1))
fi

# 3. Feature Extractor Tests
echo ""
echo "--- [3/5] Testing Feature Extractor (Stats, OneHot, Hashing) ---"
if $CXX $CPP_FLAGS -Iservices/preprocessing/src \
    services/preprocessing/src/feature_extractor.cpp \
    services/preprocessing/tests/test_feature_extractor.cpp \
    -o "$BUILD_TMP/test_feature_extractor"; then
    "$BUILD_TMP/test_feature_extractor"
    echo "[+] Feature Extractor suite passed!"
else
    echo "[-] Feature Extractor build failed!"
    FAILED=$((FAILED + 1))
fi

# 4. Storage Shard Manager Tests
echo ""
echo "--- [4/5] Testing Shard Manager (Consistent Hash Virtual Nodes) ---"
if $CXX $CPP_FLAGS -Iservices/storage-manager/src \
    services/storage-manager/src/shard_manager.cpp \
    services/storage-manager/tests/test_shard.cpp \
    -o "$BUILD_TMP/test_shard"; then
    "$BUILD_TMP/test_shard"
    echo "[+] Shard Manager suite passed!"
else
    echo "[-] Shard Manager build failed!"
    FAILED=$((FAILED + 1))
fi

# 5. Storage Service Lifecycle Tests
echo ""
echo "--- [5/5] Testing Storage Service & Quorum Replication (W=2, N=3) ---"
if $CXX $CPP_FLAGS -Iservices/storage-manager/src \
    services/storage-manager/src/storage_service.cpp \
    services/storage-manager/src/shard_manager.cpp \
    services/storage-manager/src/replication.cpp \
    shared/cpp/src/metrics.cpp \
    services/storage-manager/tests/test_storage.cpp \
    -o "$BUILD_TMP/test_storage"; then
    "$BUILD_TMP/test_storage"
    echo "[+] Storage Service suite passed!"
else
    echo "[-] Storage Service build failed!"
    FAILED=$((FAILED + 1))
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo "=========================================================="
    echo "[+] ALL 16 C++17 DISTRIBUTED SYSTEM UNIT TESTS PASSED!"
    echo "=========================================================="
    exit 0
else
    echo "=========================================================="
    echo "[-] C++ unit test suites failed ($FAILED)."
    echo "=========================================================="
    exit 1
fi
