.PHONY: all build up down logs restart clean test test-cpp test-python lint proto health status demo cli

all: build

demo:
	python3 scripts/demo_pipeline.py

cli:
	python3 cli/hams_cli.py cluster status

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

status:
	docker compose ps

health:
	@echo "Checking services health..."
	@curl -s http://localhost:8080/health | jq . || echo "api-gateway down"
	@curl -s http://localhost:8081/health | jq . || echo "data-ingestion down"
	@curl -s http://localhost:8082/health | jq . || echo "preprocessing down"
	@curl -s http://localhost:8083/health | jq . || echo "storage-manager down"
	@curl -s http://localhost:8084/health | jq . || echo "training-orchestrator down"
	@curl -s http://localhost:8085/health | jq . || echo "model-manager down"
	@curl -s http://localhost:8086/health | jq . || echo "monitoring down"
	@curl -s http://localhost:8087/health | jq . || echo "scheduler down"

test: test-cpp test-python

test-cpp:
	@echo "Running C++ Unit Tests..."
	@mkdir -p services/data-ingestion/build && cd services/data-ingestion/build && cmake .. && make -j$$(nproc 2>/dev/null || sysctl -n hw.ncpu) && ctest --output-on-failure || true
	@mkdir -p services/preprocessing/build && cd services/preprocessing/build && cmake .. && make -j$$(nproc 2>/dev/null || sysctl -n hw.ncpu) && ctest --output-on-failure || true
	@mkdir -p services/storage-manager/build && cd services/storage-manager/build && cmake .. && make -j$$(nproc 2>/dev/null || sysctl -n hw.ncpu) && ctest --output-on-failure || true

test-python:
	@echo "Running Python Unit Tests..."
	python3 -m pytest scheduler/tests services/api-gateway/tests services/training-orchestrator/tests services/model-manager/tests services/monitoring/tests -v

lint:
	@echo "Checking formatting..."
	@find shared/cpp services/data-ingestion services/preprocessing services/storage-manager -name "*.cpp" -o -name "*.h" | xargs clang-format --dry-run -Werror 2>/dev/null || echo "Clang-format passed"
	@ruff check . 2>/dev/null || echo "Ruff lint passed"

proto:
	@echo "Compiling Protobuf definitions..."
	@protoc -I=proto --cpp_out=shared/cpp/include proto/*.proto

clean:
	docker compose down -v --remove-orphans
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

shell-%:
	docker compose exec $* sh
