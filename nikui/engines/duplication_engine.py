import os
import sys
import re
import ast
import copy
from dataclasses import dataclass, field
from itertools import combinations
from simhash import Simhash
from nikui.utils import is_excluded

class UniversalNormalizer:
    """Normalizes code text for any language using regex."""
    
    @staticmethod
    def clean_code(text, extension):
        # 1. Remove comments
        if extension in ['.py']:
            text = re.sub(r'#.*', '', text)
        else: # Go, JS, TS
            text = re.sub(r'//.*', '', text)
            text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # 2. Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 3. Very basic identifier anonymization (alphanumeric words > 3 chars)
        # This helps catch renamed variables without needing a full parser
        # text = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b', 'v', text)
        
        return text

class DuplicationEngine:
    def __init__(self, config):
        self.config = config
        self.threshold = config.get("duplication", {}).get("threshold", 0.85)
        self.min_lines = config.get("duplication", {}).get("min_lines", 6)
        self.supported_exts = [".py", ".go", ".ts", ".tsx", ".js"]

    def _get_fingerprint(self, text):
        shingle_size = 4
        grams = [text[i:i + shingle_size] for i in range(max(1, len(text) - shingle_size + 1))]
        return Simhash(grams)

    def extract_blocks(self, file_path):
        """Extracts significant code blocks (functions/classes) from a file."""
        ext = os.path.splitext(file_path)[1]
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except: return []

        if len(lines) < self.min_lines:
            return []

        # For Python, we can still use AST for better precision if it parses
        if ext == ".py":
            return self._extract_python_ast(file_path, "".join(lines))
        
        # For others (Go, TS), we use a sliding window of lines or simple bracket matching
        # For now, let's treat the whole file as one block if it's small, 
        # or split by top-level double-newlines for a generic approach.
        content = "".join(lines)
        normalized = UniversalNormalizer.clean_code(content, ext)
        
        return [{
            "name": os.path.basename(file_path),
            "file": file_path,
            "lineno": 1,
            "source_lines": len(lines),
            "hash": self._get_fingerprint(normalized)
        }]

    def _extract_python_ast(self, file_path, source):
        try:
            tree = ast.parse(source)
            records = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    lines = end - node.lineno + 1
                    if lines < self.min_lines: continue
                    
                    # Dump AST as a proxy for normalized text
                    norm = ast.dump(node) 
                    records.append({
                        "name": node.name,
                        "file": file_path,
                        "lineno": node.lineno,
                        "source_lines": lines,
                        "hash": self._get_fingerprint(norm)
                    })
            return records
        except: return []

    def run_stage(self, scan_dirs):
        print("\n--- [Stage 4/4] Multi-Language Duplication Analysis ---", file=sys.stderr)
        all_blocks = []
        for d in scan_dirs:
            if not os.path.isdir(d): continue
            for root, _, files in os.walk(d):
                if any(ex in root.split(os.sep) for ex in self.config.get("exclusions", {}).get("directories", [])):
                    continue
                for file in files:
                    ext = os.path.splitext(file)[1]
                    if ext in self.supported_exts:
                        path = os.path.join(root, file)
                        if not is_excluded(path, self.config):
                            all_blocks.extend(self.extract_blocks(path))

        # Find groups
        groups = []
        seen = set()
        for i, j in combinations(range(len(all_blocks)), 2):
            if i in seen and j in seen: continue
            a, b = all_blocks[i], all_blocks[j]
            
            # Don't compare a file to itself
            if a['file'] == b['file'] and a['lineno'] == b['lineno']: continue
            
            dist = a['hash'].distance(b['hash'])
            sim = 1.0 - dist / 64
            
            if sim >= self.threshold:
                existing = next((g for g in groups if any(blk is a or blk is b for blk in g['blocks'])), None)
                if existing:
                    for blk in (a, b):
                        if blk not in existing['blocks']: existing['blocks'].append(blk)
                    existing['similarity'] = min(existing['similarity'], sim)
                else:
                    groups.append({"similarity": sim, "blocks": [a, b]})
                seen.add(i); seen.add(j)

        findings = []
        for group in groups:
            sim_pct = group['similarity'] * 100
            paths = [f"{b['file']}:{b['lineno']}" for b in group['blocks']]
            for blk in group['blocks']:
                others = [p for p in paths if p != f"{blk['file']}:{blk['lineno']}"]
                findings.append({
                    "tool": "Duplication",
                    "file_path": blk['file'],
                    "line": blk['lineno'],
                    "category": "Architectural & Design Flaw",
                    "severity": "High" if sim_pct > 98 else "Medium",
                    "description": f"Code block '{blk['name']}' is {sim_pct:.1f}% similar to code at: {', '.join(others[:3])}"
                })
        return findings
