"""
Lambda: CloudWatch Metrics Collector
Collects CloudWatch metrics for EC2, RDS, EBS, ALB, NAT, EIP, EFS.

Triggered by: Step Functions
Input:  { "resource_ids": [...], "resource_type": "ec2", "hours_back": 168 }
Output: { "resources": [{ "resource_id", "type", "metrics": {...} }, ...] }
"""
import json
import boto3
from datetime import datetime, timedelta
from decimal import Decimal

cw = boto3.client("cloudwatch")


def build_metric_query(resource_id, rtype, namespace, metric_name, stat, period=3600):
    dim_name = {
        "ec2": "InstanceId", "ebs": "VolumeId", "rds": "DBInstanceIdentifier",
        "alb": "LoadBalancer", "nat": "NatGatewayId",
        "efs": "FileSystemId", "eip": "AllocationId",
    }.get(rtype, "ResourceId")

    return {
        "Id": f"{rtype}_{resource_id[:8]}_{metric_name}".replace("-", "_"),
        "MetricStat": {
            "Metric": {
                "Namespace": namespace,
                "MetricName": metric_name,
                "Dimensions": [{"Name": dim_name, "Value": resource_id}]
            },
            "Period": period,
            "Stat": stat,
        },
        "ReturnData": True,
    }


METRICS_BY_TYPE = {
    "ec2": (("AWS/EC2", "CPUUtilization", "Average"),
            ("AWS/EC2", "NetworkIn", "Average"),
            ("AWS/EC2", "NetworkOut", "Average")),
    "ebs": (("AWS/EBS", "VolumeReadBytes", "Average"),
            ("AWS/EBS", "VolumeWriteBytes", "Average"),
            ("AWS/EBS", "VolumeQueueLength", "Average")),
    "rds": (("AWS/RDS", "CPUUtilization", "Average"),
            ("AWS/RDS", "DatabaseConnections", "Average"),
            ("AWS/RDS", "FreeableMemory", "Average")),
    "nat": (("AWS/NATGateway", "BytesInFromDestination", "Average"),
            ("AWS/NATGateway", "BytesOutToDestination", "Average"),
            ("AWS/NATGateway", "PacketsInFromDestination", "Average"),
            ("AWS/NATGateway", "PacketsOutToDestination", "Average")),
    "alb": (("AWS/ApplicationELB", "RequestCount", "Sum"),
            ("AWS/ApplicationELB", "ActiveConnectionCount", "Average"),
            ("AWS/ApplicationELB", "NewConnectionCount", "Average")),
    "efs": (("AWS/EFS", "BurstCreditBalance", "Average"),
            ("AWS/EFS", "DataReadIOBytes", "Average"),
            ("AWS/EFS", "DataWriteIOBytes", "Average")),
    "eip": (("AWS/VPN", "TunnelDataIn", "Average"),
            ("AWS/VPN", "TunnelDataOut", "Average")),
}


def handler(event, context):
    rtype = event.get("resource_type")
    resource_ids = event.get("resource_ids", [])
    hours_back = event.get("hours_back", 168)
    end = datetime.utcnow()
    start = end - timedelta(hours=hours_back)

    if not resource_ids or not rtype:
        return {"status": "error", "message": "Missing resource_type or resource_ids"}

    metric_defs = METRICS_BY_TYPE.get(rtype)
    if not metric_defs:
        return {"status": "error", "message": f"Unsupported type: {rtype}"}

    queries = []
    for rid in resource_ids:
        for namespace, metric, stat in metric_defs:
            queries.append(build_metric_query(rid, rtype, namespace, metric, stat))

    # CloudWatch GetMetricData supports 500 queries per call
    resources = {}
    for i in range(0, len(queries), 450):
        batch = queries[i:i + 450]
        response = cw.get_metric_data(
            MetricDataQueries=batch,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampDescending",
        )
        for result in response["MetricDataResults"]:
            values = result.get("Values", [])
            avg_val = float(sum(values)) / len(values) if values else 0.0
            # Parse the query ID back to resource_id and metric
            parts = result["Id"].split("_", 2)
            if len(parts) >= 3:
                rid_prefix = parts[1]
                metric_name = parts[2]
                # Match resource_id
                matched_rid = next((r for r in resource_ids if r.startswith(rid_prefix)), None)
                if matched_rid:
                    if matched_rid not in resources:
                        resources[matched_rid] = {
                            "resource_id": matched_rid,
                            "type": rtype,
                            "metrics": {},
                        }
                    resources[matched_rid]["metrics"][metric_name] = round(avg_val, 4)

    # Attach state info via Describe* APIs (example for EBS)
    if rtype == "ebs":
        ec2 = boto3.client("ec2")
        vols = ec2.describe_volumes(VolumeIds=resource_ids)
        attachments = {v["VolumeId"]: v.get("Attachments", []) for v in vols["Volumes"]}
        for rid in resource_ids:
            if rid in resources:
                resources[rid]["metrics"]["attached"] = len(attachments.get(rid, [])) > 0

    return {
        "status": "ok",
        "resources": list(resources.values()),
        "type": rtype,
        "count": len(resources),
    }
