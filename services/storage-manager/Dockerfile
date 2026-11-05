# Multi-stage build for Storage Manager Service
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ca-certificates \
    libspdlog-dev \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY shared/cpp/ /workspace/shared/cpp/
COPY services/storage-manager/ /workspace/services/storage-manager/

WORKDIR /workspace/services/storage-manager/build

RUN cmake -DCMAKE_BUILD_TYPE=Release .. && \
    cmake --build . --parallel $(nproc)

FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libspdlog1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /workspace/services/storage-manager/build/storage_manager_service /app/storage_manager_service

EXPOSE 50053 8083 9093

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8083/health || exit 1

ENTRYPOINT ["/app/storage_manager_service"]
