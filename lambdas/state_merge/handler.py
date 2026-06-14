"""
Lambda: State Merge
Persists detection results to DynamoDB and tracks recurrence.
Distinguishes: new, recurring, chronic (configurable), resolved.
Surfaces owner tags and incident trend direction.

Input:  { "results": [...], "week_number": 12, "chronic_threshold": 6 }
Output: { "findings": {...}, "summary": {...} }
"""
import os
import boto3

dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("FINDINGS_TABLE", "acheron-findings")
table = dynamodb.Table(table_name)
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "acheron-incidents")
incidents_table = dynamodb.Table(INCIDENTS_TABLE)


def compute_trend(record, current_week):
    """Compute trend arrow for incidents: ↑ increasing, ↓ decreasing, → stable."""
    if record.get("consecutive_weeks", 0) < 2:
        return "→"
    prev = record.get("frequency", 0) - record.get("last_count", 0)
    last_count = record.get("last_count", 0)
    if last_count > 0 and prev > last_count * 0.2:
        return "↑"
    elif last_count > 0 and prev < -last_count * 0.2:
        return "↓"
    return "→"


def handler(event, context):
    results = event.get("results", [])
    inc_results = event.get("incidents", {})
    current_week = event.get("week_number", 1)
    chronic_threshold = int(os.environ.get("CHRONIC_THRESHOLD", "6"))

    # Use is_zombie (one-tailed) instead of is_anomaly
    zombie_ids = {r["resource_id"] for r in results if r.get("is_zombie")}

    existing = {}
    for page in table.scan()["Items"]:
        existing[page["resource_id"]] = page

    updated = {}

    # Mark resolved
    for rid, record in existing.items():
        if record.get("status") == "resolved":
            continue
        if rid not in zombie_ids:
            record["status"] = "resolved"
            record["resolved_week"] = current_week
            record["consecutive_weeks"] = 0
        updated[rid] = record

    # Upsert current zombies
    for r in results:
        if not r.get("is_zombie"):
            continue
        rid = r["resource_id"]
        owner = r.get("owner") or r.get("tags", {}).get("Owner", "")

        if rid in updated:
            record = updated[rid]
            record["consecutive_weeks"] = record.get("consecutive_weeks", 0) + 1
            record["last_observed_week"] = current_week
            record["anomaly_score"] = r.get("anomaly_score", 0)
            record["estimated_savings"] = r.get("estimated_savings", 0)
            if owner:
                record["owner"] = owner

            if record["consecutive_weeks"] >= chronic_threshold:
                record["status"] = "chronic"
            elif record["consecutive_weeks"] >= 2:
                record["status"] = "recurring"
            else:
                record["status"] = "new"
        else:
            record = {
                "resource_id": rid,
                "resource_type": r.get("type", ""),
                "source": r.get("source", "aws"),
                "region": r.get("region", ""),
                "cluster": r.get("cluster", ""),
                "namespace": r.get("namespace", ""),
                "owner": owner,
                "anomaly_score": r.get("anomaly_score", 0),
                "estimated_savings": r.get("estimated_savings", 0),
                "monthly_cost": r.get("monthly_cost", 0),
                "first_observed_week": current_week,
                "last_observed_week": current_week,
                "consecutive_weeks": 1,
                "status": "new",
            }
        updated[rid] = record

    # Write findings to DynamoDB
    with table.batch_writer() as batch:
        for rid, record in updated.items():
            batch.put_item(Item=record)

    # Compute summary
    summary = {"new": 0, "recurring": 0, "chronic": 0, "resolved": 0, "total": len(updated)}
    total_savings = 0
    for rid, record in updated.items():
        s = record.get("status", "new")
        if s in summary:
            summary[s] += 1
        if s != "resolved":
            total_savings += record.get("estimated_savings", 0)
    summary["estimated_monthly_savings"] = round(total_savings, 2)

    # ---- Incident trend tracking ----
    if inc_results:
        existing_inc = {}
        for page in incidents_table.scan()["Items"]:
            existing_inc[page["signature"]] = page

        for sig, inc in inc_results.items():
            count = inc.get("count", 0)
            if sig in existing_inc:
                record = existing_inc[sig]
                record["last_seen_week"] = current_week
                record["frequency"] = record.get("frequency", 0) + count
                record["last_count"] = count
                record["consecutive_weeks"] = record.get("consecutive_weeks", 0) + 1
                record["trend"] = compute_trend(record, current_week)
            else:
                record = {
                    "signature": sig,
                    "normalized_message": inc.get("normalized_message", ""),
                    "example_message": inc.get("example_message", ""),
                    "level": inc.get("level", "ERROR"),
                    "first_seen_week": current_week,
                    "last_seen_week": current_week,
                    "frequency": count,
                    "last_count": count,
                    "consecutive_weeks": 1,
                    "trend": "→",
                }
            existing_inc[sig] = record

        with incidents_table.batch_writer() as batch:
            for sig, record in existing_inc.items():
                batch.put_item(Item=record)

    return {
        "status": "ok",
        "findings": updated,
        "summary": summary,
        "week_number": current_week,
    }
