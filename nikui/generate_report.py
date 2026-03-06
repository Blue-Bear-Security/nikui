import json
import os
import sys
import subprocess
import time
import shlex
import argparse
import fnmatch
from collections import defaultdict

def is_excluded(filepath, config):
    if not filepath: return False
    normalized_filepath = os.path.normpath(filepath)
    path_parts = normalized_filepath.split(os.sep)
    for d in config.get('exclusions', {}).get('directories', []):
        if d in path_parts: return True
    for p in config.get('exclusions', {}).get('patterns', []):
        if fnmatch.fnmatch(normalized_filepath, p) or fnmatch.fnmatch(os.path.basename(normalized_filepath), p): return True
    return False

def get_git_metadata(file_path):
    try:
        quoted_path = shlex.quote(file_path)
        commit_count = int(subprocess.check_output(f'git rev-list --count HEAD -- {quoted_path}', shell=True).decode().strip())
        last_mod = int(subprocess.check_output(f'git log -1 --format=%ct -- {quoted_path}', shell=True).decode().strip())
        return commit_count, last_mod
    except Exception as e:
        return 1, int(time.time())

def generate_html_report(json_path, html_path, sorted_files, findings, config):
    findings_by_file = defaultdict(list)
    for f in findings:
        findings_by_file[f.get('file_path', 'Unknown')].append(f)
    
    # Load template
    template_path = os.path.join(os.path.dirname(__file__), "report_template.html")
    if not os.path.exists(template_path):
        print(f"Error: Template not found at {template_path}")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    table_rows = []
    current_time = int(time.time())
    for idx, (path, stats) in enumerate(sorted_files):
        age_days = (current_time - stats['last_mod']) // (24 * 3600)
        status = 'ACTIVE' if age_days < 90 else 'LEGACY'
        
        # Row for the file
        table_rows.append(
            f'<tr onclick="toggleFindings({idx})" style="cursor:pointer">'
            f'<td>{path}</td><td><strong>{int(stats["hotspot_score"])}</strong></td>'
            f'<td>{int(stats["stench"])}</td><td>{stats["findings"]}</td>'
            f'<td>{stats["churn"]}</td><td>{status} ({age_days}d)</td></tr>'
        )
        
        # Row for the expandable findings
        table_rows.append(f'<tr id="findings-{idx}" class="findings-row"><td colspan="6"><div style="padding:20px; border-left:3px solid #ccc; margin-left:20px;">')
        for f in sorted(findings_by_file[path], key=lambda x: x.get("severity", "N/A")):
            sev = f.get("severity", "N/A")
            table_rows.append(
                f'<div style="margin-bottom:10px;"><span class="badge badge-{sev.lower()}">{sev}</span> '
                f'<strong>{f.get("category")}</strong>: {f.get("description")}</div>'
            )
        table_rows.append("</div></td></tr>")

    # Replace placeholders
    html_content = template.replace("{{weights}}", json.dumps(config.get('stench_weights', {})))
    html_content = html_content.replace("{{table_rows}}", "".join(table_rows))

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def generate_reports(repo_path, json_path, html_path, config_path):
    if not os.path.exists(config_path):
        print(f'Error: {config_path} missing')
        sys.exit(1)
        
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_findings = json.load(f)
        
    findings = [f for f in raw_findings if not is_excluded(f.get('file_path', ''), config)]
    weights = config['stench_weights']
    multipliers = {'High': 3.0, 'Medium': 2.0, 'Low': 1.0, 'N/A': 1.5}
    
    file_stats = defaultdict(lambda: {'stench': 0, 'findings': 0, 'churn': 0, 'last_mod': 0})
    orig_cwd = os.getcwd()
    os.chdir(repo_path)
    
    for f in findings:
        path = f.get('file_path', 'Unknown')
        score = weights.get(f.get('category'), 1) * multipliers.get(f.get('severity'), 1.5)
        file_stats[path]['stench'] += score
        file_stats[path]['findings'] += 1
        
    for path in file_stats:
        churn, last_mod = get_git_metadata(path)
        file_stats[path].update({
            'churn': churn,
            'last_mod': last_mod,
            'hotspot_score': file_stats[path]['stench'] * churn
        })
        
    sorted_files = sorted(file_stats.items(), key=lambda x: x[1]['hotspot_score'], reverse=True)
    
    # Ensure results directory exists
    results_dir = os.path.join(orig_cwd, "results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Generate timestamped filename
    repo_name = os.path.basename(os.path.abspath(repo_path)) or "repo"
    timestamp = time.strftime("%Y%m%d_%H%M")
    
    # If the user didn't provide a custom path, use the new default
    if html_path == os.path.abspath("analysis_report.html"):
        final_html_path = os.path.join(results_dir, f"{repo_name}_{timestamp}.html")
    else:
        final_html_path = html_path

    generate_html_report(json_path, final_html_path, sorted_files, findings, config)
    print(f'Report generated: {final_html_path} ({len(findings)} total findings)')
    os.chdir(orig_cwd)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_path")
    parser.add_argument("--json", default="analysis_report.json")
    parser.add_argument("--html", default="analysis_report.html")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    generate_reports(args.repo_path, os.path.abspath(args.json), os.path.abspath(args.html), os.path.abspath(args.config))

if __name__ == "__main__":
    main()
