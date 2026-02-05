# LLM-Assisted Delta Debugging: A Hybrid Approach

Delta debugging finds minimal reproducers by binary search over code. Traditional tools (ddmin, lithium, pysource-minimize) are algorithmic—they don't understand what the code *does*, just whether removing chunks breaks the oracle.

I ran an experiment: what if we let an LLM do the semantic cut first, then polish with ddmin?

## The Problem with Pure Algorithmic Reduction

Tested three tools on synthetic Python bugs:

| Tool | Strategy | Strength | Weakness |
|------|----------|----------|----------|
| **pysource-minimize** | AST rewriting | 99% reduction | Rewrites bugs: `x/(x-1)` → `0/0` |
| **lithium** | Line bisection | Preserves source | Can't simplify within lines |
| **ddmin** | Line bisection | Predictable | Breaks syntax (indentation) |

The real killer: **oracle quality**. All three produced false positives on complex cases because Python tracebacks reproduce source lines verbatim:

```
  File "test.py", line 1
    count = len(items)  # TypeError: object of type 'NoneType' has no len()
IndentationError: unexpected indent
```

A grep-based oracle sees "TypeError" in the output even when the actual error is `IndentationError`. The tools don't know better.

## The Experiment

What if we use an LLM for the initial cut? LLMs understand code semantically—they know which functions are noise, which variables matter, what the bug actually is.

### Test Cases

1. **case1**: 36-line file, `ZeroDivisionError` from `x / (x - 1)`
2. **case2**: 293-line module, `TypeError: NoneType has no len()` buried deep
3. **case3**: 196-line file that must print `FIX_APPLIED` (behavior preservation)

### LLM-Only Results

```
case1: 36 → 2 lines ✓ (preserves x/(x-1))
case2: 293 → 1 line ✗ (rewrites to len(None), loses context)
case3: 196 → 9 lines ✓ (actually works)
```

LLM alone tends to over-simplify on complex cases. Same problem as pysource-minimize—it finds *a* minimal crash, not *the* minimal reproducer.

### Hybrid: LLM + ddmin

```python
def hybrid_reduce(code, oracle):
    # Phase 1: LLM semantic cut
    reduced = llm_reduce(code, error_description)
    
    # Phase 2: ddmin polish
    if oracle(reduced):
        return ddmin(reduced, oracle)
    else:
        return ddmin(code, oracle)  # fallback
```

Results:

```
case1: 36 → 2 → 2 lines (7.6s, LLM did heavy lifting)
case2: 293 → 9 → 6 lines (8.1s, PRESERVES ROOT CAUSE)
case3: 196 → 12 → 1 line (8.0s, found true minimal)
```

## The case2 Win

This is where hybrid shines. Pure LLM produced `len(None)`. Pure lithium produced 16 lines of broken syntax. Hybrid produced:

```python
def get_items():
    return None
def process_items(items):
    count = len(items)
items = get_items()
result = process_items(items)
```

Six lines that show the actual bug pattern: `get_items()` returns `None`, which flows into `len(items)`. A developer reading this understands the problem. `len(None)` teaches nothing.

## Why It Works

LLM contribution:
- Knows `helper1()`, `helper2()`, `UnusedClass` are noise
- Understands data flow: keeps `get_items()` → `items` → `process_items()`
- Preserves semantic structure, not just syntax

ddmin contribution:
- Deterministic minimality guarantee
- Finds lines LLM thought were needed but aren't
- Verifies against actual oracle

The hybrid exploits LLM's semantic understanding to get from 293→9 lines (96% cut with one API call), then ddmin's algorithmic rigor to get from 9→6 (verified minimal).

## Numbers

| Case | Original | LLM only | Hybrid | lithium | pysource |
|------|----------|----------|--------|---------|----------|
| case1 | 36 | 2 ✓ | 2 ✓ | 2 ✓ | 1 (rewrites) |
| case2 | 293 | 1 (rewrites) | **6 ✓** | 16 (broken) | 1 (rewrites) |
| case3 | 196 | 9 | 1 ✓ | 6 | 1 (crashes) |

Wall time: ~8s per case (dominated by LLM call). Not faster than pure lithium, but **correct where others fail**.

Oracle calls: LLM does 1 "semantic oracle" call, ddmin adds 2-45 verification calls. Traditional tools do 27-240 calls.

## Implications for preduce

Building a delta debugger? Consider:

1. **LLM first pass**: One API call to cut 90%+ of noise
2. **Algorithmic polish**: ddmin/lithium for guaranteed minimality
3. **Structured oracles**: Parse exception types, don't grep strings
4. **Parallelism**: The oracle calls (not LLM) dominate; parallelize them

The LLM doesn't replace the algorithm—it makes the algorithm's job tractable. 293 lines is painful for ddmin. 9 lines is trivial.

## Code

The hybrid reducer (~80 lines):

```python
def llm_reduce(code: str, error_desc: str) -> str:
    prompt = f"""Given this Python file that should: {error_desc}
```python
{code}
```
Produce MINIMAL code that still satisfies: {error_desc}
- Output ONLY code in a single block
- Preserve root cause, don't rewrite
"""
    return call_claude(prompt)

def hybrid_reduce(filepath: str, error_desc: str, oracle_cmd: str):
    original = Path(filepath).read_text()
    
    # Phase 1: LLM semantic cut
    llm_result = llm_reduce(original, error_desc)
    if not run_oracle(llm_result, oracle_cmd):
        llm_result = original  # fallback
    
    # Phase 2: ddmin polish
    return ddmin(llm_result.splitlines(), 
                 lambda lines: run_oracle('\n'.join(lines), oracle_cmd))
```

Run it:
```bash
python hybrid.py crash.py "crash with ZeroDivisionError" \
    "python /tmp/test.py 2>&1 | grep -q ZeroDivisionError"
```

## Real-World Validation: Numba and CPython

Tested on actual bugs from production codebases:

| Codebase | Lines | Bug | LLM Fix | Actual Fix | Result |
|----------|-------|-----|---------|------------|--------|
| Numba (620K) | #10357 readonly | `readonly=False` | `readonly=False` | ✅ Identical |
| Numba (620K) | #10373 CUDA attr | `self._reload_init = set()` | same | ✅ Identical |
| CPython (2.2M) | gh-143423 bool | `not self.all_threads` | refactored | ✅ More minimal |
| CPython (2.2M) | gh-144307 refleak | `Py_DECREF(key)` | same | ✅ Identical |

On the CPython profiler bug, LLM produced a **1-token fix** (`bool` → `not`) while the actual PR did a larger refactor. Both correct, LLM's was smaller.

## Where Pure LLM Fails

Tested a data race bug (gh-144295) in CPython's dict implementation:

**LLM's fix:**
```c
if (IS_DICT_SHARED(mp) && dk->dk_kind == DICT_KEYS_UNICODE) {
```

**Actual fix:**
```c
if (_Py_IsOwnedByCurrentThread((PyObject *)mp) || IS_DICT_SHARED(mp)) {
    PyDictKeysObject *dk = _Py_atomic_load_ptr_acquire(&mp->ma_keys);
    if (dk->dk_kind == DICT_KEYS_UNICODE) {
```

LLM understood the concept but:
- Placed check AFTER loading `dk` (still racy)
- Missed thread ownership optimization
- Dismissed the optimization as "complexity"

**Key insight:** LLM fails when it needs:
- Codebase patterns it hasn't seen in the snippet
- Runtime verification (thread sanitizers, tests)
- Historical context (how were similar bugs fixed?)

## ddmin Solves Minimality, Not Correctness

| Problem | ddmin helps? | What helps? |
|---------|-------------|-------------|
| LLM over-engineers (too much code) | ✅ Yes | ddmin removes unnecessary parts |
| LLM under-engineers (incomplete fix) | ❌ No | Tools, search, iteration |
| LLM gets logic wrong | ❌ No | Tests, verification |

For the data race, LLM's fix was *incomplete*, not *over-engineered*. It needed MORE code, not less. ddmin would make it worse.

## Tool-Augmented Workflow

For hard bugs, pure LLM isn't enough. The full pipeline:

```
┌─────────────────────────────────────────────────────────┐
│  1. LLM proposes fix                                    │
│  2. Tests/sanitizers verify ──────► FAIL? Loop back     │
│  3. Search similar patterns ──────► Refine fix          │
│  4. Tests pass                                          │
│  5. THEN ddmin minimizes if over-engineered             │
└─────────────────────────────────────────────────────────┘
```

Tools that help LLM get correct fixes:

| Tool | How it helps |
|------|-------------|
| **Code search** | "Show other uses of `IS_DICT_SHARED`" → LLM sees patterns |
| **Git history** | "How was this function modified?" → context |
| **Thread sanitizer** | Verify race is actually fixed |
| **Test suite** | Validate correctness before minimizing |

ddmin is the **last step**, not the correction mechanism. It's for trimming fat after the fix is correct.

## Tool-Augmented LLM Fixes Complex Bugs

Built and tested a generalizable pipeline (`tools/bugfixer.py`):

```bash
python bugfixer.py --repo ~/cpython --bug "data race in _PyDict_GetMethodStackRef" \
    --file Objects/dictobject.c --func _PyDict_GetMethodStackRef
```

### How It Works

```
1. Extract buggy function from file
2. LLM analyzes bug → suggests search terms
3. grep codebase for similar patterns
4. LLM generates fix with pattern context
5. (Optional) Run tests, iterate on failure
```

### Results on CPython Data Race (gh-144295)

**Without tool augmentation (pure LLM):**
```c
ensure_shared_on_read(mp);  // WRONG: comment says we can't call this
PyDictKeysObject *dk = _Py_atomic_load_ptr_acquire(&mp->ma_keys);
```

**With tool augmentation (search + constraints):**
```c
if (_Py_IsOwnedByCurrentThread((PyObject *)mp) || IS_DICT_SHARED(mp)) {
    PyDictKeysObject *dk = _Py_atomic_load_ptr_acquire(&mp->ma_keys);
    // ... rest of fast path ...
}
```

**Actual merged fix:** Identical to tool-augmented output.

The pipeline found patterns like `_Py_IsOwnedByCurrentThread`, `IS_DICT_SHARED` in the codebase, showed them to the LLM, and the LLM correctly applied the pattern.

### Tested on Second Bug (gh-142555)

Null pointer dereference in array module via re-entrant `__index__`:

**LLM fix (with patterns):**
```c
if (i >= 0) {
    if (ap->ob_item == NULL || i >= Py_SIZE(ap)) {
        PyErr_SetString(PyExc_IndexError, "array assignment index out of range");
        return -1;
    }
    ((char *)ap->ob_item)[i] = (char)x;
}
```

**Actual fix:** Uses a macro for DRY, but same logic. LLM got the semantics right.

### Key Insight

Pure LLM fails on complex bugs because it doesn't see:
- Codebase patterns (how do similar functions handle this?)
- Constraints (comments say "can't do X here")
- Git history (how were similar bugs fixed?)

Search tools bridge this gap. The LLM doesn't need to memorize CPython's threading model—it just needs to see how the codebase does it.

## Open Questions

- Can we auto-extract constraints from comments/docs?
- How do we handle multi-file bugs?
- Can we parallelize pattern search and test runs?

## Combined Tool: Fix + Minimize

The full pipeline in `tools/fix_and_minimize.py`:

```bash
python fix_and_minimize.py \
  --repo ~/cpython \
  --bug "data race in dict lookup" \
  --file Objects/dictobject.c \
  --func _PyDict_GetMethodStackRef \
  --test "make test"
```

**Pipeline:**
```
┌────────────────────────────────────────────────────────┐
│ PHASE 1: FIX                                           │
│   1. Extract function                                  │
│   2. Search patterns (grep codebase)                   │
│   3. LLM generates fix with context                    │
│   4. Run tests → iterate on failure                    │
├────────────────────────────────────────────────────────┤
│ PHASE 2: MINIMIZE                                      │
│   5. Diff buggy vs fixed → list changed lines          │
│   6. ddmin on changed lines (remove unnecessary)       │
│   7. Verify minimal patch still passes tests           │
└────────────────────────────────────────────────────────┘
```

**Example output:**
```
--- LLM Fix (5 changed lines) ---
+    if (_Py_IsOwnedByCurrentThread(...) || IS_DICT_SHARED(mp)) {
+        // ... comment explaining why ...
         PyDictKeysObject *dk = ...
+    }

--- Minimal Fix (2 changed lines) ---
+    if (_Py_IsOwnedByCurrentThread(...) || IS_DICT_SHARED(mp)) {
         PyDictKeysObject *dk = ...
+    }

Reduction: 5 → 2 changed lines
```

The minimizer strips comments and other non-essential changes while preserving correctness.

## Conclusion

| Scenario | Approach |
|----------|----------|
| Simple bugs | Pure LLM works |
| Over-engineered fixes | LLM + ddmin |
| Hard bugs (races, leaks) | LLM + tools + tests + iteration |
| Minimal patches | ddmin after fix is correct |

The experiment shows LLM-assisted fixing is viable for most bugs. For hard bugs, add tools and verification loops. ddmin remains valuable but solves a different problem than correctness.

---

*2026-02-05. Tested on Numba (620K lines) and CPython (2.2M lines) with Claude CLI.*
