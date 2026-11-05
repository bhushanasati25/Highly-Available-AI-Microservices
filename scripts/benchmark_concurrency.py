#!/usr/bin/env python3
"""
High-Throughput Concurrency & Stress Benchmark
Simulates high-load concurrent AI training data pipeline backend architecture requests.
Measures latency percentiles (min, p50, p95, p99, max) and throughput (req/sec).
"""

import asyncio
import time
import statistics
import sys
from pathlib import Path

# Add shared paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "shared" / "python"))
sys.path.insert(0, str(BASE_DIR / "scheduler"))
sys.path.insert(0, str(BASE_DIR / "services" / "training-orchestrator"))
sys.path.insert(0, str(BASE_DIR / "services" / "model-manager"))

from scheduler_app.node_manager import NodeManager
from scheduler_app.scheduler import WorkloadScheduler, SchedulingAlgorithm
from orchestrator_app.orchestrator import orchestrator_instance
from model_app.registry import registry_instance


async def simulate_pipeline_transaction(
    tx_id: int,
    scheduler: WorkloadScheduler,
    latencies: list
):
    start = time.perf_counter()
    try:
        # 1. Schedule distributed data pipeline workload
        wkl = await scheduler.schedule(
            name=f"concurrent-pipeline-tx-{tx_id:04d}",
            required_cpu=2.0,
            required_memory=4.0,
            required_gpu=0,
            required_disk=10.0,
            priority=(tx_id % 10) + 1,
            algorithm=SchedulingAlgorithm.LEAST_LOADED,
        )

        # 2. Submit concurrent training job
        job = await orchestrator_instance.submit_job(
            model_type="transformer-fast-inference",
            dataset_id=f"batch-chunk-{tx_id % 5}",
            hyperparameters={"batch_size": 64},
            priority=(tx_id % 10) + 1,
            req_gpu=0,
            req_cpu=2.0,
            req_mem=4.0,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(elapsed_ms)
        return True
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(elapsed_ms)
        return False


async def run_benchmark(concurrency: int = 100):
    print("=" * 65)
    print("HAMS: Distributed AI Pipeline Concurrency Benchmark")
    print(f"Target Concurrency: {concurrency} simultaneous pipeline transactions")
    print("=" * 65)

    # Initialize 50-node cluster
    node_mgr = NodeManager(node_count=50)
    await node_mgr.initialize(50)
    scheduler = WorkloadScheduler(node_mgr)

    latencies = []
    wall_start = time.perf_counter()

    tasks = [
        simulate_pipeline_transaction(i, scheduler, latencies)
        for i in range(concurrency)
    ]
    results = await asyncio.gather(*tasks)

    total_duration = time.perf_counter() - wall_start
    success_count = sum(1 for r in results if r)
    failure_count = len(results) - success_count
    throughput = len(results) / total_duration

    sorted_lats = sorted(latencies)
    p50 = statistics.median(sorted_lats)
    p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
    p99 = sorted_lats[int(len(sorted_lats) * 0.99)]
    min_lat = sorted_lats[0]
    max_lat = sorted_lats[-1]
    mean_lat = statistics.mean(sorted_lats)

    print("\nBenchmark Execution Results:")
    print("-" * 65)
    print(f"Total Transactions Completed : {len(results)}")
    print(f"Successful Transactions      : {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"Failed Transactions          : {failure_count}")
    print(f"Total Wall Clock Duration    : {total_duration:.3f} seconds")
    print(f"Effective Throughput         : {throughput:.1f} req/sec")
    print("-" * 65)
    print("Latency Distribution (ms):")
    print(f"  Min   : {min_lat:8.2f} ms")
    print(f"  Mean  : {mean_lat:8.2f} ms")
    print(f"  P50   : {p50:8.2f} ms")
    print(f"  P95   : {p95:8.2f} ms")
    print(f"  P99   : {p99:8.2f} ms")
    print(f"  Max   : {max_lat:8.2f} ms")
    print("=" * 65)
    print("[+] Concurrency benchmark completed successfully!")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    asyncio.run(run_benchmark(count))
