#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "HAMS: Running Comprehensive Automated Test Suites"
echo "=========================================================="

FAILED_SUITES=0

echo ""
echo "--- [1/3] Running Python Microservices & Rescheduler Tests ---"
if pytest scheduler/tests \
          services/api-gateway/tests \
          services/training-orchestrator/tests \
          services/model-manager/tests \
          services/monitoring/tests -v; then
    echo "[+] Python unit test suite passed!"
else
    echo "[-] Python unit tests encountered failures."
    FAILED_SUITES=$((FAILED_SUITES + 1))
fi

echo ""
echo "--- [2/3] Running End-to-End System Integration Tests ---"
if pytest tests/integration/test_end_to_end_pipeline.py -v; then
    echo "[+] System integration tests passed!"
else
    echo "[-] System integration tests encountered failures."
    FAILED_SUITES=$((FAILED_SUITES + 1))
fi

echo ""
echo "--- [3/3] Running Native C++17 Distributed Systems Tests ---"
if ./scripts/run_cpp_tests_native.sh; then
    echo "[+] Native C++17 test suite passed!"
else
    echo "[-] Native C++17 test suite encountered failures."
    FAILED_SUITES=$((FAILED_SUITES + 1))
fi

echo ""
if [ $FAILED_SUITES -eq 0 ]; then
    echo "=========================================================="
    echo "[+] ALL 38 AUTOMATED TEST SUITES PASSED FLAWLESSLY!"
    echo "=========================================================="
    exit 0
else
    echo "=========================================================="
    echo "[-] Some test suites failed ($FAILED_SUITES)."
    echo "=========================================================="
    exit 1
fi
