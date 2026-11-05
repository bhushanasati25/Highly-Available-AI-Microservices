#!/usr/bin/env python3
"""
Generate realistic synthetic datasets (CSV, JSON, Binary) for testing
the HAMS data ingestion, preprocessing, and training pipeline.
"""

import os
import json
import random
import struct

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data_samples"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_csv_dataset(filename="train_features.csv", num_rows=1000):
    filepath = os.path.join(OUTPUT_DIR, filename)
    headers = ["id", "feat_embedding_norm", "feat_latency_p99", "feat_throughput_qps", "feat_error_rate", "label"]
    
    with open(filepath, "w") as f:
        f.write(",".join(headers) + "\n")
        for i in range(1, num_rows + 1):
            emb = round(random.gauss(0.5, 0.15), 4)
            lat = round(random.uniform(5.0, 120.0), 2)
            tps = round(random.uniform(100.0, 5000.0), 1)
            err = round(random.expovariate(100.0), 5)
            label = 1 if (lat > 50.0 or err > 0.05) else 0
            row = [str(i), str(emb), str(lat), str(tps), str(err), str(label)]
            f.write(",".join(row) + "\n")
            
    print(f"[+] Generated CSV dataset with {num_rows} records at: {filepath}")
    return filepath

def generate_json_dataset(filename="telemetry_logs.json", num_records=200):
    filepath = os.path.join(OUTPUT_DIR, filename)
    records = []
    
    for i in range(1, num_records + 1):
        record = {
            "node_id": f"worker-node-{random.randint(1, 50):02d}",
            "sequence": i,
            "metrics": {
                "cpu_load": round(random.uniform(10.0, 95.0), 1),
                "memory_gb": round(random.uniform(4.0, 64.0), 2),
                "gpu_temp_c": random.randint(45, 82),
            },
            "status": "HEALTHY" if random.random() > 0.05 else "DEGRADED"
        }
        records.append(record)
        
    with open(filepath, "w") as f:
        json.dump(records, f, indent=2)
        
    print(f"[+] Generated JSON dataset with {num_records} records at: {filepath}")
    return filepath

def generate_binary_tensor(filename="weights_tensor.bin", num_floats=1024):
    filepath = os.path.join(OUTPUT_DIR, filename)
    data = [random.gauss(0.0, 1.0) for _ in range(num_floats)]
    
    with open(filepath, "wb") as f:
        # Pack as 32-bit floats
        packed = struct.pack(f"{num_floats}f", *data)
        f.write(packed)
        
    print(f"[+] Generated Binary Float32 tensor ({num_floats} elements, {len(packed)} bytes) at: {filepath}")
    return filepath

if __name__ == "__main__":
    print("Generating HAMS synthetic test datasets...")
    generate_csv_dataset()
    generate_json_dataset()
    generate_binary_tensor()
    print("Dataset generation completed.")
