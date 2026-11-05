#!/usr/bin/env python3
"""
HAMS CLI: Unified Command-Line Interface for Highly Available AI Microservices.
Manage cluster nodes, simulate hardware failures, orchestrate training jobs,
and view real-time telemetry.
"""

import argparse
import json
import sys
import os
import asyncio

# Setup module paths
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "shared/python"))
sys.path.insert(0, os.path.join(ROOT_DIR, "scheduler"))
sys.path.insert(0, os.path.join(ROOT_DIR, "services/training-orchestrator"))
sys.path.insert(0, os.path.join(ROOT_DIR, "services/model-manager"))
sys.path.insert(0, os.path.join(ROOT_DIR, "services/monitoring"))

from scheduler_app.node_manager import NodeManager
from scheduler_app.scheduler import WorkloadScheduler
from scheduler_app.failure_detector import FailureDetector
from model_app.registry import ModelRegistry
from orchestrator_app.orchestrator import TrainingOrchestrator

def format_table(rows, headers):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
            
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row)))

async def cmd_cluster_status(args):
    mgr = NodeManager(node_count=50)
    await mgr.initialize(50)
    nodes = list(mgr.nodes.values())
    
    total_cpu = sum(n.total_cpu for n in nodes)
    avail_cpu = sum(n.available_cpu for n in nodes)
    total_mem = sum(n.total_memory for n in nodes)
    avail_mem = sum(n.available_memory for n in nodes)
    total_gpu = sum(n.total_gpu for n in nodes)
    
    print("\n--- HAMS 50-NODE CLUSTER STATUS ---")
    print(f"Total Nodes:     {len(nodes)} (Active: {sum(1 for n in nodes if n.status == 'ACTIVE')})")
    print(f"CPU Utilization: {round((total_cpu - avail_cpu) / total_cpu * 100, 1)}% ({round(avail_cpu, 1)} / {total_cpu} Cores Available)")
    print(f"RAM Utilization: {round((total_mem - avail_mem) / total_mem * 100, 1)}% ({round(avail_mem, 1)} / {total_mem} GB Available)")
    print(f"GPU Capacity:    {total_gpu} Dedicated GPUs\n")

async def cmd_cluster_nodes(args):
    mgr = NodeManager(node_count=50)
    await mgr.initialize(50)
    limit = args.limit or 15
    nodes = list(mgr.nodes.values())[:limit]
    
    headers = ["Node ID", "Hostname", "Status", "CPU (Tot/Avail)", "RAM (GB)", "GPUs", "Tier"]
    rows = []
    for n in nodes:
        tier = n.labels.get("tier", "standard")
        rows.append([
            n.id,
            n.hostname,
            n.status.value,
            f"{n.total_cpu:.0f}/{n.available_cpu:.1f}",
            f"{n.total_memory:.0f}/{n.available_memory:.1f}",
            str(n.total_gpu),
            tier
        ])
    print(f"\nShowing first {len(rows)} nodes:")
    format_table(rows, headers)

async def cmd_simulate_failure(args):
    node_id = args.node_id
    mgr = NodeManager(node_count=50)
    await mgr.initialize(50)
    sched = WorkloadScheduler(mgr)
    detector = FailureDetector(mgr, sched)
    
    # Schedule a dummy job on this node first
    wkl = await sched.schedule("test-workload", 2.0, 8.0, 0, priority=8)
    # Force assign to requested node
    wkl.assigned_node = node_id
    mgr.nodes[node_id].workload_ids.append(wkl.id)
    
    print(f"\n[!] Simulating hardware failure on node: {node_id}")
    res = await detector.simulate_node_failure(node_id)
    print("[+] Node Status: Marked FAILED")
    print(f"[+] Affected Workloads: {res['orphaned_count']}")
    print(f"[+] Automated Rescheduled: {res['rescheduled_count']}")
    if res['rescheduled_ids']:
        new_node = sched.workloads[wkl.id].assigned_node
        print(f"[+] Workload {wkl.id} seamlessly migrated from {node_id} -> {new_node}\n")

async def cmd_model_list(args):
    reg = ModelRegistry()
    reg.register_model("resnet50-feature-extractor", "pytorch", "Vision backbone")
    reg.register_model("gpt2-text-generator", "transformers", "Language model")
    
    headers = ["Model ID", "Name", "Framework", "Version", "Description"]
    rows = []
    for m in reg.list_models():
        rows.append([m.id, m.name, m.framework, "v1.0.0", m.description])
    print("\n--- MODEL REGISTRY ---")
    format_table(rows, headers)

def main():
    parser = argparse.ArgumentParser(description="HAMS: Highly Available AI Microservices CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Cluster commands
    cluster_parser = subparsers.add_parser("cluster", help="Manage 50-node compute cluster")
    cluster_sub = cluster_parser.add_subparsers(dest="cluster_cmd", required=True)
    
    cluster_sub.add_parser("status", help="Get cluster status & capacity summary")
    
    nodes_p = cluster_sub.add_parser("nodes", help="List cluster compute nodes")
    nodes_p.add_argument("--limit", type=int, default=15, help="Limit number of nodes shown")
    
    fail_p = cluster_sub.add_parser("simulate-failure", help="Inject hardware failure on a node")
    fail_p.add_argument("node_id", help="Node ID (e.g. node-005)")
    
    # Model commands
    model_parser = subparsers.add_parser("model", help="Inspect model registry & versions")
    model_sub = model_parser.add_subparsers(dest="model_cmd", required=True)
    model_sub.add_parser("list", help="List registered AI models")
    
    args = parser.parse_args()
    
    if args.command == "cluster":
        if args.cluster_cmd == "status":
            asyncio.run(cmd_cluster_status(args))
        elif args.cluster_cmd == "nodes":
            asyncio.run(cmd_cluster_nodes(args))
        elif args.cluster_cmd == "simulate-failure":
            asyncio.run(cmd_simulate_failure(args))
    elif args.command == "model":
        if args.model_cmd == "list":
            asyncio.run(cmd_model_list(args))

if __name__ == "__main__":
    main()
