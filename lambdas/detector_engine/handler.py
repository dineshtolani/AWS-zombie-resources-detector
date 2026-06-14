"""
Lambda: Zombie Detection Engine
Runs per-type Isolation Forest models on collected metrics.
Loads/saves model artifacts from S3 for cross-week consistency.

Input:  { "resources": [{ "resource_id", "type", "source", "metrics": {...} }, ...] }
Output: { "results": [{ "resource_id", "type", "is_anomaly", "anomaly_score", "estimated_savings" }] }
"""
import json
import os
import tempfile

import boto3
import numpy as np
from sklearn.ensemble import IsolationForest

s3 = boto3.client("s3")
MODEL_BUCKET = os.environ.get("MODEL_BUCKET", "acheron-models")


# ----- Low-activity filters (one-tailed: only flag if metrics confirm idleness) -----

def _is_low_activity(rtype, metrics):
    """
    Post-filter: only flag as zombie if the resource actually shows near-zero activity.
    This fixes the one-tailed problem — Isolation Forest flags high-activity outliers too.
    """
    if rtype == "ec2":
        return metrics.get("cpu_avg", 100) < 5.0 and metrics.get("network_in", 1e9) < 5000
    elif rtype == "ebs":
        return (not metrics.get("attached", True)) or metrics.get("VolumeReadBytes", 1e9) < 5000
    elif rtype == "rds":
        return metrics.get("cpu_avg", 100) < 5.0 and metrics.get("db_connections", 100) < 5
    elif rtype == "nat":
        return metrics.get("BytesInFromDestination", 1e9) < 1_000_000
    elif rtype == "alb":
        return metrics.get("request_count", 1e9) < 50
    elif rtype == "efs":
        return metrics.get("burst_credit_balance", 100) < 20
    elif rtype == "eip":
        return metrics.get("TunnelDataIn", 1e9) < 1000
    elif rtype == "eks_cluster":
        return metrics.get("cluster_cpu_util", 100) < 5.0
    elif rtype == "eks_nodegroup":
        return metrics.get("node_cpu_util", 100) < 5.0
    elif rtype == "k8s_namespace":
        return metrics.get("running_pods", 100) < 2
    elif rtype == "k8s_pvc":
        return metrics.get("iops_read", 1e9) < 5 and not metrics.get("in_use", True)
    return True


# ----- Feature extractors (mirrors src/detectors/feature_extractors.py) -----

def _extract_ec2(r, m):
    return [r.get("monthly_cost", 0), m.get("cpu_avg", 0), m.get("network_in", 0), m.get("network_out", 0)]

def _extract_ebs(r, m):
    return [r.get("monthly_cost", 0), 0 if m.get("attached", True) else 1, m.get("VolumeReadBytes", 0), m.get("VolumeWriteBytes", 0)]

def _extract_rds(r, m):
    return [r.get("monthly_cost", 0), m.get("cpu_avg", 0), m.get("db_connections", 0), m.get("freeable_memory_bytes", 0)]

def _extract_nat(r, m):
    return [r.get("monthly_cost", 0), m.get("BytesInFromDestination", 0), m.get("BytesOutToDestination", 0), m.get("PacketsInFromDestination", 0)]

def _extract_alb(r, m):
    return [r.get("monthly_cost", 0), m.get("request_count", 0), m.get("active_connections", 0), m.get("new_connections", 0)]

def _extract_efs(r, m):
    return [r.get("monthly_cost", 0), m.get("burst_credit_balance", 0), m.get("DataReadIOBytes", 0), m.get("DataWriteIOBytes", 0)]

def _extract_eks_cluster(r, m):
    return [r.get("monthly_cost", 0), m.get("cluster_cpu_util", 0), m.get("cluster_mem_util", 0), m.get("node_count", 0)]

def _extract_eks_nodegroup(r, m):
    return [r.get("monthly_cost", 0), m.get("node_cpu_util", 0), m.get("node_cpu_util", 0), m.get("node_count", 0)]

def _extract_k8s_namespace(r, m):
    return [m.get("running_pods", 0), m.get("cpu_usage", 0), m.get("mem_usage_mb", 0), m.get("restart_count", 0)]

def _extract_k8s_pvc(r, m):
    return [r.get("monthly_cost", 0), m.get("storage_request_gb", 0), m.get("storage_used_gb", 0), m.get("iops_read", 0)]

EXTRACTORS = {
    "ec2": _extract_ec2, "ebs": _extract_ebs, "rds": _extract_rds,
    "nat": _extract_nat, "alb": _extract_alb, "efs": _extract_efs,
    "eks_cluster": _extract_eks_cluster, "eks_nodegroup": _extract_eks_nodegroup,
    "k8s_namespace": _extract_k8s_namespace, "k8s_pvc": _extract_k8s_pvc,
}


def load_model(rtype):
    key = f"models/{rtype}_isolation_forest.joblib"
    try:
        import joblib
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            s3.download_fileobj(MODEL_BUCKET, key, tmp)
            tmp_path = tmp.name
        model = joblib.load(tmp_path)
        os.unlink(tmp_path)
        return model
    except Exception:
        return None


def save_model(rtype, model):
    import joblib
    with tempfile.NamedTemporaryFile(delete=False, suffix=".joblib") as tmp:
        tmp_path = tmp.name
        joblib.dump(model, tmp_path)
    s3.upload_file(tmp_path, MODEL_BUCKET, f"models/{rtype}_isolation_forest.joblib")
    os.unlink(tmp_path)


def handler(event, context):
    resources = event.get("resources", [])
    contamination = float(os.environ.get("CONTAMINATION", "0.20"))

    # Group by type
    grouped = {}
    for r in resources:
        rtype = r.get("type")
        if rtype not in grouped:
            grouped[rtype] = []
        grouped[rtype].append(r)

    all_results = []

    for rtype, type_resources in grouped.items():
        extractor = EXTRACTORS.get(rtype)
        if not extractor:
            for r in type_resources:
                all_results.append({**r, "is_anomaly": False, "anomaly_score": 0.0, "estimated_savings": 0})
            continue

        vecs = []
        valid = []
        for r in type_resources:
            v = extractor(r, r.get("metrics", {}))
            if v:
                vecs.append(v)
                valid.append(r)

        if len(vecs) < 5:
            for r in valid:
                all_results.append({**r, "is_anomaly": False, "anomaly_score": 0.0, "estimated_savings": 0})
            continue

        X = np.array(vecs, dtype=np.float64)

        # Try loading existing model, else train new one
        model = load_model(rtype)
        if model is None:
            model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
            model.fit(X)
            save_model(rtype, model)

        preds = model.predict(X)
        scores = model.score_samples(X)

        s_min, s_max = scores.min(), scores.max()
        if s_max > s_min:
            normalized = 1 - (scores - s_min) / (s_max - s_min)
        else:
            normalized = np.zeros_like(scores)

        for i, r in enumerate(valid):
            is_anom = bool(preds[i] == -1)
            metrics = r.get("metrics", {})
            # One-tailed filter: only count as zombie if metrics confirm low activity
            is_zombie = is_anom and _is_low_activity(rtype, metrics)
            all_results.append({
                "resource_id": r["resource_id"],
                "type": rtype,
                "source": r.get("source", "aws"),
                "region": r.get("region", ""),
                "cluster": r.get("cluster", ""),
                "namespace": r.get("namespace", ""),
                "tags": r.get("tags", {}),
                "owner": r.get("tags", {}).get("Owner", ""),
                "monthly_cost": r.get("monthly_cost", 0),
                "is_anomaly": bool(preds[i] == -1),
                "is_zombie": is_zombie,
                "anomaly_score": round(normalized[i], 4),
                "estimated_savings": r.get("monthly_cost", 0) if is_zombie else 0,
            })

    zombies = [r for r in all_results if r.get("is_zombie")]
    return {
        "status": "ok",
        "results": all_results,
        "total_analyzed": len(resources),
        "anomalies_detected": sum(1 for r in all_results if r.get("is_anomaly")),
        "zombies_detected": len(zombies),
        "estimated_monthly_savings": round(sum(r.get("monthly_cost", 0) for r in zombies), 2),
    }
