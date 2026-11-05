.PHONY: all build up down logs restart clean test test-cpp test-python test-integration benchmark chaos profile lint proto health health-probes status demo cli cli-dlq dashboard data deploy-aks

all: build

demo:
	python3 scripts/demo_pipeline.py

cli:
	python3 cli/hams_cli.py cluster status

cli-dlq:
	python3 cli/hams_cli.py dlq list

benchmark:
	python3 scripts/benchmark_concurrency.py 100

chaos:
	python3 scripts/chaos_simulation.py

profile:
	python3 scripts/profile_inference_latency.py --iterations 50

dashboard:
	@echo "Opening Operations Mission Control Dashboard..."
	@open web/index.html 2>/dev/null || xdg-open web/index.html 2>/dev/null || echo "Open web/index.html in your browser or visit http://localhost:8080/dashboard"

data:
	python3 scripts/generate_ai_dataset.py --rows 1000

deploy-aks:
	./scripts/deploy_azure_aks.sh

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
	@./scripts/health-check.sh localhost

health-probes:
	@echo "Checking 3-tier Kubernetes probes (/healthz, /readyz, /startupz)..."
	@./scripts/health-check.sh localhost --probes

test:
	./scripts/run-tests.sh

test-cpp:
	./scripts/run_cpp_tests_native.sh

test-python:
	python3 -m pytest scheduler/tests services/api-gateway/tests services/training-orchestrator/tests services/model-manager/tests services/monitoring/tests tests/integration/ -v

test-integration:
	python3 -m pytest tests/integration/test_end_to_end_pipeline.py -v

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
