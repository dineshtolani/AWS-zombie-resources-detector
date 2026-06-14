import os
from datetime import datetime


def generate_html_report(week_number, findings_summary, findings, incident_data, results, by_source, output_dir="reports", week_start=None, week_end=None):
    os.makedirs(output_dir, exist_ok=True)

    zombies = sorted([r for r in results if r.get("is_zombie")], key=lambda x: x["anomaly_score"], reverse=True)

    # Merge incident_data with trend info from findings if available
    incidents_list = sorted(incident_data.values(), key=lambda x: x.get("count", 0), reverse=True) if incident_data else []

    active = {k: v for k, v in findings.items() if v.get("status") != "resolved"}
    resolved = {k: v for k, v in findings.items() if v.get("status") == "resolved"}
    new_w = {k: v for k, v in findings.items() if v.get("status") == "new"}
    recurring = {k: v for k, v in findings.items() if v.get("status") == "recurring"}
    chronic = {k: v for k, v in findings.items() if v.get("status") == "chronic"}

    def status_badge(status):
        colors = {"new": "badge-new", "recurring": "badge-recurring", "chronic": "badge-chronic", "resolved": "badge-resolved"}
        return f'<span class="badge {colors.get(status, "badge-new")}">{status}</span>'

    def trend_arrow(trend):
        colors = {"↑": "#ef4444", "↓": "#10b981", "→": "#94a3b8"}
        return f'<span style="color:{colors.get(trend, "#94a3b8")};font-size:1.2rem;">{trend}</span>'

    findings_rows = ""
    for rid, rec in sorted(active.items(), key=lambda x: x[1].get("anomaly_score", 0), reverse=True)[:40]:
        owner = rec.get("owner", "")
        owner_cell = f"<code>{owner}</code>" if owner else "<span style='color:#64748b;'>—</span>"
        findings_rows += f"""<tr><td><code>{rec.get('resource_id', rid)[:20]}</code></td><td>{rec.get('resource_type','N/A')}</td><td>{rec.get('source','N/A')}</td><td>{owner_cell}</td><td>{rec.get('anomaly_score',0):.4f}</td><td>${rec.get('estimated_savings',0):.2f}</td><td>{rec.get('consecutive_weeks',1)}</td><td>{status_badge(rec.get('status','new'))}</td></tr>"""

    incidents_rows = ""
    for inc in incidents_list[:20]:
        trend = inc.get("trend", "→")
        incidents_rows += f"""<tr><td><code>{inc.get('signature','')[:20]}</code></td><td>{inc.get('level','N/A')}</td><td>{inc.get('normalized_message','')[:70]}</td><td>{inc.get('count',0)}</td><td>{inc.get('consecutive_weeks',1)}</td><td>{trend_arrow(trend)}</td></tr>"""

    top_savings = ""
    for i, (rid, rec) in enumerate(sorted(active.items(), key=lambda x: x[1].get("estimated_savings",0), reverse=True)[:10], 1):
        owner = rec.get("owner", "")
        owner_cell = f"<code>{owner}</code>" if owner else "<span style='color:#64748b;'>—</span>"
        top_savings += f"""<tr><td>{i}</td><td><code>{rec.get('resource_id',rid)[:16]}</code></td><td>{rec.get('resource_type','N/A')}</td><td>{owner_cell}</td><td>{rec.get('anomaly_score',0):.4f}</td><td>${rec.get('estimated_savings',0):.2f}</td><td>{rec.get('consecutive_weeks',1)}</td><td>{status_badge(rec.get('status','new'))}</td></tr>"""

    aws_a = by_source.get("aws", {}).get("anomalous", 0)
    k8s_a = by_source.get("k8s", {}).get("anomalous", 0)
    aws_s = by_source.get("aws", {}).get("savings", 0)
    k8s_s = by_source.get("k8s", {}).get("savings", 0)

    if not week_start:
        week_start = datetime.now()
    if not week_end:
        week_end = datetime.now()
    week_start_str = week_start.strftime("%b %d, %Y")
    week_end_str = week_end.strftime("%b %d, %Y")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project Acheron — Weekly Report #{week_number}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f172a; color:#e2e8f0; line-height:1.6; }}
.container {{ max-width:1200px; margin:0 auto; padding:20px; }}
.header {{ background:linear-gradient(135deg,#1e293b,#0f172a); border-bottom:1px solid #334155; padding:40px 0; text-align:center; }}
.header h1 {{ font-size:2rem; color:#38bdf8; margin-bottom:8px; }}
.header p {{ color:#94a3b8; font-size:0.95rem; }}
.header .week-badge {{ display:inline-block; background:#38bdf8; color:#0f172a; padding:4px 16px; border-radius:20px; font-weight:700; font-size:0.9rem; margin-top:12px; }}
.section {{ margin:32px 0; }}
.section h2 {{ font-size:1.3rem; color:#38bdf8; margin-bottom:16px; padding-bottom:8px; border-bottom:1px solid #334155; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; margin-bottom:24px; }}
.kpi-card {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; text-align:center; }}
.kpi-card .value {{ font-size:1.8rem; font-weight:700; color:#38bdf8; }}
.kpi-card .label {{ font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px; }}
.kpi-card .savings {{ color:#4ade80; }}
.kpi-card .danger {{ color:#f87171; }}
.kpi-card .warning {{ color:#fbbf24; }}
table {{ width:100%; border-collapse:collapse; background:#1e293b; border:1px solid #334155; border-radius:12px; overflow:hidden; margin-bottom:16px; }}
th {{ background:#334155; color:#94a3b8; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.5px; padding:10px 14px; text-align:left; font-weight:600; }}
td {{ padding:8px 14px; border-top:1px solid #1e293b; font-size:0.82rem; }}
tr:hover {{ background:#2d3a4f; }}
code {{ font-family:'JetBrains Mono','Fira Code',monospace; font-size:0.78rem; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.68rem; font-weight:600; text-transform:uppercase; }}
.badge-new {{ background:#3b82f6; color:#fff; }}
.badge-recurring {{ background:#f59e0b; color:#000; }}
.badge-chronic {{ background:#ef4444; color:#fff; }}
.badge-resolved {{ background:#10b981; color:#fff; }}
.source-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px; }}
.source-card {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; }}
.source-card h3 {{ font-size:1rem; color:#38bdf8; margin-bottom:8px; }}
.source-card .stat {{ display:flex; justify-content:space-between; padding:4px 0; font-size:0.85rem; }}
.source-card .stat .val {{ color:#e2e8f0; font-weight:600; }}
.comparison-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
.comparison-card {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; text-align:center; }}
.comparison-card h3 {{ font-size:0.95rem; margin-bottom:6px; }}
.comparison-card .count {{ font-size:1.8rem; font-weight:700; }}
.added {{ color:#3b82f6; }}
.resolved-card {{ color:#10b981; }}
.persisting {{ color:#f59e0b; }}
.footer {{ text-align:center; padding:32px 0; color:#64748b; font-size:0.8rem; border-top:1px solid #334155; margin-top:40px; }}
</style>
</head>
<body>
<div class="header">
<h1>Project Acheron</h1>
<p>AWS + Kubernetes Resource Intelligence &bull; Weekly Executive Report</p>
<div class="week-badge">Week #{week_number}</div>
<p style="margin-top:6px; color:#94a3b8; font-size:0.85rem;">{week_start_str} — {week_end_str}</p>
<p style="margin-top:4px; color:#64748b; font-size:0.8rem;">Generated: {now_str}</p>
</div>
<div class="container">

<div class="section">
<h2>Executive Summary</h2>
<div class="kpi-grid">
<div class="kpi-card"><div class="value">{findings_summary.get('total',0)}</div><div class="label">Total Findings</div></div>
<div class="kpi-card"><div class="value" style="color:#3b82f6;">{findings_summary.get('new',0)}</div><div class="label">New This Week</div></div>
<div class="kpi-card"><div class="value warning">{findings_summary.get('recurring',0)}</div><div class="label">Recurring</div></div>
<div class="kpi-card"><div class="value danger">{findings_summary.get('chronic',0)}</div><div class="label">Chronic (6+ wks)</div></div>
<div class="kpi-card"><div class="value" style="color:#10b981;">{findings_summary.get('resolved',0)}</div><div class="label">Resolved</div></div>
<div class="kpi-card"><div class="value savings">${findings_summary.get('estimated_monthly_savings',0):.2f}</div><div class="label">Est. Monthly Savings</div></div>
</div>

<div class="source-grid">
<div class="source-card">
<h3>AWS Resources</h3>
<div class="stat"><span>Zombies detected</span><span class="val">{aws_a}</span></div>
<div class="stat"><span>Est. savings</span><span class="val savings">${aws_s:.2f}</span></div>
</div>
<div class="source-card">
<h3>Kubernetes Resources</h3>
<div class="stat"><span>Zombies detected</span><span class="val">{k8s_a}</span></div>
<div class="stat"><span>Est. savings</span><span class="val savings">${k8s_s:.2f}</span></div>
</div>
</div>
</div>

<div class="section">
<h2>Top Zombie Resources</h2>
<table>
<thead><tr><th>#</th><th>Resource ID</th><th>Type</th><th>Owner</th><th>Score</th><th>Savings</th><th>Weeks</th><th>Status</th></tr></thead>
<tbody>
{top_savings if top_savings else '<tr><td colspan="8" style="text-align:center;padding:24px;color:#64748b;">No zombie resources detected.</td></tr>'}
</tbody>
</table>
</div>

<div class="section">
<h2>All Active Infrastructure Findings</h2>
<table>
<thead><tr><th>Resource ID</th><th>Type</th><th>Source</th><th>Owner</th><th>Score</th><th>Savings</th><th>Weeks</th><th>Status</th></tr></thead>
<tbody>
{findings_rows if findings_rows else '<tr><td colspan="8" style="text-align:center;padding:24px;color:#64748b;">No active findings.</td></tr>'}
</tbody>
</table>
</div>

<div class="section">
<h2>Operational Trends — Top Incidents</h2>
<table>
<thead><tr><th>Signature</th><th>Level</th><th>Normalized Message</th><th>Count</th><th>Weeks</th><th>Trend</th></tr></thead>
<tbody>
{incidents_rows if incidents_rows else '<tr><td colspan="6" style="text-align:center;padding:24px;color:#64748b;">No incidents tracked.</td></tr>'}
</tbody>
</table>
</div>

<div class="section">
<h2>Historical Comparison</h2>
<div class="comparison-grid">
<div class="comparison-card"><h3 style="color:#3b82f6;">Added</h3><div class="count added">{len(new_w)}</div><p style="color:#94a3b8;font-size:0.8rem;">New this week</p></div>
<div class="comparison-card"><h3 style="color:#10b981;">Resolved</h3><div class="count resolved-card">{len(resolved)}</div><p style="color:#94a3b8;font-size:0.8rem;">No longer detected</p></div>
<div class="comparison-card"><h3 style="color:#f59e0b;">Persisting</h3><div class="count persisting">{len(recurring)+len(chronic)}</div><p style="color:#94a3b8;font-size:0.8rem;">Across multiple periods</p></div>
</div>
<table style="margin-top:16px;">
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Total findings (all time)</td><td>{findings_summary.get('total',0)}</td></tr>
<tr><td>Active findings</td><td>{len(active)}</td></tr>
<tr><td>New (first seen)</td><td>{len(new_w)}</td></tr>
<tr><td>Recurring (2-5 wks)</td><td>{len(recurring)}</td></tr>
<tr><td>Chronic (6+ wks)</td><td>{len(chronic)}</td></tr>
<tr><td>Resolved</td><td>{len(resolved)}</td></tr>
<tr><td>Unique incident signatures</td><td>{len(incident_data)}</td></tr>
</tbody>
</table>
</div>

<div class="footer">
<p>Project Acheron — AWS + Kubernetes Resource Intelligence Platform</p>
<p>Privacy-first: all processing local, no data leaves environment boundaries.</p>
<p>Generated at {now_str}</p>
</div>
</div>
</body>
</html>"""

    filename = f"acheron_report_week_{week_number:03d}.html"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        f.write(report)
    print(f"  Report saved: {os.path.abspath(filepath)}")
    return filepath
