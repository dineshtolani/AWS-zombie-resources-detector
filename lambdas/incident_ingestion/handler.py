"""
Lambda: Incident Ingestion
Runs CloudWatch Logs Insights queries to extract ERROR/CRITICAL/FATAL messages,
normalizes dynamic values, and generates deterministic incident signatures.

Input:  { "log_groups": ["/aws/lambda/*", "/aws/eks/*"], "hours_back": 168 }
Output: { "incidents": { "<signature>": { "normalized_message", "level", "count" } } }
"""
import json
import hashlib
import re
import time
import boto3

logs = boto3.client("logs")

DYNAMIC_PATTERNS = [
    (r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '<UUID>'),
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>'),
    (r'\b(i-[0-9a-f]{17})\b', '<INSTANCE_ID>'),
    (r'\b(vol-[0-9a-f]{17})\b', '<VOLUME_ID>'),
    (r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\d.]*Z\b', '<TIMESTAMP>'),
    (r'\b(arn:aws:[\w-]+:[\w-]*:\d{12}:[\w-]+/[\w-]+)\b', '<ARN>'),
    (r'\b\d{4,}\b', '<NUMBER>'),
]


def normalize_message(msg):
    for pattern, replacement in DYNAMIC_PATTERNS:
        msg = re.sub(pattern, replacement, msg)
    return msg


def make_signature(normalized):
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def handler(event, context):
    log_groups = event.get("log_groups", [])
    hours_back = event.get("hours_back", 168)
    start_time = int((time.time() - hours_back * 3600) * 1000)
    end_time = int(time.time() * 1000)

    all_incidents = {}

    for log_group in log_groups:
        query = f"""
        fields @timestamp, @message, @logStream
        | filter @message like /(?i)(ERROR|CRITICAL|FATAL)/
        | sort @timestamp desc
        | limit 10000
        """

        try:
            resp = logs.start_query(
                logGroupNames=[log_group],
                queryString=query.strip(),
                startTime=start_time,
                endTime=end_time,
            )
            query_id = resp["queryId"]

            # Poll for results (up to 60 seconds)
            for _ in range(60):
                result = logs.get_query_results(queryId=query_id)
                if result["status"] == "Complete":
                    break
                time.sleep(1)

            for row in result.get("results", []):
                msg = next((f["value"] for f in row if f["field"] == "@message"), "")
                normalized = normalize_message(msg)
                sig = make_signature(normalized)

                if sig not in all_incidents:
                    level = "ERROR"
                    if "CRITICAL" in msg.upper():
                        level = "CRITICAL"
                    if "FATAL" in msg.upper():
                        level = "FATAL"

                    all_incidents[sig] = {
                        "signature": sig,
                        "normalized_message": normalized,
                        "example_message": msg[:200],
                        "level": level,
                        "count": 0,
                    }
                all_incidents[sig]["count"] += 1

        except Exception as e:
            print(f"Failed to query {log_group}: {e}")

    return {
        "status": "ok",
        "incidents": all_incidents,
        "unique_signatures": len(all_incidents),
        "log_groups_queried": len(log_groups),
    }
