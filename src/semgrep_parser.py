import json
import sys

def categorize_semgrep_finding(check_id, semgrep_severity, semgrep_category=None):
    """
    Categorizes a Semgrep finding into our high-level categories.
    """
    check_id_lower = check_id.lower()
    category_lower = (semgrep_category or "").lower()

    # 1. Security Vulnerability
    if "security" in check_id_lower or "security" in category_lower or semgrep_severity == "ERROR" or "audit" in check_id_lower:
        return "Security Vulnerability"
    
    # 2. Architectural & Design Flaw
    if "design" in check_id_lower or "complexity" in check_id_lower or "architecture" in check_id_lower:
        return "Architectural & Design Flaw"

    # 3. Best Practices & Conventions
    if "best-practice" in check_id_lower or "correctness" in check_id_lower or "convention" in check_id_lower:
        return "Best Practices & Conventions"
    
    # 4. Code Quality & Maintainability (Default)
    return "Code Quality & Maintainability"

def parse_semgrep_results(json_data):
    """
    Parses Semgrep JSON results and categorizes them.
    """
    categorized_findings = []
    
    for finding in json_data.get("results", []):
        file_path = finding.get("path")
        line = finding.get("start", {}).get("line")
        check_id = finding.get("check_id")
        message = finding.get("extra", {}).get("message")
        semgrep_severity = finding.get("extra", {}).get("severity")
        semgrep_category = finding.get("extra", {}).get("metadata", {}).get("category")

        category = categorize_semgrep_finding(check_id, semgrep_severity, semgrep_category)

        categorized_findings.append({
            "tool": "Semgrep",
            "file_path": file_path,
            "line": line,
            "category": category,
            "description": f"[{check_id}] {message}"
        })
    return categorized_findings

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python semgrep_parser.py <semgrep_json_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            semgrep_output = json.load(f)
        
        parsed_findings = parse_semgrep_results(semgrep_output)
        print(json.dumps(parsed_findings, indent=2))

    except FileNotFoundError:
        print(f"Error: File not found at {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {input_file}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
