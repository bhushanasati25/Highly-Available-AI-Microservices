# Multi-stage build for Preprocessing Service
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

COPY proto/ /workspace/proto/
COPY shared/cpp/ /workspace/shared/cpp/
COPY services/preprocessing/ /workspace/services/preprocessing/

WORKDIR /workspace/services/preprocessing/build

RUN cmake -DCMAKE_BUILD_TYPE=Release .. && \
    cmake --build . --parallel $(nproc)

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

COPY --from=builder /workspace/services/preprocessing/build/preprocessing_service /app/preprocessing_service

EXPOSE 50052 8082 9092

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8082/health || exit 1

ENTRYPOINT ["/app/preprocessing_service"]
