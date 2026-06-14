"""
Lambda: Prometheus / Container Insights Collector
Collects EKS cluster, node group, namespace, and PVC metrics.

Input:  { "cluster_name": "eks-prod", "source": "amp" | "container_insights" }
Output: { "resources": [...] }
"""
import json
import boto3
import requests
from datetime import datetime, timedelta
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

cw = boto3.client("cloudwatch")
session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()
region = session.region_name


def sign_request(url, params):
    """SigV4-sign a request to AMP."""
    request = AWSRequest(method="GET", url=url, params=params)
    SigV4Auth(credentials, "aps", region).add_auth(request)
    return request


def query_amp(workspace_id, promql, start, end, step=3600):
    endpoint = f"https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace_id}/api/v1/query_range"
    params = {
        "query": promql,
        "start": start.isoformat() + "Z",
        "end": end.isoformat() + "Z",
        "step": str(step),
    }
    req = sign_request(endpoint, params)
    import urllib.request
    response = urllib.request.urlopen(
        urllib.request.Request(endpoint + "?" + "&".join(f"{k}={v}" for k, v in params.items()),
                               headers=dict(req.headers))
    )
    return json.loads(response.read())["data"]["result"]


def query_container_insights(cluster_name, metric_name, stat="Average", hours_back=168):
    end = datetime.utcnow()
    start = end - timedelta(hours=hours_back)
    response = cw.get_metric_data(
        MetricDataQueries=[{
            "Id": f"ci_{metric_name}",
            "MetricStat": {
                "Metric": {
                    "Namespace": "ContainerInsights",
                    "MetricName": metric_name,
                    "Dimensions": [{"Name": "ClusterName", "Value": cluster_name}]
                },
                "Period": 3600,
                "Stat": stat,
            },
            "ReturnData": True,
        }],
        StartTime=start,
        EndTime=end,
    )
    results = response["MetricDataResults"]
    if results and results[0].get("Values"):
        vals = results[0]["Values"]
        return round(float(sum(vals)) / len(vals), 4)
    return 0.0


def handler(event, context):
    cluster_name = event.get("cluster_name")
    source = event.get("source", "container_insights")
    workspace_id = event.get("workspace_id")
    hours_back = event.get("hours_back", 168)

    resources = []

    if source == "amp":
        # EKS Cluster-level metrics
        cpu_util = query_amp(workspace_id,
            f'avg(kube_node_status_capacity_cpu_cores{{cluster="{cluster_name}"})', ...)
        mem_util = query_amp(workspace_id,
            f'avg(kube_node_status_capacity_memory_bytes{{cluster="{cluster_name}"})', ...)
        node_count = query_amp(workspace_id,
            f'count(kube_node_info{{cluster="{cluster_name}"})', ...)

        resources.append({
            "resource_id": f"eks:{cluster_name}",
            "type": "eks_cluster",
            "source": "k8s",
            "cluster": cluster_name,
            "metrics": {
                "cluster_cpu_util": cpu_util,
                "cluster_mem_util": mem_util,
                "node_count": node_count,
            }
        })

        # Per-nodegroup metrics
        ng_results = query_amp(workspace_id,
            f'avg(node_cpu_utilization{{cluster="{cluster_name}"}}) by (nodegroup)', ...)
        for ng in ng_results:
            resources.append({
                "resource_id": f"{cluster_name}/{ng['metric'].get('nodegroup', 'unknown')}",
                "type": "eks_nodegroup",
                "source": "k8s",
                "cluster": cluster_name,
                "metrics": {
                    "node_cpu_util": float(ng["values"][-1][1]) if ng.get("values") else 0,
                    "pod_count": 0,
                    "container_restarts": 0,
                }
            })

    elif source == "container_insights":
        resources.append({
            "resource_id": f"eks:{cluster_name}",
            "type": "eks_cluster",
            "source": "k8s",
            "cluster": cluster_name,
            "metrics": {
                "cluster_cpu_util": query_container_insights(cluster_name, "node_cpu_utilization"),
                "cluster_mem_util": query_container_insights(cluster_name, "node_memory_utilization"),
                "node_count": query_container_insights(cluster_name, "node_count", stat="SampleCount"),
            }
        })

    # Discover node groups via EKS API
    eks = boto3.client("eks")
    ng_paginator = eks.get_paginator("describe_nodegroup")
    ngs = eks.list_nodegroups(clusterName=cluster_name)["nodegroups"]
    for ng_name in ngs:
        ng_info = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng_name)["nodegroup"]
        resources.append({
            "resource_id": f"{cluster_name}/{ng_name}",
            "type": "eks_nodegroup",
            "source": "k8s",
            "cluster": cluster_name,
            "instance_type": ng_info.get("instanceTypes", ["unknown"])[0],
            "node_count": ng_info.get("scalingConfig", {}).get("desiredSize", 0),
            "metrics": {
                "node_count": ng_info.get("scalingConfig", {}).get("desiredSize", 0),
            }
        })

    return {"status": "ok", "resources": resources, "cluster": cluster_name, "count": len(resources)}
