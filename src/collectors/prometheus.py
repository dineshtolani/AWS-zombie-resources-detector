import copy
from src.core.resource_generator import generate_resources
from src.core.metrics_generator import generate_k8s_metrics


class PrometheusCollector:
    """
    Simulates scraping Prometheus/AMP metrics for K8s resources.
    Uses a fixed resource pool — only metrics vary week-to-week.
    """

    def __init__(self):
        self._pool = None

    def _get_pool(self, count, seed):
        if self._pool is None:
            self._pool = [r for r in generate_resources(n_aws=0, n_k8s=count, seed=seed) if r["source"] == "k8s"]
        return self._pool

    def collect(self, resource_count=80, seed=42, week_offset=0):
        pool = self._get_pool(resource_count, 42)
        pairs = []
        for i, r in enumerate(pool):
            r_copy = copy.deepcopy(r)
            m = generate_k8s_metrics(r_copy, seed=seed + week_offset + i + 1000)
            pairs.append((r_copy, m))
        return pairs
