import os
import re
import sys
from collections import defaultdict


class DependencyEngine:
    def __init__(self, config):
        self.config = config
        self.outgoing_edges = defaultdict(list)
        self.incoming_edges = defaultdict(list)
        self.eligible_paths = set()

    def _normalize_import(self, imp_path):
        """Converts module-style dots to path-style slashes."""
        return imp_path.replace(".", "/")

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
            # Matches: import bff.handlers OR from shared import utils
            patterns = [
                r"^import\s+([a-zA-Z0-9_\.]+)",
                r"^from\s+([a-zA-Z0-9_\.]+)\s+import",
            ]
        elif ext in [".js", ".ts", ".tsx"]:
            # Matches: import { x } from './utils' OR require('../api')
            patterns = [r"from\s+['\"](.*?)['\"]", r"require\(['\"](.*?)['\"]\)"]
        elif ext == ".go":
            # Matches: "github.com/org/repo/pkg" inside import blocks
            patterns = [r"\"([a-zA-Z0-9_\./\-]+)\""]
        else:
            return []

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                imp_path = match.group(1)

                # DYNAMIC LOCAL DETECTION:
                # 1. Direct relative indicators (JS/TS/Go)
                if any(ind in imp_path for ind in ["./", "../"]):
                    imports.append(imp_path)
                    continue

                # 2. Check if the module path exists within our project files (Python/Go)
                normalized = self._normalize_import(imp_path)
                # Does any eligible file start with this path?
                if any(p.startswith(normalized) or normalized in p for p in self.eligible_paths):
                    imports.append(imp_path)

        return list(set(imports))

    def run_stage(self, eligible_files):
        print("\n--- [Stage 5/5] Dependency & Coupling Analysis ---", file=sys.stderr)

        # Reset state so run_stage is idempotent
        self.outgoing_edges = defaultdict(list)
        self.incoming_edges = defaultdict(list)

        # Build a fast lookup set of all files in the project
        self.eligible_paths = {os.path.normpath(f) for f in eligible_files}

        # 1. Build Graph
        for file_path in eligible_files:
            imports = self.extract_imports(file_path)
            self.outgoing_edges[file_path] = imports
            for imp in imports:
                self.incoming_edges[imp].append(file_path)

        findings = []
        HUB_THRESHOLD = 8  # Files that import too many things
        GOD_THRESHOLD = 15  # Files that are imported by too many things

        # 2. Analyze Outgoing (Hubs)
        for file_path, links in self.outgoing_edges.items():
            if len(links) > HUB_THRESHOLD:
                findings.append(
                    {
                        "tool": "DependencyEngine",
                        "file_path": file_path,
                        "line": 1,
                        "category": "Architectural & Design Flaw",
                        "severity": "High",
                        "description": f"Hub-like Dependency: This file imports {len(links)} internal modules. High coupling makes it brittle and hard to test.",
                    }
                )

        # 3. Analyze Incoming (God Components)
        for imp_name, callers in self.incoming_edges.items():
            if len(callers) > GOD_THRESHOLD:
                # Find the actual file matching this import name
                normalized = self._normalize_import(imp_name)
                matching_file = next(
                    (f for f in eligible_files if normalized in f), None
                )
                if matching_file:
                    findings.append(
                        {
                            "tool": "DependencyEngine",
                            "file_path": matching_file,
                            "line": 1,
                            "category": "Architectural & Design Flaw",
                            "severity": "Medium",
                            "description": f"God Component: This module is used by {len(callers)} other files. It is a central point of failure and heavily coupled.",
                        }
                    )

        return findings
