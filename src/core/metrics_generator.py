import hashlib
import random


def _is_zombie_per_resource(resource, idle_probability=0.20):
    """Stable per-resource zombie classification (same resource = same zombie status every week)."""
    h = int(hashlib.sha256(resource["resource_id"].encode()).hexdigest(), 16)
    return (h % 1000) / 1000 < idle_probability


def generate_aws_metrics(resource, idle_probability=0.20, seed=None):
    rtype = resource["type"]
    is_zombie = _is_zombie_per_resource(resource, idle_probability)
    if seed is not None:
        random.seed(seed + (0 if not is_zombie else 100000))

    if is_zombie:
        m = {
            "cpu_avg": round(random.uniform(0.0, 2.0), 2),
            "cpu_max": round(random.uniform(0.5, 5.0), 2),
            "network_in_bytes": round(random.uniform(0, 1_000), 2),
            "network_out_bytes": round(random.uniform(0, 500), 2),
            "io_read_bytes": round(random.uniform(0, 1_000), 2),
            "io_write_bytes": round(random.uniform(0, 500), 2),
            "io_ops": round(random.uniform(0, 5), 2),
        }
        if rtype == "nat":
            m.update({
                "bytes_in": round(random.uniform(0, 1_000_000), 2),
                "bytes_out": round(random.uniform(0, 500_000), 2),
                "packets_in": round(random.uniform(0, 100), 2),
                "packets_out": round(random.uniform(0, 50), 2),
            })
        elif rtype == "alb":
            m.update({
                "request_count": round(random.uniform(0, 10), 2),
                "active_connections": round(random.uniform(0, 3), 2),
                "new_connections": round(random.uniform(0, 2), 2),
            })
        elif rtype == "rds":
            m.update({
                "db_connections": round(random.uniform(0, 5), 2),
                "read_latency": round(random.uniform(0, 0.1), 4),
                "write_latency": round(random.uniform(0, 0.1), 4),
                "freeable_memory_bytes": round(random.uniform(500_000_000, 2_000_000_000), 2),
            })
        elif rtype == "efs":
            m.update({
                "burst_credit_balance": round(random.uniform(0, 5), 2),
                "data_read_io": round(random.uniform(0, 1_000), 2),
                "data_write_io": round(random.uniform(0, 500), 2),
            })
        elif rtype == "eip":
            m.update({
                "inbound_bytes": round(random.uniform(0, 100), 2),
                "outbound_bytes": round(random.uniform(0, 50), 2),
            })
        elif rtype == "ebs":
            m["attached"] = False
            m["volume_size_gb"] = resource.get("age_days", 30) % 100 + 1
            m["snapshot_count"] = 0
    else:
        m = {
            "cpu_avg": round(random.uniform(15, 85), 2),
            "cpu_max": round(random.uniform(40, 98), 2),
            "network_in_bytes": round(random.uniform(10_000, 5_000_000), 2),
            "network_out_bytes": round(random.uniform(5_000, 2_000_000), 2),
            "io_read_bytes": round(random.uniform(10_000, 10_000_000), 2),
            "io_write_bytes": round(random.uniform(5_000, 5_000_000), 2),
            "io_ops": round(random.uniform(50, 5_000), 2),
        }
        if rtype == "nat":
            m.update({
                "bytes_in": round(random.uniform(10_000_000, 500_000_000), 2),
                "bytes_out": round(random.uniform(5_000_000, 200_000_000), 2),
                "packets_in": round(random.uniform(1_000, 50_000), 2),
                "packets_out": round(random.uniform(500, 25_000), 2),
            })
        elif rtype == "alb":
            m.update({
                "request_count": round(random.uniform(100, 50_000), 2),
                "active_connections": round(random.uniform(10, 2_000), 2),
                "new_connections": round(random.uniform(5, 500), 2),
            })
        elif rtype == "rds":
            m.update({
                "db_connections": round(random.uniform(10, 200), 2),
                "read_latency": round(random.uniform(0.001, 0.05), 4),
                "write_latency": round(random.uniform(0.001, 0.05), 4),
                "freeable_memory_bytes": round(random.uniform(100_000_000, 500_000_000), 2),
            })
        elif rtype == "efs":
            m.update({
                "burst_credit_balance": round(random.uniform(50, 100), 2),
                "data_read_io": round(random.uniform(100_000, 10_000_000), 2),
                "data_write_io": round(random.uniform(50_000, 5_000_000), 2),
            })
        elif rtype == "eip":
            m.update({
                "inbound_bytes": round(random.uniform(10_000, 1_000_000), 2),
                "outbound_bytes": round(random.uniform(5_000, 500_000), 2),
            })
        elif rtype == "ebs":
            m["attached"] = True
            m["volume_size_gb"] = resource.get("age_days", 30) % 100 + 1
            m["snapshot_count"] = random.randint(1, 10)

    m["_is_zombie_ground_truth"] = is_zombie
    return m


def generate_k8s_metrics(resource, idle_probability=0.20, seed=None):
    rtype = resource["type"]
    is_zombie = _is_zombie_per_resource(resource, idle_probability)
    if seed is not None:
        random.seed(seed + (0 if not is_zombie else 100000))

    cluster = resource.get("cluster", "eks-unknown")
    base = {
        "cluster": cluster,
        "source": "prometheus",
    }

    if rtype == "eks_cluster":
        if is_zombie:
            base.update({
                "node_count": random.randint(0, 2),
                "total_pod_capacity": random.randint(0, 20),
                "allocated_pods": random.randint(0, 3),
                "cluster_cpu_util": round(random.uniform(0, 3), 2),
                "cluster_mem_util": round(random.uniform(0, 5), 2),
                "unschedulable_pods": random.randint(5, 20),
            })
        else:
            base.update({
                "node_count": random.randint(5, 20),
                "total_pod_capacity": random.randint(60, 300),
                "allocated_pods": random.randint(40, 280),
                "cluster_cpu_util": round(random.uniform(35, 80), 2),
                "cluster_mem_util": round(random.uniform(40, 85), 2),
                "unschedulable_pods": random.randint(0, 3),
            })

    elif rtype == "eks_nodegroup":
        node_count = resource.get("desired_size", 3)
        if is_zombie:
            base.update({
                "node_count": node_count,
                "node_cpu_util": round(random.uniform(0, 3), 2),
                "node_mem_util": round(random.uniform(0, 5), 2),
                "pod_count": round(random.uniform(0, node_count)),  # less than node count
                "container_restarts": round(random.uniform(5, 30), 2),
                "avg_node_disk_util": round(random.uniform(10, 30), 2),
                "network_rx_bytes": round(random.uniform(0, 100_000), 2),
                "network_tx_bytes": round(random.uniform(0, 50_000), 2),
            })
        else:
            base.update({
                "node_count": node_count,
                "node_cpu_util": round(random.uniform(30, 85), 2),
                "node_mem_util": round(random.uniform(40, 90), 2),
                "pod_count": round(random.uniform(node_count * 5, node_count * 15)),
                "container_restarts": round(random.uniform(0, 3), 2),
                "avg_node_disk_util": round(random.uniform(40, 80), 2),
                "network_rx_bytes": round(random.uniform(1_000_000, 100_000_000), 2),
                "network_tx_bytes": round(random.uniform(500_000, 50_000_000), 2),
            })

    elif rtype == "k8s_namespace":
        if is_zombie:
            base.update({
                "running_pods": round(random.uniform(0, 1)),
                "cpu_request": random.randint(0, 100),
                "cpu_usage": random.randint(0, 10),
                "mem_request_mb": random.randint(0, 256),
                "mem_usage_mb": random.randint(0, 32),
                "restart_count": round(random.uniform(10, 50), 2),
                "oom_count": round(random.uniform(3, 15), 2),
            })
        else:
            base.update({
                "running_pods": round(random.uniform(5, 50)),
                "cpu_request": random.randint(500, 5000),
                "cpu_usage": random.randint(300, 4000),
                "mem_request_mb": random.randint(1024, 16384),
                "mem_usage_mb": random.randint(512, 12288),
                "restart_count": round(random.uniform(0, 5), 2),
                "oom_count": round(random.uniform(0, 1), 2),
            })

    elif rtype == "k8s_pvc":
        if is_zombie:
            base.update({
                "storage_request_gb": resource.get("storage_gb", 10),
                "storage_used_gb": round(random.uniform(0, 0.5), 2),
                "iops_read": round(random.uniform(0, 1), 2),
                "iops_write": round(random.uniform(0, 1), 2),
                "read_bytes": round(random.uniform(0, 100), 2),
                "write_bytes": round(random.uniform(0, 50), 2),
                "in_use": False,
            })
        else:
            base.update({
                "storage_request_gb": resource.get("storage_gb", 10),
                "storage_used_gb": round(random.uniform(3, resource.get("storage_gb", 10) * 0.8), 2),
                "iops_read": round(random.uniform(50, 5000), 2),
                "iops_write": round(random.uniform(20, 2000), 2),
                "read_bytes": round(random.uniform(10_000, 10_000_000), 2),
                "write_bytes": round(random.uniform(5_000, 5_000_000), 2),
                "in_use": True,
            })

    base["_is_zombie_ground_truth"] = is_zombie
    return base
