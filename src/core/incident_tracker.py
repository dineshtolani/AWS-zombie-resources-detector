import hashlib
import random
import re
import uuid


DYNAMIC_PATTERNS = [
    (r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '<UUID>'),
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>'),
    (r'\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b', '<MAC>'),
    (r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\d.]*Z\b', '<TIMESTAMP>'),
    (r'\b(i-[0-9a-f]{17})\b', '<INSTANCE_ID>'),
    (r'\b(snap-[0-9a-f]{17})\b', '<SNAPSHOT_ID>'),
    (r'\b(vol-[0-9a-f]{17})\b', '<VOLUME_ID>'),
    (r'\b(arn:aws:[\w-]+:[\w-]*:\d{12}:[\w-]+/[\w-]+)\b', '<ARN>'),
    (r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', '<EMAIL>'),
    (r'\b\d{4,}\b', '<NUMBER>'),
]


def normalize_log_message(message):
    normalized = message
    for pattern, replacement in DYNAMIC_PATTERNS:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def generate_signature(normalized_message):
    return hashlib.sha256(normalized_message.encode('utf-8')).hexdigest()[:32]


LOG_TEMPLATES = [
    ("ERROR", "Connection timeout connecting to {service} on {host}:{port}"),
    ("ERROR", "Failed to process request for resource {resource}: {error_code}"),
    ("CRITICAL", "Disk space critical on volume {volume_id}: {percent}% full"),
    ("ERROR", "Database connection pool exhausted on {instance_id}, active connections: {count}"),
    ("FATAL", "OutOfMemoryError in pod {pod_name} on node {node_name}"),
    ("ERROR", "Request to {endpoint} failed with status {status_code} after {retries} retries"),
    ("CRITICAL", "Certificate for {domain} expires in {days} days"),
    ("ERROR", "Unable to assume role {role_arn} for account {account_id}"),
    ("CRITICAL", "AutoScaling activity failed for {asg_name}: {reason}"),
    ("ERROR", "Timeout waiting for {resource_type} {resource_id} to reach {state} state"),
    ("CRITICAL", "ELB {elb_name} has {count} unhealthy hosts in target group {tg_name}"),
    ("ERROR", "Lambda function {function_name} exceeded memory limit of {memory_mb} MB"),
    ("CRITICAL", "RDS instance {db_instance} is in {state} state for {minutes} minutes"),
    ("WARN", "High memory usage on {instance_id}: {percent}%"),
    ("ERROR", "K8s pod {pod_name} in CrashLoopBackOff in namespace {namespace}"),
    ("CRITICAL", "Node {node_name} has {count} taints preventing pod scheduling"),
    ("ERROR", "PVC {pvc_name} is pending in namespace {namespace}: {reason}"),
    ("CRITICAL", "K8s API server {api_server} is unreachable from {node}"),
    ("FATAL", "Node {node_name} disk pressure: {percent}% disk usage"),
    ("ERROR", "Ingress {ingress_name} has {count} backend failures for path {path}"),
]


def simulate_incidents(week_number, base_count=80):
    random.seed(hash(f"incidents_week_{week_number}") % (2**31))
    incidents = {}
    recurring_seeds = [hash(f"recurring_{i}") % (2**31) for i in range(10)]

    for i in range(base_count):
        if random.random() < 0.35 and recurring_seeds:
            seed = random.choice(recurring_seeds)
            random.seed(seed)
            template = random.choice(LOG_TEMPLATES)
        else:
            template = random.choice(LOG_TEMPLATES)

        level, message_template = template
        variables = {
            "service": random.choice(["api-gateway", "auth-service", "payment-svc", "notification-svc", "user-svc", "checkout-svc"]),
            "host": f"10.0.{random.randint(0,255)}.{random.randint(1,254)}",
            "port": random.choice([443, 8080, 5432, 6379, 9090, 8443]),
            "resource": f"arn:aws:s3:::bucket-{random.randint(1000,9999)}/key-{uuid.uuid4().hex[:8]}",
            "error_code": random.choice(["AccessDenied", "Throttling", "LimitExceeded", "InternalFailure", "Timeout", "ValidationError"]),
            "volume_id": f"vol-{uuid.uuid4().hex[:17]}",
            "percent": random.randint(75, 99),
            "instance_id": f"i-{uuid.uuid4().hex[:17]}",
            "count": random.randint(50, 200),
            "pod_name": f"app-{random.randint(1,20)}-{uuid.uuid4().hex[:5]}",
            "node_name": f"node-{random.randint(1,20)}",
            "endpoint": random.choice(["/api/v1/users", "/api/v1/orders", "/health", "/metrics", "/api/v1/checkout"]),
            "status_code": random.choice([500, 502, 503, 504, 429, 403]),
            "retries": random.randint(2, 5),
            "domain": random.choice(["app.example.com", "api.example.com", "admin.example.com", "checkout.example.com"]),
            "days": random.randint(1, 14),
            "role_arn": f"arn:aws:iam::123456789012:role/CrossAccountRole-{random.randint(1,5)}",
            "account_id": "123456789012",
            "s3_key": f"data/{uuid.uuid4().hex[:8]}/file.json",
            "error_message": random.choice(["Permission denied", "Not found", "Rate exceeded", "Service unavailable", "Internal error", "Timeout"]),
            "asg_name": f"asg-{random.choice(['web', 'api', 'worker', 'ml'])}-{random.randint(1,5)}",
            "reason": random.choice(["Insufficient capacity", "Health check failed", "Launch template error", "Scale-in protection"]),
            "api_name": random.choice(["Stripe", "S3", "DynamoDB", "SQS", "SNS", "ECS"]),
            "current": random.randint(80, 100),
            "limit": 100,
            "app_name": random.choice(["frontend", "checkout", "inventory", "notifications", "ml-inference"]),
            "version": f"v{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,20)}",
            "resource_type": random.choice(["ec2", "rds", "elb", "nat", "eks-nodegroup"]),
            "resource_id": f"res-{uuid.uuid4().hex[:8]}",
            "state": random.choice(["available", "stopped", "terminated", "deleted", "pending"]),
            "elb_name": f"app-{random.choice(['web', 'api', 'worker', 'ml'])}-{random.randint(1000,9999)}",
            "tg_name": f"tg-{random.choice(['web', 'api', 'worker'])}-{random.randint(100,999)}",
            "kms_key_id": f"alias/key-{uuid.uuid4().hex[:8]}",
            "function_name": f"service-{random.choice(['auth', 'payment', 'order', 'user', 'ml'])}-{random.choice(['prod', 'staging'])}",
            "memory_mb": random.choice([128, 256, 512, 1024, 2048, 4096]),
            "db_instance": f"db-{random.choice(['prod', 'staging', 'dev'])}-{random.randint(1,10)}",
            "minutes": random.randint(5, 120),
            "cluster_id": f"redis-{uuid.uuid4().hex[:8]}",
            "az": f"us-east-{random.randint(1,6)}",
            "namespace": random.choice(["default", "kube-system", "monitoring", "payments", "auth", "ml-workloads"]),
            "pvc_name": f"data-{uuid.uuid4().hex[:6]}",
            "api_server": f"k8s-{random.randint(1,3)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            "node": f"ip-10-0-{random.randint(1,255)}-{random.randint(1,255)}",
            "ingress_name": f"app-{random.choice(['web', 'api', 'grpc'])}",
            "path": random.choice(["/", "/api", "/health", "/static/*", "/graphql"]),
        }

        message = message_template.format(**variables)
        normalized = normalize_log_message(message)

        if level in ("ERROR", "CRITICAL", "FATAL"):
            sig = generate_signature(normalized)
            if sig not in incidents:
                incidents[sig] = {
                    "signature": sig,
                    "normalized_message": normalized,
                    "example_message": message,
                    "level": level,
                    "count": 0,
                    "first_seen_week": week_number,
                }
            incidents[sig]["count"] += 1

    return incidents


def print_incident_summary(incidents):
    sigs = list(incidents.values())
    sigs.sort(key=lambda x: x.get("count", 0), reverse=True)
    print(f"\n{'='*60}")
    print(f"  INCIDENT SIGNATURES — {len(sigs)} unique patterns")
    print(f"{'='*60}")
    for inc in sigs[:8]:
        sig = inc.get("signature", "")[:24]
        level = inc.get("level", "?")
        count = inc.get("count", 0)
        msg = inc.get("normalized_message", "")[:55]
        print(f"  {sig:<26} {level:<8} {count:>4}x  {msg}")
    print(f"{'='*60}\n")
