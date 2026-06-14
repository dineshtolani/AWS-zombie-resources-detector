"""
Lambda: Resource Discovery
Discovers AWS resources via Describe* APIs and EKS via List* APIs.
Outputs organized lists of resource IDs by type, including tags and cost info.

Called by: Step Functions (first step in workflow)
Input:  { "regions": ["us-east-1"], "eks_clusters": ["eks-prod"] }
Output: {
    "resources": {
        "ec2":         [{ "resource_id", "region", "tags", "monthly_cost" }, ...],
        "ebs":         [...],
        "rds":         [...],
        "nat":         [...],
        "alb":         [...],
        "efs":         [...],
        "eip":         [...],
        "eks_cluster": [{ "resource_id", "cluster", "tags", ... }],
        "eks_nodegroup": [...],
    },
    "id_lists": {
        "ec2_ids":  [...],
        "ebs_ids":  [...],
        ...
    },
    "resource_count": 123,
    "week_number": 12,
}
"""
import boto3
from datetime import datetime, timezone

ec2 = boto3.client("ec2")
rds = boto3.client("rds")
elbv2 = boto3.client("elbv2")
efs_client = boto3.client("efs")
eks = boto3.client("eks")


def _extract_tags(tag_list):
    return {t["Key"]: t["Value"] for t in tag_list} if tag_list else {}


def discover_ec2(region):
    client = boto3.client("ec2", region_name=region)
    resources = []
    paginator = client.get_paginator("describe_instances")
    for page in paginator.paginate():
        for r in page.get("Reservations", []):
            for inst in r.get("Instances", []):
                if inst.get("State", {}).get("Name") in ("terminated", "shutting-down"):
                    continue
                tags = _extract_tags(inst.get("Tags", []))
                resources.append({
                    "resource_id": inst["InstanceId"],
                    "type": "ec2",
                    "region": region,
                    "state": inst.get("State", {}).get("Name", "unknown"),
                    "instance_type": inst.get("InstanceType", ""),
                    "launch_time": inst.get("LaunchTime", "").isoformat() if inst.get("LaunchTime") else "",
                    "tags": tags,
                    "monthly_cost": _estimate_ec2_cost(inst.get("InstanceType", "t3.medium")),
                })
    return resources


def _estimate_ec2_cost(instance_type):
    # Rough on-demand prices per hour * 730 hours
    prices = {
        "t3.nano": 5, "t3.micro": 8, "t3.small": 17, "t3.medium": 34,
        "t3.large": 67, "t3.xlarge": 134, "t3.2xlarge": 269,
        "m5.large": 77, "m5.xlarge": 154, "m5.2xlarge": 308,
        "c5.large": 69, "c5.xlarge": 138, "c5.2xlarge": 276,
        "r5.large": 91, "r5.xlarge": 182, "r5.2xlarge": 364,
    }
    return round(prices.get(instance_type, 50), 2)


def discover_ebs(region):
    client = boto3.client("ec2", region_name=region)
    resources = []
    for page in client.get_paginator("describe_volumes").paginate():
        for vol in page.get("Volumes", []):
            tags = _extract_tags(vol.get("Tags", []))
            attachments = vol.get("Attachments", [])
            resources.append({
                "resource_id": vol["VolumeId"],
                "type": "ebs",
                "region": region,
                "size_gb": vol.get("Size", 0),
                "attached": len(attachments) > 0,
                "attached_instance": attachments[0]["InstanceId"] if attachments else "",
                "state": vol.get("State", ""),
                "tags": tags,
                "monthly_cost": round(vol.get("Size", 0) * 0.08, 2),
            })
    return resources


def discover_rds(region):
    client = boto3.client("rds", region_name=region)
    resources = []
    for page in client.get_paginator("describe_db_instances").paginate():
        for db in page.get("DBInstances", []):
            if db.get("DBInstanceStatus") in ("deleting", "deleted"):
                continue
            tags_raw = client.list_tags_for_resource(ResourceName=db["DBInstanceArn"])["TagList"]
            tags = _extract_tags(tags_raw)
            resources.append({
                "resource_id": db["DBInstanceIdentifier"],
                "type": "rds",
                "region": region,
                "engine": db.get("Engine", ""),
                "instance_class": db.get("DBInstanceClass", ""),
                "storage_gb": db.get("AllocatedStorage", 0),
                "multi_az": db.get("MultiAZ", False),
                "tags": tags,
                "monthly_cost": _estimate_rds_cost(db.get("DBInstanceClass", "db.t3.medium")),
            })
    return resources


def _estimate_rds_cost(instance_class):
    prices = {
        "db.t3.micro": 17, "db.t3.small": 34, "db.t3.medium": 68,
        "db.t3.large": 136, "db.r5.large": 175, "db.r5.xlarge": 350,
    }
    return round(prices.get(instance_class, 100), 2)


def discover_nat(region):
    client = boto3.client("ec2", region_name=region)
    resources = []
    for page in client.get_paginator("describe_nat_gateways").paginate():
        for ngw in page.get("NatGateways", []):
            if ngw.get("State") in ("deleted", "deleting"):
                continue
            tags = _extract_tags(ngw.get("Tags", []))
            resources.append({
                "resource_id": ngw["NatGatewayId"],
                "type": "nat",
                "region": region,
                "state": ngw.get("State", ""),
                "vpc_id": ngw.get("VpcId", ""),
                "tags": tags,
                "monthly_cost": 32.40,  # NAT Gateway hourly ~$0.045 * 720
            })
    return resources


def discover_alb(region):
    client = boto3.client("elbv2", region_name=region)
    resources = []
    for page in client.get_paginator("describe_load_balancers").paginate():
        for lb in page.get("LoadBalancers", []):
            if lb.get("State", {}).get("Code") in ("active_impaired", "failed"):
                continue
            tags_raw = client.describe_tags(ResourceArns=[lb["LoadBalancerArn"]])["TagDescriptions"]
            tags = _extract_tags(tags_raw[0]["Tags"]) if tags_raw else {}
            resources.append({
                "resource_id": lb["LoadBalancerArn"].split("/")[-1],
                "type": "alb",
                "region": region,
                "scheme": lb.get("Scheme", ""),
                "type": lb.get("Type", "application"),
                "tags": tags,
                "monthly_cost": 22.50,  # ~$0.0225 per hour * 720 for ALB
            })
    return resources


def discover_efs(region):
    client = boto3.client("efs", region_name=region)
    resources = []
    for page in client.get_paginator("describe_file_systems").paginate():
        for fs in page.get("FileSystems", []):
            if fs.get("LifeCycleState") != "available":
                continue
            tags_raw = client.describe_tags(FileSystemId=fs["FileSystemId"])["Tags"]
            tags = _extract_tags(tags_raw)
            resources.append({
                "resource_id": fs["FileSystemId"],
                "type": "efs",
                "region": region,
                "size_gb": fs.get("SizeInBytes", {}).get("Value", 0) / (1024**3),
                "performance_mode": fs.get("PerformanceMode", ""),
                "tags": tags,
                "monthly_cost": round(fs.get("SizeInBytes", {}).get("Value", 0) / (1024**3) * 0.30, 2),
            })
    return resources


def discover_eip(region):
    client = boto3.client("ec2", region_name=region)
    resources = []
    for page in client.get_paginator("describe_addresses").paginate():
        for addr in page.get("Addresses", []):
            tags = _extract_tags(addr.get("Tags", []))
            resources.append({
                "resource_id": addr["AllocationId"],
                "type": "eip",
                "region": region,
                "public_ip": addr.get("PublicIp", ""),
                "associated": addr.get("AssociationId") is not None,
                "tags": tags,
                "monthly_cost": 3.60,  # $0.005 per hour
            })
    return resources


def discover_eks(region):
    client = boto3.client("eks", region_name=region)
    resources = []
    clusters = client.list_clusters()["clusters"]
    for cluster_name in clusters:
        cluster_info = client.describe_cluster(name=cluster_name)["cluster"]
        tags = _extract_tags(cluster_info.get("tags", {}))
        resources.append({
            "resource_id": f"eks:{cluster_name}",
            "type": "eks_cluster",
            "region": region,
            "cluster": cluster_name,
            "version": cluster_info.get("version", ""),
            "endpoint": cluster_info.get("endpoint", ""),
            "tags": tags,
            "monthly_cost": 73.00,  # EKS cluster ~$0.10/hour
        })

        # Discover node groups for each cluster
        ng_names = client.list_nodegroups(clusterName=cluster_name)["nodegroups"]
        for ng_name in ng_names:
            ng = client.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng_name)["nodegroup"]
            ng_tags = _extract_tags(ng.get("tags", {}))
            instance_type = ng.get("instanceTypes", ["unknown"])[0]
            desired = ng.get("scalingConfig", {}).get("desiredSize", 0)
            resources.append({
                "resource_id": f"{cluster_name}/{ng_name}",
                "type": "eks_nodegroup",
                "region": region,
                "cluster": cluster_name,
                "nodegroup": ng_name,
                "instance_type": instance_type,
                "desired_size": desired,
                "min_size": ng.get("scalingConfig", {}).get("minSize", 0),
                "max_size": ng.get("scalingConfig", {}).get("maxSize", 0),
                "tags": ng_tags,
                "monthly_cost": round(desired * _estimate_ec2_cost(instance_type), 2),
            })

    return resources


def handler(event, context):
    regions = event.get("regions", [context.invoked_function_arn.split(":")[3]])
    eks_clusters = event.get("eks_clusters", [])
    week_number = event.get("week_number", 1)

    all_resources = {}
    id_lists = {}

    # AWS resource discovery per region
    for region in regions:
        discover_fns = {
            "ec2": discover_ec2,
            "ebs": discover_ebs,
            "rds": discover_rds,
            "nat": discover_nat,
            "alb": discover_alb,
            "efs": discover_efs,
            "eip": discover_eip,
        }

        for rtype, fn in discover_fns.items():
            try:
                items = fn(region)
                if rtype not in all_resources:
                    all_resources[rtype] = []
                all_resources[rtype].extend(items)
            except Exception as e:
                print(f"Failed to discover {rtype} in {region}: {e}")

    # EKS discovery (separate since it's cluster-based, not service-based)
    try:
        eks_resources = discover_eks(regions[0])
        for r in eks_resources:
            rtype = r["type"]
            if rtype not in all_resources:
                all_resources[rtype] = []
            all_resources[rtype].append(r)
    except Exception as e:
        print(f"Failed to discover EKS: {e}")

    # Build flat ID lists for metric collectors
    for rtype, items in all_resources.items():
        id_lists[f"{rtype}_ids"] = [r["resource_id"] for r in items]

    total_count = sum(len(v) for v in all_resources.values())

    return {
        "status": "ok",
        "resources": all_resources,
        "id_lists": id_lists,
        "resource_count": total_count,
        "week_number": week_number,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
