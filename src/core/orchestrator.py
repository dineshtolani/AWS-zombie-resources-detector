from datetime import datetime, timedelta
from src.collectors.cloudwatch import CloudWatchCollector
from src.collectors.prometheus import PrometheusCollector
from src.detectors.zombie_detector import detect_per_type, analyze_by_source, print_detection_summary
from src.core.state_store import StateStore, print_findings_summary
from src.core.incident_tracker import simulate_incidents, print_incident_summary
from src.reporting.html_report import generate_html_report


class AcheronOrchestrator:
    """
    Simulates the AWS Step Functions workflow:
    1. Collect resources + metrics (CloudWatch + Prometheus)
    2. Run per-type Isolation Forest detection
    3. Merge findings into persistent store (DynamoDB)
    4. Simulate incident log ingestion
    5. Generate HTML report
    """

    def __init__(self, data_dir="data", reports_dir="reports"):
        self.store = StateStore(data_dir)
        self.cw_collector = CloudWatchCollector()
        self.prom_collector = PrometheusCollector()
        self.reports_dir = reports_dir

    def run_week(self, week_number=None, cw_count=120, prom_count=80, incident_count=80, week_start=None, week_end=None):
        if week_number is None:
            week_number = self.store.advance_week()
        else:
            week_number = week_number

        if week_start is None:
            week_start = datetime.now()
        if week_end is None:
            week_end = datetime.now()

        print(f"\n{'#'*60}")
        print(f"  ACHERON WEEKLY SCAN — Week #{week_number} ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')})")
        print(f"{'#'*60}")

        # Step 1: Collect data (fixed resource pool, metrics vary by week)
        print("\n[1/5] Collecting AWS resources...")
        aws_pairs = self.cw_collector.collect(resource_count=cw_count, seed=42, week_offset=week_number)

        print("[2/5] Collecting K8s resources...")
        k8s_pairs = self.prom_collector.collect(resource_count=prom_count, seed=42, week_offset=week_number)

        all_pairs = aws_pairs + k8s_pairs

        # Step 2: Detect zombies
        print("[3/5] Running per-type Isolation Forest detection...")
        results, models = detect_per_type(all_pairs, contamination=0.20, random_state=42 + week_number)
        print_detection_summary(results)
        by_source = analyze_by_source(results)

        # Step 3: Persist findings (only one-tailed zombies, not all anomalies)
        print("[4/5] Merging findings into state store...")
        zombies = [r for r in results if r.get("is_zombie")]
        findings = self.store.merge_findings(zombies, week_number, chronic_threshold=6)
        summary = self.store.get_findings_summary()
        print_findings_summary(summary)

        # Step 4: Incident tracking
        print("[5/5] Tracking operational incidents...")
        incidents = simulate_incidents(week_number, base_count=incident_count)
        all_incidents = self.store.merge_incidents(incidents, week_number)
        print_incident_summary(all_incidents)

        # Step 5: Generate report
        report_path = generate_html_report(
            week_number=week_number,
            findings_summary=summary,
            findings=findings,
            incident_data=all_incidents,
            results=results,
            by_source=by_source,
            output_dir=self.reports_dir,
            week_start=week_start,
            week_end=week_end,
        )

        print(f"\n{'#'*60}")
        print(f"  WEEK #{week_number} COMPLETE")
        print(f"  Report: {report_path}")
        print(f"{'#'*60}\n")

        return {
            "week": week_number,
            "findings_summary": summary,
            "results_count": len(results),
            "anomalies_count": len(zombies),
            "report_path": report_path,
        }

    def simulate_weeks(self, num_weeks=4, cw_count=120, prom_count=80, incident_count=80):
        print(f"\n{'='*60}")
        print(f"  PROJECT ACHERON — SIMULATION")
        print(f"  Simulating {num_weeks} weeks of weekly scans")
        print(f"{'='*60}")

        self.store.reset()
        results = []
        base_date = datetime.now()
        for w in range(1, num_weeks + 1):
            self.store.advance_week()
            week_start = base_date - timedelta(weeks=num_weeks - w + 1)
            week_end = base_date - timedelta(weeks=num_weeks - w)
            r = self.run_week(
                week_number=w, cw_count=cw_count, prom_count=prom_count,
                incident_count=incident_count,
                week_start=week_start, week_end=week_end,
            )
            results.append(r)

        print(f"\n{'='*60}")
        print(f"  SIMULATION COMPLETE — {num_weeks} WEEKS")
        print(f"{'='*60}")
        for r in results:
            print(f"  Week {r['week']:2d} : {r['anomalies_count']:3d} zombies, "
                  f"{r['findings_summary']['new']:2d} new, "
                  f"{r['findings_summary']['recurring']:2d} recurring, "
                  f"{r['findings_summary']['chronic']:2d} chronic, "
                  f"${r['findings_summary']['estimated_monthly_savings']:>8.2f} savings")
        print(f"{'='*60}\n")
        print(f"Reports saved in: {self.reports_dir}/")
        return results
