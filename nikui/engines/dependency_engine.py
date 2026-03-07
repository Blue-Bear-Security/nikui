import os
import re
import sys
from collections import defaultdict

class DependencyEngine:
    def __init__(self, config):
        self.config = config
        self.outgoing_edges = defaultdict(list)
        self.incoming_edges = defaultdict(list)

    def extract_imports(self, file_path):
        """Extracts local imports from Python, Go, and JS/TS files."""
        ext = os.path.splitext(file_path)[1]
        imports = []
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return []

        if ext == ".py":
            # Matches: import nikui.utils OR from nikui import utils
            patterns = [r"^import\s+([a-zA-Z0-9_\.]+)", r"^from\s+([a-zA-Z0-9_\.]+)\s+import"]
        elif ext in [".js", ".ts", ".tsx"]:
            # Matches: import { x } from './utils' OR require('./utils')
            patterns = [r"from\s+['\"](.*?)['\"]", r"require\(['\"](.*?)['\"]\)"]
        elif ext == ".go":
            # Matches: "nikui/utils" inside import blocks
            patterns = [r"\"([a-zA-Z0-9_\./\-]+)\""]
        else:
            return []

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                imp_path = match.group(1)
                # Keep only what looks like a local internal import
                if any(pkg in imp_path for pkg in ["nikui", "./", "../"]):
                    imports.append(imp_path)
        return list(set(imports))

    def run_stage(self, eligible_files):
        print("\n--- [Stage 5/5] Dependency & Coupling Analysis ---", file=sys.stderr)
        
        # 1. Build Graph
        for file_path in eligible_files:
            imports = self.extract_imports(file_path)
            self.outgoing_edges[file_path] = imports
            for imp in imports:
                self.incoming_edges[imp].append(file_path)

        findings = []
        HUB_THRESHOLD = 8 # Files that import too many things
        GOD_THRESHOLD = 15 # Files that are imported by too many things

        # 2. Analyze Outgoing (Hubs / Message Chains)
        for file_path, links in self.outgoing_edges.items():
            if len(links) > HUB_THRESHOLD:
                findings.append({
                    "tool": "DependencyEngine",
                    "file_path": file_path,
                    "line": 1,
                    "category": "Architectural & Design Flaw",
                    "severity": "High",
                    "description": f"Hub-like Dependency: This file imports {len(links)} modules. High coupling makes it brittle and hard to test."
                })

        # 3. Analyze Incoming (God Components / Unstable Dependencies)
        # We look for files where the 'basename' or 'nikui.path' is heavily used
        for imp_name, callers in self.incoming_edges.items():
            if len(callers) > GOD_THRESHOLD:
                # Find the actual file matching this import name
                matching_file = next((f for f in eligible_files if imp_name.replace(".", "/") in f), None)
                if matching_file:
                    findings.append({
                        "tool": "DependencyEngine",
                        "file_path": matching_file,
                        "line": 1,
                        "category": "Architectural & Design Flaw",
                        "severity": "Medium",
                        "description": f"God Component: This module is used by {len(callers)} other files. It is a central point of failure."
                    })

        return findings
