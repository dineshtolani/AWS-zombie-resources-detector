RESOURCE_TYPES_AWS = ["ec2", "ebs", "rds", "nat", "alb", "efs", "eip"]
RESOURCE_TYPES_K8S = ["eks_cluster", "eks_nodegroup", "k8s_namespace", "k8s_pvc"]
RESOURCE_TYPES = RESOURCE_TYPES_AWS + RESOURCE_TYPES_K8S

REGIONS_AWS = [
    "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
    "ap-south-1", "ap-southeast-1", "ap-northeast-1",
]

COST_RANGES = {
    "ec2":          (8, 400),
    "ebs":          (2, 50),
    "rds":          (15, 600),
    "nat":          (30, 90),
    "alb":          (20, 80),
    "efs":          (5, 100),
    "eip":          (3, 4),
    "eks_cluster":  (70, 150),
    "eks_nodegroup": (120, 800),
    "k8s_namespace": (0, 0),
    "k8s_pvc":      (10, 200),
}

AGE_RANGES = {
    "ec2":          (1, 365),
    "ebs":          (1, 180),
    "rds":          (7, 730),
    "nat":          (1, 365),
    "alb":          (1, 365),
    "efs":          (1, 365),
    "eip":          (1, 1095),
    "eks_cluster":  (30, 730),
    "eks_nodegroup": (7, 365),
    "k8s_namespace": (1, 365),
    "k8s_pvc":      (1, 365),
}

ENVIRONMENTS = ["production", "staging", "development", "testing"]
TEAMS = ["team-platform", "team-data", "team-apps", "team-ml", "team-infra"]

# Feature extractor registry:
# Each resource type registers a function that extracts a fixed-length feature vector
# from (resource_dict, metrics_dict) -> list[float]

FEATURE_EXTRACTORS = {}

def register_extractor(rtype):
    def decorator(fn):
        FEATURE_EXTRACTORS[rtype] = fn
        return fn
    return decorator

def get_extractor(rtype):
    return FEATURE_EXTRACTORS.get(rtype)

def list_registered_types():
    return list(FEATURE_EXTRACTORS.keys())
