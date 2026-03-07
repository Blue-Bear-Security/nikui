Act as an expert Senior Software Engineer. You are given two snippets of code that have been flagged as structurally similar. 

Your task is to determine if these snippets represent **Copy-Pasted Technical Debt** or are simply **Incidental Similarity** (like boilerplate, standard CLI patterns, or common data structures).

### DEFINITIONS:
- **DUPLICATE**: The core logic, algorithms, or sequence of operations are effectively the same. Copy-pasting this logic violates the DRY (Don't Repeat Yourself) principle. Renamed variables or slightly different comments still count as a duplicate.
- **UNIQUE**: The functions serve different purposes or are standard architectural boilerplate (like different `main` functions, simple `__init__` constructors, or generic error handlers) that happen to look similar.

### OUTPUT RULES:
- Return ONLY a raw JSON object.
- Structure: {{ "status": "DUPLICATE|UNIQUE", "reason": "1-sentence technical explanation" }}

---
CODE BLOCK A (File: {file_a}):
{code_a}

---
CODE BLOCK B (File: {file_b}):
{code_b}
