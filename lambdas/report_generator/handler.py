"""
Lambda: Report Generator
Generates HTML report and sends via SES.

Input:  { "week_number", "findings_summary", "findings", "incidents", "results", "recipients": ["ops@example.com"] }
Output: { "status": "ok", "report_s3_key": "...", "emails_sent": 1 }
"""
import json
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import boto3

s3 = boto3.client("s3")
ses = boto3.client("ses")

REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "acheron-reports")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "acheron@example.com")


def generate_html(week_number, summary, findings, incident_data, results):
    anomalies = sorted([r for r in results if r.get("is_anomaly")], key=lambda x: x.get("anomaly_score", 0), reverse=True)
    incidents_list = sorted(incident_data.values(), key=lambda x: x.get("count", 0), reverse=True) if incident_data else []

    active = {k: v for k, v in findings.items() if v.get("status") != "resolved"}
    new_w = {k: v for k, v in findings.items() if v.get("status") == "new"}
    recurring = {k: v for k, v in findings.items() if v.get("status") == "recurring"}
    chronic = {k: v for k, v in findings.items() if v.get("status") == "chronic"}
    resolved = {k: v for k, v in findings.items() if v.get("status") == "resolved"}

    def status_badge(status):
        colors = {"new": "#3b82f6", "recurring": "#f59e0b", "chronic": "#ef4444", "resolved": "#10b981"}
        return f'<span style="background:{colors.get(status, "#3b82f6")};color:#fff;padding:2px 8px;border-radius:6px;font-size:0.7rem;font-weight:600;text-transform:uppercase;">{status}</span>'

    top_rows = ""
    for i, r in enumerate(sorted(active.values(), key=lambda x: x.get("estimated_savings", 0), reverse=True)[:10], 1):
        top_rows += f"<tr><td>{i}</td><td><code>{r.get('resource_id','')[:16]}</code></td><td>{r.get('resource_type','')}</td><td>{r.get('anomaly_score',0):.4f}</td><td>${r.get('estimated_savings',0):.2f}</td><td>{r.get('consecutive_weeks',1)}</td><td>{status_badge(r.get('status','new'))}</td></tr>"

    all_rows = ""
    for r in sorted(active.values(), key=lambda x: x.get("anomaly_score", 0), reverse=True)[:40]:
        all_rows += f"<tr><td><code>{r.get('resource_id','')[:20]}</code></td><td>{r.get('resource_type','')}</td><td>{r.get('source','')}</td><td>{r.get('anomaly_score',0):.4f}</td><td>${r.get('estimated_savings',0):.2f}</td><td>{r.get('consecutive_weeks',1)}</td><td>{status_badge(r.get('status','new'))}</td></tr>"

    inc_rows = ""
    for inc in incidents_list[:20]:
        inc_rows += f"<tr><td><code>{inc.get('signature','')[:20]}</code></td><td>{inc.get('level','')}</td><td>{inc.get('normalized_message','')[:70]}</td><td>{inc.get('count',0)}</td><td>{inc.get('consecutive_weeks',1)}</td></tr>"

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Project Acheron — Week #{week_number}</title>
<style>
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f172a; color:#e2e8f0; line-height:1.6; }}
.container {{ max-width:1200px; margin:0 auto; padding:20px; }}
.header {{ background:linear-gradient(135deg,#1e293b,#0f172a); border-bottom:1px solid #334155; padding:40px 0; text-align:center; }}
.header h1 {{ font-size:2rem; color:#38bdf8; margin-bottom:8px; }}
.week-badge {{ display:inline-block; background:#38bdf8; color:#0f172a; padding:4px 16px; border-radius:20px; font-weight:700; }}
h2 {{ color:#38bdf8; border-bottom:1px solid #334155; padding-bottom:8px; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; margin:20px 0; }}
.kpi-card {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; text-align:center; }}
.kpi-card .value {{ font-size:1.8rem; font-weight:700; color:#38bdf8; }}
.kpi-card .label {{ font-size:0.75rem; color:#94a3b8; text-transform:uppercase; }}
.savings {{ color:#4ade80; }}
.badge-new {{ background:#3b82f6; }}
table {{ width:100%; border-collapse:collapse; background:#1e293b; border:1px solid #334155; border-radius:12px; overflow:hidden; margin:16px 0; }}
th {{ background:#334155; color:#94a3b8; font-size:0.7rem; text-transform:uppercase; padding:10px 14px; }}
td {{ padding:8px 14px; border-top:1px solid #1e293b; font-size:0.82rem; }}
code {{ font-family:'JetBrains Mono',monospace; font-size:0.78rem; }}
</style></head><body>
<div class="header"><h1>Project Acheron</h1><p>AWS + Kubernetes Resource Intelligence</p><div class="week-badge">Week #{week_number}</div><p style="color:#64748b;font-size:0.8rem;">{now}</p></div>
<div class="container">
<h2>Executive Summary</h2>
<div class="kpi-grid">
<div class="kpi-card"><div class="value">{summary.get('total',0)}</div><div class="label">Total Findings</div></div>
<div class="kpi-card"><div class="value" style="color:#3b82f6;">{summary.get('new',0)}</div><div class="label">New</div></div>
<div class="kpi-card"><div class="value" style="color:#f59e0b;">{summary.get('recurring',0)}</div><div class="label">Recurring</div></div>
<div class="kpi-card"><div class="value" style="color:#ef4444;">{summary.get('chronic',0)}</div><div class="label">Chronic (6+)</div></div>
<div class="kpi-card"><div class="value" style="color:#10b981;">{summary.get('resolved',0)}</div><div class="label">Resolved</div></div>
<div class="kpi-card"><div class="value savings">${summary.get('estimated_monthly_savings',0):.2f}</div><div class="label">Monthly Savings</div></div>
</div>

<h2>Top Zombie Resources</h2>
<table><thead><tr><th>#</th><th>ID</th><th>Type</th><th>Score</th><th>Savings</th><th>Weeks</th><th>Status</th></tr></thead><tbody>
{top_rows if top_rows else '<tr><td colspan="7" style="text-align:center;color:#64748b;">No zombies.</td></tr>'}
</tbody></table>

<h2>All Active Findings</h2>
<table><thead><tr><th>ID</th><th>Type</th><th>Source</th><th>Score</th><th>Savings</th><th>Weeks</th><th>Status</th></tr></thead><tbody>
{all_rows if all_rows else '<tr><td colspan="7" style="text-align:center;color:#64748b;">None.</td></tr>'}
</tbody></table>

<h2>Operational Incidents</h2>
<table><thead><tr><th>Signature</th><th>Level</th><th>Message</th><th>Count</th><th>Weeks</th></tr></thead><tbody>
{inc_rows if inc_rows else '<tr><td colspan="5" style="text-align:center;color:#64748b;">None.</td></tr>'}
</tbody></table>

<h2>Historical Comparison</h2>
<div class="kpi-grid">
<div class="kpi-card"><div class="value" style="color:#3b82f6;">{len(new_w)}</div><div class="label">Added</div></div>
<div class="kpi-card"><div class="value" style="color:#10b981;">{len(resolved)}</div><div class="label">Resolved</div></div>
<div class="kpi-card"><div class="value" style="color:#f59e0b;">{len(recurring)+len(chronic)}</div><div class="label">Persisting</div></div>
</div>
<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
<tr><td>Active findings</td><td>{len(active)}</td></tr>
<tr><td>New</td><td>{len(new_w)}</td></tr>
<tr><td>Recurring (2-5 wks)</td><td>{len(recurring)}</td></tr>
<tr><td>Chronic (6+ wks)</td><td>{len(chronic)}</td></tr>
<tr><td>Resolved</td><td>{len(resolved)}</td></tr>
<tr><td>Unique incident signatures</td><td>{len(incident_data)}</td></tr>
</tbody></table>
</div>
<div style="text-align:center;padding:32px 0;color:#64748b;font-size:0.8rem;">
<p>Project Acheron — Privacy-first AWS + K8s Resource Intelligence</p>
</div>
</body></html>"""


def handler(event, context):
    week_number = event.get("week_number", 0)
    summary = event.get("findings_summary", {})
    findings = event.get("findings", {})
    incident_data = event.get("incidents", {})
    results = event.get("results", [])
    recipients = event.get("recipients", [])

    html = generate_html(week_number, summary, findings, incident_data, results)

    # Upload to S3
    report_key = f"reports/acheron_report_week_{week_number:03d}.html"
    s3.put_object(
        Bucket=REPORT_BUCKET,
        Key=report_key,
        Body=html.encode("utf-8"),
        ContentType="text/html",
    )

    # Send via SES
    emails_sent = 0
    for recipient in recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Project Acheron — Weekly Resource Report #{week_number}"
            msg["From"] = FROM_EMAIL
            msg["To"] = recipient
            msg.attach(MIMEText(html, "html"))
            ses.send_raw_email(
                Source=FROM_EMAIL,
                Destinations=[recipient],
                RawMessage={"Data": msg.as_string()},
            )
            emails_sent += 1
        except Exception as e:
            print(f"Failed to send to {recipient}: {e}")

    return {
        "status": "ok",
        "report_s3_key": f"s3://{REPORT_BUCKET}/{report_key}",
        "emails_sent": emails_sent,
    }
