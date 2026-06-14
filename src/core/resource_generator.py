import random
import uuid
from src.core.registry import (
    RESOURCE_TYPES_AWS, RESOURCE_TYPES_K8S, RESOURCE_TYPES,
    REGIONS_AWS, COST_RANGES, AGE_RANGES, ENVIRONMENTS, TEAMS,
)

def generate_resources(n_aws=120, n_k8s=80, seed=42):
    random.seed(seed)
    resources = []

    # AWS resources
    for _ in range(n_aws):
        rtype = random.choice(RESOURCE_TYPES_AWS)
        cost_min, cost_max = COST_RANGES[rtype]
        age_min, age_max = AGE_RANGES[rtype]
        resource = {
            "resource_id": str(uuid.uuid4()),
            "type": rtype,
            "source": "aws",
            "region": random.choice(REGIONS_AWS),
            "age_days": random.randint(age_min, age_max),
            "monthly_cost": round(random.uniform(cost_min, cost_max), 2),
            "tags": {
                "Name": f"{rtype}-{random.randint(1000,9999)}",
                "Environment": random.choice(ENVIRONMENTS),
            },
        }
        if random.random() > 0.3:
            resource["tags"]["Owner"] = random.choice(TEAMS)
        resources.append(resource)

    # K8s resources
    cluster_names = [f"eks-prod-{i}" for i in range(1, 4)]
    for _ in range(n_k8s):
        rtype = random.choice(RESOURCE_TYPES_K8S)
        cost_min, cost_max = COST_RANGES[rtype]
        age_min, age_max = AGE_RANGES[rtype]
        cluster = random.choice(cluster_names)
        ns = random.choice(["default", "kube-system", "monitoring", "payments", "auth", "data-pipeline", "ml-workloads"])

        resource = {
            "resource_id": str(uuid.uuid4()),
            "type": rtype,
            "source": "k8s",
            "cluster": cluster,
            "region": random.choice(REGIONS_AWS),
            "namespace": ns if rtype != "eks_cluster" else "",
            "age_days": random.randint(age_min, age_max),
            "monthly_cost": round(random.uniform(cost_min, cost_max), 2),
            "tags": {
                "Name": f"{rtype}-{random.randint(1000,9999)}",
                "Environment": random.choice(ENVIRONMENTS),
                "kubernetes.io/cluster": cluster,
            },
        }
        if random.random() > 0.3:
            resource["tags"]["Owner"] = random.choice(TEAMS)

        if rtype == "eks_nodegroup":
            resource["node_count"] = random.randint(1, 10)
            resource["instance_type"] = random.choice(["t3.medium", "t3.large", "m5.large", "c5.xlarge", "r5.large"])
            resource["disk_size_gb"] = random.choice([20, 50, 100, 200])
            resource["min_size"] = 1
            resource["max_size"] = random.randint(5, 20)
            resource["desired_size"] = random.randint(1, 10)

        if rtype == "k8s_pvc":
            resource["storage_gb"] = random.choice([1, 5, 10, 20, 50, 100, 500])
            resource["storage_class"] = random.choice(["gp2", "gp3", "efs", "ebs-csi"])

        if rtype == "k8s_namespace":
            resource["pod_quota"] = random.randint(10, 200)
            resource["resource_quota_cpu"] = random.choice(["4", "8", "16", "32"])
            resource["resource_quota_mem"] = random.choice(["8Gi", "16Gi", "32Gi", "64Gi"])

        resources.append(resource)

    return resources
