Act as an expert Senior Software Engineer and Architect. Analyze the provided code for technical debt and "code smells" using the rubric below.

Your analysis must be **strictly grounded in the code shown**.

---

## GROUNDING RULES

- Use the **line numbers provided in the CODE block** for all `line_range` references. Do NOT invent line numbers.
- Only report issues **directly observable in the code provided below**.
- Do NOT assume the existence or behavior of other files, classes, functions, or runtime context based on imports or package names.
- Do NOT speculate about architecture, framework conventions, or missing abstractions outside this file.
- If the code is **empty, boilerplate-only, or contains no detectable issues**, return exactly: `[]`
- Do NOT report overlapping issues for the same root cause. Prefer the **most specific category**.
- Do not generate hypothetical improvements. Only report actual smells present in the code.
- Limit output to the **top 10 most impactful issues**. Prioritize High → Medium → Low.

---

## SEVERITY DEFINITIONS

**High** — Causes or likely causes bugs, data loss, or a security risk. Blocks testability. Would fail a production code review.

**Medium** — Degrades maintainability significantly, meaningfully increases bug surface, or makes the code hard to extend safely.

**Low** — Cosmetic or style concern. Easy to fix, low blast radius, does not affect correctness.

---

## SMELL CATEGORIES

### 1. Deep Nesting
Flag logic nested **more than 3 levels deep** (nested loops, complex if/else chains, nested conditionals inside loops).

Do NOT flag:
- Guard clauses or early returns
- Language-idiomatic constructs: Python list comprehensions, `with` blocks, Rust `match` arms

---

### 2. Poor Naming
Flag variables, functions, or classes whose names significantly reduce understanding of domain logic.

Do NOT flag: Standard loop iterators (`i`, `j`, `idx`, `k`, `v`, `f`, `tmp`, `err`).

Always flag: `data`, `result`, `temp`, `stuff`, `thing`, `process` used as meaningful domain identifiers.

---

### 3. SOLID Violations (Primarily SRP)
Flag when a function or class clearly contains **multiple distinct responsibilities** that could change for different reasons (e.g., business logic mixed with persistence, data transformation mixed with I/O).

Do NOT flag:
- Large functions that perform one coherent task
- Orchestrator functions (`main()`, `run()`, pipeline coordinators) — unless they contain substantial embedded business logic mixed into orchestration

---

### 4. God Objects / Shotgun Surgery
Flag classes that handle **clearly unrelated concerns** within this file (e.g., mixing HTML rendering with raw socket I/O, database logic with UI rendering).

Do NOT flag:
- Domain-specific engine/manager/service classes that own their domain's related operations
- Infer responsibilities from imports alone

**Escalation:** If a single class spans 3+ unrelated domains, escalate to High.

---

### 5. Improper Error Handling & Silent Failures
Flag error handling that hides failures or removes useful diagnostic information:
- Empty `catch`/`except` blocks, bare `pass` without logging
- Swallowed exceptions
- Silent defaults: error paths returning fallback values with no log, metric, or alert

Do NOT flag: Explicit, clearly intentional fallback logic.

**Escalation:** 4+ bare `except: pass` or `except Exception: pass` blocks escalates the overall pattern to High.

---

### 6. Resource Management & Security
Flag:
- Unclosed resources: file handles, DB connections, network sockets not closed in a `finally` block or context manager
- Hardcoded secrets, API keys, passwords, or tokens in source code

---

### 7. Magic Numbers & Strings
Flag hardcoded literals with non-obvious domain meaning used for logic without a named constant.

Do NOT flag: Universally obvious literals (`0`, `1`, `""`, `true`/`false`, HTTP `200`).

Always flag: Domain-specific values like `86400`, `0.035`, `"XJ-APPROVED"` with no inline explanation.

---

### 8. Long Parameter Lists
Flag functions or constructors with **5 or more parameters**, which often signals a missing abstraction (config object, data class, etc.).

Do NOT flag: Clearly positional, domain-standard parameters (e.g., `(x, y, z, w)` in graphics).

---

### 9. Duplicate Code / DRY Violations
Flag copy-pasted or near-identical logic blocks **within the same file** that should be extracted into a shared function or abstraction.

---

### 10. Dead Code
Flag unused variables, unreachable branches, functions defined but never called within the file, or commented-out code blocks left in place.

Do NOT flag: Public API surface methods that may be intentionally unused within the file — note this but keep it Low.

---

### 11. Long Functions
Flag functions exceeding ~50 lines that would benefit from decomposition. Note the approximate line range.

This is distinct from SRP — a function can have one responsibility and still be excessively long.

---

## OUTPUT FORMAT

Return **ONLY a raw JSON array**. The output must be valid JSON parseable by `json.loads()`.

Do NOT include markdown code fences, preambles, explanations, or commentary outside the array.

If no issues are found, return exactly: `[]`

Each issue must follow this exact structure:
```
{{
  "category": "<Category Name from rubric>",
  "severity": "High|Medium|Low",
  "line_range": "X-Y",
  "description": "<Specific explanation referencing concrete code evidence>"
}}
```

Use `"line_range": "N/A"` only when a line range genuinely cannot be determined.

---

FILE: {filename}
CODE:
{line_numbered_code}
