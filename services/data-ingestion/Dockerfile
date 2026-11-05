# Multi-stage build for Data Ingestion Service
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ca-certificates \
    libprotobuf-dev \
    protobuf-compiler \
    libgrpc++-dev \
    protobuf-compiler-grpc \
    libspdlog-dev \
    nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy source tree
COPY proto/ /workspace/proto/
COPY shared/cpp/ /workspace/shared/cpp/
COPY services/data-ingestion/ /workspace/services/data-ingestion/

WORKDIR /workspace/services/data-ingestion/build

RUN cmake -DCMAKE_BUILD_TYPE=Release .. && \
    cmake --build . --parallel $(nproc)

# Runtime image
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libprotobuf23 \
    libgrpc++1 \
    libspdlog1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /workspace/services/data-ingestion/build/data_ingestion_service /app/data_ingestion_service

EXPOSE 50051 8081 9091

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8081/health || exit 1

ENTRYPOINT ["/app/data_ingestion_service"]
