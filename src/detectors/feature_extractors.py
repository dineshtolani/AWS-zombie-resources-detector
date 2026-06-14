from src.core.registry import register_extractor


@register_extractor("ec2")
def ec2_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["cpu_avg"], m["cpu_max"],
        m["network_in_bytes"], m["network_out_bytes"],
        m["io_read_bytes"], m["io_write_bytes"], m["io_ops"],
    ]


@register_extractor("ebs")
def ebs_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        1 if m.get("attached", True) else 0,
        m.get("volume_size_gb", 0),
        m["io_read_bytes"], m["io_write_bytes"], m["io_ops"],
        m.get("snapshot_count", 0),
    ]


@register_extractor("rds")
def rds_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["cpu_avg"], m["cpu_max"],
        m["network_in_bytes"], m["network_out_bytes"],
        m["db_connections"], m["read_latency"], m["write_latency"],
        m["io_read_bytes"], m["io_write_bytes"], m["io_ops"],
        m.get("freeable_memory_bytes", 0),
    ]


@register_extractor("nat")
def nat_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["bytes_in"], m["bytes_out"],
        m["packets_in"], m["packets_out"],
    ]


@register_extractor("alb")
def alb_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["request_count"], m["active_connections"], m["new_connections"],
        m["network_in_bytes"], m["network_out_bytes"],
    ]


@register_extractor("efs")
def efs_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["burst_credit_balance"],
        m["data_read_io"], m["data_write_io"],
        m["io_read_bytes"], m["io_write_bytes"],
    ]


@register_extractor("eip")
def eip_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["inbound_bytes"], m["outbound_bytes"],
    ]


@register_extractor("eks_cluster")
def eks_cluster_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["node_count"], m["total_pod_capacity"], m["allocated_pods"],
        m["cluster_cpu_util"], m["cluster_mem_util"],
        m["unschedulable_pods"],
    ]


@register_extractor("eks_nodegroup")
def eks_nodegroup_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["node_count"], m["node_cpu_util"], m["node_mem_util"],
        m["pod_count"], m["container_restarts"],
        m["avg_node_disk_util"],
        m["network_rx_bytes"], m["network_tx_bytes"],
    ]


@register_extractor("k8s_namespace")
def k8s_ns_features(r, m):
    return [
        r["age_days"],
        m["running_pods"], m["cpu_request"], m["cpu_usage"],
        m["mem_request_mb"], m["mem_usage_mb"],
        m["restart_count"], m["oom_count"],
    ]


@register_extractor("k8s_pvc")
def k8s_pvc_features(r, m):
    return [
        r["age_days"], r["monthly_cost"],
        m["storage_request_gb"], m["storage_used_gb"],
        m["iops_read"], m["iops_write"],
        m["read_bytes"], m["write_bytes"],
        1 if m.get("in_use", True) else 0,
    ]
