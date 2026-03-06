import json
import os
import sys
import subprocess
import time
import shlex
from collections import Counter, defaultdict

def get_git_metadata(file_path):
    """Fetches commit count and last modified timestamp for a file."""
    try:
        quoted_path = shlex.quote(file_path)
        # Get commit count (Churn)
        commit_count_cmd = f"git rev-list --count HEAD -- {quoted_path}"
        commit_count = int(subprocess.check_output(commit_count_cmd, shell=True).decode().strip())
        
        # Get last modified timestamp
        last_mod_cmd = f"git log -1 --format=%ct -- {quoted_path}"
        last_mod = int(subprocess.check_output(last_mod_cmd, shell=True).decode().strip())
        
        return commit_count, last_mod
    except:
        return 1, int(time.time()) # Fallback if not in git or file moved

def generate_html_report(json_report_path, html_report_path, sorted_files, file_stats, findings):
    """Generates an interactive HTML summary from the JSON analysis report."""
    
    # Group findings by file
    findings_by_file = defaultdict(list)
    for f in findings:
        findings_by_file[f.get("file_path", "Unknown")].append(f)

    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "    <title>BlueDen Code Smell Hotspot Report</title>",
        "    <style>",
        "        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background: #f9fafb; color: #333; }",
        "        .container { max-width: 1200px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        "        h1, h2, h3 { color: #111; }",
        "        .stats { display: flex; gap: 20px; margin-bottom: 20px; }",
        "        .stat-card { background: #eff6ff; padding: 15px; border-radius: 6px; flex: 1; border: 1px solid #bfdbfe; }",
        "        .stat-card strong { display: block; font-size: 24px; color: #1d4ed8; }",
        "        .calc-box { background: #f8fafc; padding: 15px; border-left: 4px solid #3b82f6; margin-bottom: 30px; font-size: 14px; border-radius: 4px; }",
        "        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }",
        "        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e5e7eb; }",
        "        th { background: #f3f4f6; font-weight: 600; cursor: pointer; user-select: none; }",
        "        th:hover { background: #e5e7eb; }",
        "        tr.file-row { cursor: pointer; transition: background 0.15s; }",
        "        tr.file-row:hover { background: #f9fafb; }",
        "        .findings-row { display: none; background: #fafafa; }",
        "        .findings-row.active { display: table-row; }",
        "        .findings-container { padding: 20px; border-left: 3px solid #cbd5e1; margin: 10px 10px 10px 40px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }",
        "        .finding-item { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee; }",
        "        .finding-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }",
        "        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }",
        "        .badge-high { background: #fee2e2; color: #991b1b; }",
        "        .badge-medium { background: #fef3c7; color: #92400e; }",
        "        .badge-low { background: #dcfce3; color: #166534; }",
        "        .badge-active { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }",
        "        .badge-legacy { background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db; }",
        "    </style>",
        "</head>",
        "<body>",
        "    <div class='container'>",
        "        <h1>🔥 BlueDen Code Smell Hotspot Report</h1>",
        "        <div class='stats'>",
        f"            <div class='stat-card'>Total Findings<strong>{len(findings)}</strong></div>",
        f"            <div class='stat-card'>Files Scanned<strong>{len(sorted_files)}</strong></div>",
        "        </div>",
        "        <div class='calc-box'>",
        "            <h3>🧮 How is Stench Calculated?</h3>",
        "            <p><strong>Stench Score = Σ (Category Weight × Severity Multiplier)</strong></p>",
        "            <ul style='margin-top:5px;'>",
        "               <li><strong>Weights:</strong> Security (50), Silent Fails (30), Architecture (20), Code Quality (5), Best Practices (2).</li>",
        "               <li><strong>Multipliers:</strong> High (3x), Medium (2x), Low (1x), Basic Tools/NA (1.5x).</li>",
        "            </ul>",
        "            <p><strong>Hotspot Score = Stench Score × Churn (Commit Count)</strong>. This prioritizes messy files that are frequently modified.</p>",
        "        </div>",
        "        <h2>Files Needing Attention</h2>",
        "        <p><em>Click on a row to expand and view specific findings for that file. Click headers to sort.</em></p>",
        "        <table id='hotspotTable'>",
        "            <thead>",
        "                <tr>",
        "                    <th onclick='sortTable(0)'>File Path ⇕</th>",
        "                    <th onclick='sortTable(1, true)'>Hotspot Score ⇕</th>",
        "                    <th onclick='sortTable(2, true)'>Stench Score ⇕</th>",
        "                    <th onclick='sortTable(3, true)'>Findings ⇕</th>",
        "                    <th onclick='sortTable(4, true)'>Churn ⇕</th>",
        "                    <th onclick='sortTable(5)'>Status ⇕</th>",
        "                </tr>",
        "            </thead>",
        "            <tbody>"
    ]

    current_time = int(time.time())
    LEGACY_THRESHOLD_SECONDS = 90 * 24 * 60 * 60

    for idx, (path, stats) in enumerate(sorted_files):
        age_days = (current_time - stats['last_mod']) // (24 * 3600)
        is_legacy = (current_time - stats['last_mod']) > LEGACY_THRESHOLD_SECONDS
        status_class = "badge-legacy" if is_legacy else "badge-active"
        status_text = "LEGACY" if is_legacy else "ACTIVE"
        
        html.append(f"                <tr class='file-row' onclick='toggleFindings({idx})'>")
        html.append(f"                    <td style='font-family: monospace;'>{path}</td>")
        html.append(f"                    <td><strong>{int(stats['hotspot_score'])}</strong></td>")
        html.append(f"                    <td>{int(stats['stench'])}</td>")
        html.append(f"                    <td>{stats['findings']}</td>")
        html.append(f"                    <td>{stats['churn']}</td>")
        html.append(f"                    <td><span class='badge {status_class}'>{status_text} ({age_days}d)</span></td>")
        html.append("                </tr>")
        
        # Expandable findings row
        html.append(f"                <tr id='findings-{idx}' class='findings-row'>")
        html.append("                    <td colspan='6'>")
        html.append("                        <div class='findings-container'>")
        
        file_findings = findings_by_file.get(path, [])
        # Sort findings by severity
        severity_rank = {"High": 0, "Medium": 1, "N/A": 2, "Low": 3}
        file_findings.sort(key=lambda x: severity_rank.get(x.get("severity", "N/A"), 4))
        
        for f in file_findings:
            sev = f.get('severity', 'N/A')
            sev_class = f"badge-{sev.lower()}" if sev != "N/A" else "badge-legacy"
            line = f":{f.get('line')}" if f.get('line') else ""
            html.append(f"                            <div class='finding-item'>")
            html.append(f"                                <span class='badge {sev_class}'>{sev}</span> <strong>{f.get('category')}</strong> ({f.get('tool')}{line})<br>")
            html.append(f"                                <span style='color: #555; margin-top: 4px; display: block;'>{f.get('description', '').replace('<', '&lt;').replace('>', '&gt;')}</span>")
            html.append(f"                            </div>")
            
        html.append("                        </div>")
        html.append("                    </td>")
        html.append("                </tr>")

    html.extend([
        "            </tbody>",
        "        </table>",
        "    </div>",
        "    <script>",
        "        function toggleFindings(idx) {",
        "            const row = document.getElementById('findings-' + idx);",
        "            if (row.classList.contains('active')) {",
        "                row.classList.remove('active');",
        "            } else {",
        "                row.classList.add('active');",
        "            }",
        "        }",
        "        let sortDir = {};",
        "        function sortTable(colIndex, isNumeric=false) {",
        "            const table = document.getElementById('hotspotTable');",
        "            const tbody = table.tBodies[0];",
        "            // Each file has 2 rows (main + findings). We need to sort in pairs.",
        "            const rows = Array.from(tbody.rows);",
        "            let pairs = [];",
        "            for(let i=0; i<rows.length; i+=2) {",
        "                pairs.push({main: rows[i], details: rows[i+1]});",
        "            }",
        "            ",
        "            sortDir[colIndex] = !sortDir[colIndex];",
        "            const dir = sortDir[colIndex] ? 1 : -1;",
        "            ",
        "            pairs.sort((a, b) => {",
        "                let valA = a.main.cells[colIndex].innerText.trim();",
        "                let valB = b.main.cells[colIndex].innerText.trim();",
        "                if(isNumeric) {",
        "                    valA = parseFloat(valA) || 0;",
        "                    valB = parseFloat(valB) || 0;",
        "                }",
        "                if (valA > valB) return 1 * dir;",
        "                if (valA < valB) return -1 * dir;",
        "                return 0;",
        "            });",
        "            ",
        "            pairs.forEach(p => {",
        "                tbody.appendChild(p.main);",
        "                tbody.appendChild(p.details);",
        "            });",
        "        }",
        "    </script>",
        "</body>",
        "</html>"
    ])

    with open(html_report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(html))
    print(f"Interactive HTML report generated successfully at: {html_report_path}")

def generate_markdown_report(json_report_path, markdown_report_path, html_report_path="analysis_report.html"):
    """Generates a prioritized Hotspot Markdown summary from the JSON analysis report."""
    if not os.path.exists(json_report_path):
        print(f"Error: {json_report_path} not found.")
        return

    try:
        with open(json_report_path, 'r', encoding='utf-8') as f:
            findings = json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding {json_report_path}.")
        return

    # 1. Scoring & Categorization Constants
    weights = {
        "Security Vulnerability": 50,
        "Improper Error Handling & Silent Failures": 30,
        "Architectural & Design Flaw": 20,
        "Code Quality & Maintainability": 5,
        "Best Practices & Conventions": 2,
        "Unknown": 1
    }
    multipliers = {
        "High": 3.0,
        "Medium": 2.0,
        "Low": 1.0,
        "N/A": 1.5
    }

    # 2. Process File Metrics (Stench & Churn)
    file_stats = defaultdict(lambda: {"stench": 0, "findings": 0, "churn": 0, "last_mod": 0})
    
    for f in findings:
        path = f.get("file_path", "Unknown")
        cat = f.get("category", "Unknown")
        sev = f.get("severity", "N/A")
        
        score = weights.get(cat, 1) * multipliers.get(sev, 1.5)
        file_stats[path]["stench"] += score
        file_stats[path]["findings"] += 1

    # Enrich with Git metadata
    current_time = int(time.time())
    LEGACY_THRESHOLD_SECONDS = 90 * 24 * 60 * 60 # 3 months

    for path in file_stats:
        churn, last_mod = get_git_metadata(path)
        file_stats[path]["churn"] = churn
        file_stats[path]["last_mod"] = last_mod
        # Hotspot Score = Stench * Churn
        file_stats[path]["hotspot_score"] = file_stats[path]["stench"] * churn

    # 3. Prioritize Hotspots
    sorted_files = sorted(file_stats.items(), key=lambda x: x[1]["hotspot_score"], reverse=True)

    # 4. Build Markdown
    md = []
    md.append("# BlueDen Code Smell Analysis: Hotspot Report")
    md.append(f"\n**Total Findings:** {len(findings)} | **Files Scanned:** {len(file_stats)}")
    md.append(f"\n👉 **[View Interactive HTML Report]({os.path.basename(html_report_path)})** for detailed file breakdowns.\n")
    
    md.append("\n## 🔥 Top 10 Hotspots (Action Required)")
    md.append("> prioritized by **Stench** (Issue Severity) × **Churn** (Commit Frequency)")
    md.append("| File | Hotspot Score | Stench | Findings | Churn | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for path, stats in sorted_files[:10]:
        age_days = (current_time - stats['last_mod']) // (24 * 3600)
        status = "🔴 ACTIVE"
        if (current_time - stats['last_mod']) > LEGACY_THRESHOLD_SECONDS:
            status = "⚪ LEGACY"
        
        md.append(f"| `{path}` | **{int(stats['hotspot_score'])}** | {int(stats['stench'])} | {stats['findings']} | {stats['churn']} | {status} ({age_days}d old) |")

    md.append("\n## Summary by Category")
    categories = Counter([f.get("category", "Unknown") for f in findings])
    md.append("| Category | Count |")
    md.append("| :--- | :--- |")
    for category, count in categories.most_common():
        md.append(f"| {category} | {count} |")

    with open(markdown_report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    
    print(f"Hotspot Markdown report generated successfully at: {markdown_report_path}")

    # 5. Generate HTML Report
    generate_html_report(json_report_path, html_report_path, sorted_files, file_stats, findings)

if __name__ == "__main__":
    JSON_PATH = "analysis_report.json"
    MD_PATH = "analysis_report.md"
    HTML_PATH = "analysis_report.html"
    generate_markdown_report(JSON_PATH, MD_PATH, HTML_PATH)
