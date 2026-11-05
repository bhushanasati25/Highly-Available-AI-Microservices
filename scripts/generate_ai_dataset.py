#!/usr/bin/env python3
"""
Synthetic AI Training Dataset Generator
Generates realistic multi-feature datasets in CSV, JSON, Parquet, and Binary formats
for testing ingestion pipelines, magic-byte validators, and drift detectors.
"""

import argparse
import csv
import json
import os
import random
import zlib
from pathlib import Path


def generate_datasets(num_rows: int = 1000, output_dir: str = "data_samples", inject_drift: bool = False):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"Generating synthetic AI training datasets ({num_rows} rows)...")
    mean_shift = 15.0 if inject_drift else 0.0

    # 1. Generate CSV
    csv_file = out_path / "synthetic_train_features.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "feature_embedding_1", "feature_embedding_2", "latency_ms", "label"])
        for i in range(num_rows):
            f1 = round(random.gauss(5.0 + mean_shift, 1.5), 4)
            f2 = round(random.gauss(10.0 + mean_shift, 2.5), 4)
            lat = round(random.uniform(1.2, 8.5), 2)
            label = 1 if (f1 + f2 > 16.0) else 0
            writer.writerow([f"s-{i:06d}", f1, f2, lat, label])
    print(f"[+] CSV dataset generated: {csv_file}")

    # 2. Generate JSON
    json_file = out_path / "synthetic_train_records.json"
    records = []
    for i in range(min(num_rows, 500)):
        records.append({
            "id": f"record-{i:05d}",
            "features": [
                round(random.gauss(1.0, 0.2), 4),
                round(random.gauss(2.5, 0.4), 4),
                round(random.gauss(7.8, 1.1), 4)
            ],
            "metadata": {
                "source": "iot-sensor-stream",
                "tier": "edge-accelerator",
                "timestamp": 1793910000 + i
            }
        })
    with open(json_file, "w") as f:
        json.dump(records, f, indent=2)
    print(f"[+] JSON dataset generated: {json_file}")

    # 3. Generate Mock Parquet with PAR1 Magic Bytes
    parquet_file = out_path / "synthetic_train_dataset.parquet"
    parquet_header = b"PAR1"
    parquet_footer = b"PAR1"
    body = b"\x00\x01\x02\x03\x04" * 100
    with open(parquet_file, "wb") as f:
        f.write(parquet_header + body + parquet_footer)
    print(f"[+] Parquet binary file with PAR1 magic bytes generated: {parquet_file}")

    # 4. Generate Binary Payload with CRC32 Checksum
    bin_file = out_path / "synthetic_binary_payload.bin"
    raw_payload = os.urandom(4096)
    crc = zlib.crc32(raw_payload)
    with open(bin_file, "wb") as f:
        f.write(raw_payload)

    checksum_file = out_path / "synthetic_binary_payload.bin.crc32"
    with open(checksum_file, "w") as f:
        f.write(f"{crc:#010x}\n")
    print(f"[+] Binary payload (4KB) with CRC32 ({crc:#010x}) generated: {bin_file}")

    print("[✓] All sample datasets created successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic AI Training Dataset Generator")
    parser.add_argument("--rows", type=int, default=1000, help="Number of samples to generate")
    parser.add_argument("--out", type=str, default="data_samples", help="Output directory")
    parser.add_argument("--drift", action="store_true", help="Inject significant distribution drift")
    args = parser.parse_args()

    generate_datasets(num_rows=args.rows, output_dir=args.out, inject_drift=args.drift)
