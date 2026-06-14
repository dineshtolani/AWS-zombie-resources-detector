import json
import os


class StateStore:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.findings_file = os.path.join(data_dir, "findings.json")
        self.incidents_file = os.path.join(data_dir, "incidents.json")
        self.week_counter_file = os.path.join(data_dir, "week_counter.json")
        self._ensure_files()

    def _ensure_files(self):
        for fpath in [self.findings_file, self.incidents_file, self.week_counter_file]:
            if not os.path.exists(fpath):
                with open(fpath, "w") as f:
                    json.dump({} if "week" not in fpath else {"week": 0}, f)

    def _load_json(self, fpath):
        with open(fpath, "r") as f:
            return json.load(f)

    def _save_json(self, fpath, data):
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def get_current_week(self):
        return self._load_json(self.week_counter_file).get("week", 0)

    def advance_week(self):
        data = self._load_json(self.week_counter_file)
        data["week"] = data.get("week", 0) + 1
        self._save_json(self.week_counter_file, data)
        return data["week"]

    def reset(self):
        for fpath in [self.findings_file, self.incidents_file, self.week_counter_file]:
            if os.path.exists(fpath):
                os.remove(fpath)
        self._ensure_files()

    def load_findings(self):
        return self._load_json(self.findings_file)

    def merge_findings(self, current_anomalies, week_number, chronic_threshold=6):
        previous = self.load_findings()
        current_ids = {a["resource"]["resource_id"] for a in current_anomalies}
        updated = {}

        for finding_id, record in previous.items():
            if record.get("status") == "resolved":
                continue
            if finding_id not in current_ids:
                record["status"] = "resolved"
                record["resolved_week"] = week_number
            updated[finding_id] = record

        for anomaly in current_anomalies:
            rid = anomaly["resource"]["resource_id"]
            rtype = anomaly["resource"]["type"]
            source = anomaly["resource"]["source"]

            if rid in updated:
                record = updated[rid]
                record["last_observed_week"] = week_number
                record["consecutive_weeks"] = record.get("consecutive_weeks", 0) + 1
                record["anomaly_score"] = anomaly["anomaly_score"]
                record["estimated_savings"] = anomaly["estimated_savings"]
                record["status"] = "recurring" if record["consecutive_weeks"] >= 2 else "new"
                if record["consecutive_weeks"] >= chronic_threshold:
                    record["status"] = "chronic"
            else:
                tags = anomaly["resource"].get("tags", {})
                updated[rid] = {
                    "resource_id": rid,
                    "resource_type": rtype,
                    "source": source,
                    "region": anomaly["resource"].get("region", "N/A"),
                    "cluster": anomaly["resource"].get("cluster", ""),
                    "namespace": anomaly["resource"].get("namespace", ""),
                    "owner": tags.get("Owner", ""),
                    "anomaly_score": anomaly["anomaly_score"],
                    "estimated_savings": anomaly["estimated_savings"],
                    "first_observed_week": week_number,
                    "last_observed_week": week_number,
                    "consecutive_weeks": 1,
                    "status": "new",
                    "monthly_cost": anomaly["resource"]["monthly_cost"],
                }

        self._save_json(self.findings_file, updated)
        return updated

    def get_findings_summary(self):
        findings = self.load_findings()
        summary = {"new": 0, "recurring": 0, "chronic": 0, "resolved": 0, "total": 0}
        total_savings = 0
        for rid, record in findings.items():
            status = record.get("status", "new")
            if status in summary:
                summary[status] += 1
            summary["total"] += 1
            if status != "resolved":
                total_savings += record.get("estimated_savings", 0)
        summary["estimated_monthly_savings"] = round(total_savings, 2)
        return summary

    def load_incidents(self):
        return self._load_json(self.incidents_file)

    def merge_incidents(self, current_incidents, week_number):
        existing = self.load_incidents()
        for sig_hash, record in current_incidents.items():
            if sig_hash in existing:
                existing[sig_hash]["last_seen_week"] = week_number
                existing[sig_hash]["frequency"] = existing[sig_hash].get("frequency", 0) + record.get("count", 1)
                existing[sig_hash]["consecutive_weeks"] = existing[sig_hash].get("consecutive_weeks", 0) + 1
                weeks_seen = existing[sig_hash].get("weeks_seen", [])
                if week_number not in weeks_seen:
                    weeks_seen.append(week_number)
                existing[sig_hash]["weeks_seen"] = weeks_seen
            else:
                record["first_seen_week"] = week_number
                record["last_seen_week"] = week_number
                record["consecutive_weeks"] = 1
                record["weeks_seen"] = [week_number]
                existing[sig_hash] = record
        self._save_json(self.incidents_file, existing)
        return existing


def print_findings_summary(summary):
    active = summary.get("new", 0) + summary.get("recurring", 0) + summary.get("chronic", 0)
    print(f"\n{'='*50}")
    print(f"  FINDINGS SUMMARY")
    print(f"{'='*50}")
    print(f"  New              : {summary.get('new', 0)}")
    print(f"  Recurring        : {summary.get('recurring', 0)}")
    print(f"  Chronic (6+ wks) : {summary.get('chronic', 0)}")
    print(f"  Resolved         : {summary.get('resolved', 0)}")
    print(f"  Active total     : {active}")
    print(f"  Est. monthly savings: ${summary.get('estimated_monthly_savings', 0):.2f}")
    print(f"{'='*50}\n")
