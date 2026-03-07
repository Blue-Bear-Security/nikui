import ast
import os
import sys
import copy
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from simhash import Simhash
from nikui.utils import is_excluded

class AstNormalizer(ast.NodeTransformer):
    """Strips surface-level differences from Python ASTs."""
    def __init__(self):
        self._var_map = {}
        self._counter = 0

    def _canonical(self, name):
        if name not in self._var_map:
            self._var_map[name] = f"v{self._counter}"
            self._counter += 1
        return self._var_map[name]

    def visit_FunctionDef(self, node):
        node.name = "fn"
        node.decorator_list = []
        node.returns = None
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)):
            node.body = node.body[1:] or [ast.Pass()]
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_arg(self, node):
        node.arg = self._canonical(node.arg)
        node.annotation = None
        return node

    def visit_Name(self, node):
        node.id = self._canonical(node.id)
        return node

    def visit_AnnAssign(self, node):
        node.annotation = None
        self.generic_visit(node)
        return node

@dataclass
class FuncRecord:
    name: str
    file: str
    lineno: int
    end_lineno: int
    source_lines: int
    hash: Simhash = field(repr=False)
    normalized: str = field(repr=False)

class DuplicationFinder:
    def __init__(self, config):
        self.threshold = config.get("duplication", {}).get("threshold", 0.90)
        self.min_lines = config.get("duplication", {}).get("min_lines", 5)

    @staticmethod
    def normalize_ast(node):
        clone = copy.deepcopy(node)
        normalized = AstNormalizer().visit(clone)
        return ast.dump(normalized)

    @staticmethod
    def fingerprint(text, shingle_size=4):
        grams = [text[i:i + shingle_size] for i in range(max(1, len(text) - shingle_size + 1))]
        return Simhash(grams)

    def get_similarity(self, h1, h2, bits=64):
        return 1.0 - h1.distance(h2) / bits

    def find_groups(self, records):
        candidates = [r for r in records if r.source_lines >= self.min_lines]
        groups = []
        seen = set()

        for i, j in combinations(range(len(candidates)), 2):
            if i in seen and j in seen: continue
            a, b = candidates[i], candidates[j]
            sim = self.get_similarity(a.hash, b.hash)
            if sim >= self.threshold:
                existing = next((g for g in groups if any(r is a or r is b for r in g['functions'])), None)
                if existing:
                    for r in (a, b):
                        if r not in existing['functions']: existing['functions'].append(r)
                    existing['similarity'] = min(existing['similarity'], sim)
                else:
                    groups.append({"similarity": sim, "functions": [a, b]})
                seen.add(i); seen.add(j)
        return groups

class DuplicationEngine:
    def __init__(self, config):
        self.config = config
        self.finder = DuplicationFinder(config)

    def extract_functions(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            tree = ast.parse(source)
        except: return []

        records = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno)
                norm = self.finder.normalize_ast(node)
                records.append(FuncRecord(
                    name=node.name,
                    file=file_path,
                    lineno=node.lineno,
                    end_lineno=end,
                    source_lines=end - node.lineno + 1,
                    hash=self.finder.fingerprint(norm),
                    normalized=norm
                ))
        return records

    def run_stage(self, scan_dirs):
        print("\n--- [Stage 4/4] Code Duplication Analysis ---", file=sys.stderr)
        all_records = []
        for d in scan_dirs:
            if not os.path.isdir(d): continue
            for root, _, files in os.walk(d):
                if any(ex in root.split(os.sep) for ex in self.config.get("exclusions", {}).get("directories", [])):
                    continue
                for file in files:
                    if file.endswith(".py"):
                        path = os.path.join(root, file)
                        if not is_excluded(path, self.config):
                            all_records.extend(self.extract_functions(path))

        groups = self.finder.find_groups(all_records)
        findings = []
        for group in groups:
            sim_pct = group['similarity'] * 100
            # Report each function in the group as a finding
            paths = [f"{f.file}:{f.lineno}" for f in group['functions']]
            for fn in group['functions']:
                others = [p for p in paths if p != f"{fn.file}:{fn.lineno}"]
                findings.append({
                    "tool": "Duplication",
                    "file_path": fn.file,
                    "line": fn.lineno,
                    "category": "Architectural & Design Flaw",
                    "severity": "Medium" if sim_pct < 100 else "High",
                    "description": f"Function '{fn.name}' is {sim_pct:.1f}% similar to functions at: {', '.join(others)}"
                })
        return findings
