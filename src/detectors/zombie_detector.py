import numpy as np
from collections import defaultdict
from sklearn.ensemble import IsolationForest
import src.detectors.feature_extractors  # noqa: F401 — registers extractors via decorator
from src.core.registry import get_extractor


def is_low_activity(rtype, metrics):
    """One-tailed post-filter: only count as zombie if metrics confirm idleness."""
    if rtype == "ec2":
        return metrics.get("cpu_avg", 100) < 5.0 and metrics.get("network_in_bytes", 1e9) < 5000
    elif rtype == "ebs":
        return not metrics.get("attached", True)
    elif rtype == "rds":
        return metrics.get("cpu_avg", 100) < 5.0 and metrics.get("db_connections", 100) < 5
    elif rtype == "nat":
        return metrics.get("bytes_in", 1e9) < 1_000_000
    elif rtype == "alb":
        return metrics.get("request_count", 1e9) < 50
    elif rtype == "efs":
        return metrics.get("burst_credit_balance", 100) < 20
    elif rtype == "eip":
        return metrics.get("inbound_bytes", 1e9) < 1000
    elif rtype == "eks_cluster":
        return metrics.get("cluster_cpu_util", 100) < 5.0
    elif rtype == "eks_nodegroup":
        return metrics.get("node_cpu_util", 100) < 5.0
    elif rtype == "k8s_namespace":
        return metrics.get("running_pods", 100) < 2
    elif rtype == "k8s_pvc":
        return metrics.get("iops_read", 1e9) < 5 and not metrics.get("in_use", True)
    return True


def extract(r, m):
    fn = get_extractor(r["type"])
    if fn is None:
        return None
    return np.array(fn(r, m), dtype=np.float64)


def pad_to_max(vectors):
    max_len = max(len(v) for v in vectors)
    padded = []
    for v in vectors:
        if len(v) < max_len:
            v = np.pad(v, (0, max_len - len(v)), constant_values=0)
        padded.append(v)
    return np.array(padded)


def detect_per_type(pairs, contamination=0.20, random_state=42):
    """
    Train a separate Isolation Forest per resource type.
    Much more accurate than a single global model because each type
    has its own feature space and activity baselines.
    """
    grouped = defaultdict(list)
    for r, m in pairs:
        grouped[r["type"]].append((r, m))

    all_results = []
    models = {}

    for rtype, type_pairs in grouped.items():
        vecs = []
        for r, m in type_pairs:
            v = extract(r, m)
            if v is not None:
                vecs.append(v)

        if len(vecs) < 3:
            for r, m in type_pairs:
                all_results.append({
                    "resource": r, "metrics": m,
                    "is_anomaly": False, "anomaly_score": 0.0,
                    "true_zombie": m.get("_is_zombie_ground_truth", False),
                    "estimated_savings": 0,
                })
            continue

        X = pad_to_max(vecs)
        model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100,
        )
        preds = model.fit_predict(X)
        scores = model.score_samples(X)
        models[rtype] = model

        s_min, s_max = scores.min(), scores.max()
        if s_max > s_min:
            normalized = 1 - (scores - s_min) / (s_max - s_min)
        else:
            normalized = np.zeros_like(scores)

        for j, (r, m) in enumerate(type_pairs):
            is_anom = preds[j] == -1
            is_zombie = is_anom and is_low_activity(r["type"], m)
            score = round(normalized[j], 4)
            all_results.append({
                "resource": r,
                "metrics": m,
                "is_anomaly": bool(is_anom),
                "is_zombie": is_zombie,
                "anomaly_score": score,
                "true_zombie": m.get("_is_zombie_ground_truth", False),
                "estimated_savings": r["monthly_cost"] if is_zombie else 0,
            })

    return all_results, models


def analyze_by_source(results):
    aws = [r for r in results if r["resource"]["source"] == "aws"]
    k8s = [r for r in results if r["resource"]["source"] == "k8s"]
    return {
        "aws": {
            "total": len(aws),
            "anomalous": sum(1 for r in aws if r.get("is_zombie")),
            "savings": sum(r["estimated_savings"] for r in aws),
        },
        "k8s": {
            "total": len(k8s),
            "anomalous": sum(1 for r in k8s if r.get("is_zombie")),
            "savings": sum(r["estimated_savings"] for r in k8s),
        },
    }


def print_detection_summary(results):
    zombies = [r for r in results if r.get("is_zombie")]
    total_savings = sum(r["estimated_savings"] for r in zombies)
    tp = sum(1 for r in zombies if r["true_zombie"])
    fp = sum(1 for r in zombies if not r["true_zombie"])
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + sum(1 for r in results if r["true_zombie"])) if tp > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    by_source = analyze_by_source(results)

    print(f"\n{'='*60}")
    print(f"  ZOMBIE DETECTION RESULTS (one-tailed filter applied)")
    print(f"{'='*60}")
    print(f"  Analyzed  : {len(results)} resources ({by_source['aws']['total']} AWS, {by_source['k8s']['total']} K8s)")
    print(f"  Zombies   : {len(zombies)} ({by_source['aws']['anomalous']} AWS, {by_source['k8s']['anomalous']} K8s)")
    print(f"  Savings   : ${total_savings:.2f}/month")
    print(f"  Precision : {precision:.1%}")
    print(f"  Recall    : {recall:.1%}")
    print(f"  F1 Score  : {f1:.1%}")

    if zombies:
        print(f"\n  Top Zombie Resources:")
        print(f"  {'Resource ID':<38} {'Type':<14} {'Source':<6} {'Score':<8} {'Savings':<10}")
        print(f"  {'-'*76}")
        for r in sorted(zombies, key=lambda x: x["anomaly_score"], reverse=True)[:10]:
            rid = r["resource"]["resource_id"][:36]
            rtype = r["resource"]["type"]
            src = r["resource"]["source"]
            sc = r["anomaly_score"]
            sv = r["estimated_savings"]
            owner = r["resource"].get("tags", {}).get("Owner", "-")
            print(f"  {rid:<38} {rtype:<14} {src:<6} {sc:<8.4f} ${sv:<8.2f}  ({owner})")
    print(f"{'='*60}\n")
