# Contributing to Highly Available AI Microservices (HAMS)

Thank you for your interest in contributing to HAMS! This document provides guidelines for contributing code, architecture enhancements, tests, and documentation.

---

## 1. Code of Conduct

All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to the project maintainers.

---

## 2. Development Setup

### Prerequisites
- Python 3.11+
- Clang++ (macOS) or GCC 9+ (Linux) with C++17 support
- Docker Engine 24+ & Docker Compose v2+
- Make, Curl

### Quickstart Setup
```bash
# Clone the repository
git clone https://github.com/bhushanasati25/Highly-Available-AI-Microservices.git
cd Highly-Available-AI-Microservices

# Run automated setup
./scripts/setup.sh

# Run the complete test suite to verify baseline
make test
```

---

## 3. Coding Guidelines

### C++17 Guidelines
- Follow the Google C++ Style Guide.
- Utilize modern C++17 idioms: `std::optional`, `std::variant`, `std::string_view`, structured bindings, and RAII.
- Format code using `clang-format` (`.clang-format` file provided in root).
- Ensure thread safety for all concurrent data structures using `std::mutex` or `std::shared_mutex`.
- No raw `new`/`delete`; use smart pointers (`std::unique_ptr`, `std::shared_ptr`).

### Python Guidelines
- Adhere to PEP 8. Format and lint with `ruff`:
  ```bash
  ruff check .
  ```
- Type annotations are mandatory on all public function signatures.
- Prefer asynchronous I/O (`async`/`await`) for I/O-bound microservices (FastAPI, httpx).
- Pydantic models must use OpenAPI 3.1 compliant `examples=[...]`.

---

## 4. Testing Requirements

Every pull request must include tests for new functionality:
```bash
# 1. Run all 38 test suites
make test

# 2. Run native C++ unit tests
make test-cpp

# 3. Run Python unit & integration tests
make test-python

# 4. Verify end-to-end pipeline & failover
make demo
```

---

## 5. Submitting a Pull Request

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Implement your changes with clear, semantic commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
3. Verify that all tests pass (`make test`).
4. Push your branch to GitHub and open a Pull Request using the provided PR template.
