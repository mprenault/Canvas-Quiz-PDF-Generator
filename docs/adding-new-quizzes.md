# Adding New Quizzes: Workflow & Guide

This document describes the process of adding Quiz 6 (Intractability) support to the system, including hurdles faced and solutions. It serves as a guide for adding future quizzes.

## Table of Contents
1. [Investigation Phase](#investigation-phase)
2. [Key Discoveries](#key-discoveries)
3. [Implementation Steps](#implementation-steps)
4. [Common Pitfalls](#common-pitfalls)
5. [Step-by-Step Guide for New Quizzes](#step-by-step-guide-for-new-quizzes)

---

## Investigation Phase

### Understanding the CSV Structure

The first step was analyzing the Canvas CSV export to understand its column structure. Key investigation commands:

```python
import pandas as pd
df = pd.read_csv('test_data/Quiz 6 - Intractability Student Analysis Report.csv')

# List all columns with their indices
for i, col in enumerate(df.columns):
    col_preview = str(col)[:80].replace('\n', ' ')
    print(f'{i:3}: {col_preview}')
```

**Quiz 6 CSV Structure Discovered:**
- Columns 0-10: Student metadata (Name, ID, SISID, etc.)
- Column 11: Question 1 Part A (variant-specific)
- Column 16: "Part B: Provide the if part..." (SHARED across all variants)
- Column 21: "Part C: Provide the only-if part..." (SHARED across all variants)
- Column 26: Question 2 Part A
- ... and so on for all 11 variants

### Detecting Student Variants

To find which variant each student received:

```python
# Check which variant column has content for a student
variant_cols = {1: 11, 2: 26, 3: 31, ...}  # variant → column index

for variant, col_idx in variant_cols.items():
    val = row.iloc[col_idx]
    if pd.notna(val) and str(val).strip() not in ['', 'Not Attempted']:
        detected_variant = variant
        break
```

---

## Key Discoveries

### Quiz 5 vs Quiz 6 Differences

| Aspect | Quiz 5 | Quiz 6 |
|--------|--------|--------|
| Question Groups | 2 (Q1: Network Flow, Q2: Bipartite Matching) | 1 (Q1: Reductions) |
| Variants per Group | 12 | 11 |
| Variant Tag Format | `"1.1"`, `"1.2"`, `"2.3"` (X.Y format) | `"1."`, `"2."`, `"10."` (X. format) |
| Parts per Question | Q1: 2 parts, Q2: 3 parts | 3 parts (A, B, C) |
| Shared Columns | Hardcoded patterns | Config-driven patterns |

### The Variant Tag Format Problem

**Quiz 5 columns:** `"1.5 Consider the following graph..."` → Tag: `1.5`
**Quiz 6 columns:** `"1. You will show that Problem P..."` → Tag: `1.`

The existing regex `r'^(\d+\.\d+)'` only matched Quiz 5's format. Quiz 6 needed `r'^(\d+\.)\s'`.

### The Shared Column Detection Problem

**Initial bug:** Pattern matching `'part b:' in col_text` matched column 71 (which contained "Part B:" in its question description), not the actual Part B column (16).

**Solution:** Use `col_text.startswith(pattern)` instead of `pattern in col_text`.

### The LaTeX Algorithm Parsing Problem

Previous attempts tried to convert LaTeX `algorithm2e` environments using regex, which failed due to:
- Nested braces in math expressions
- Regex can't handle balanced delimiters

**Solution:** Use screenshots of the algorithm blocks as images instead of parsing LaTeX.

---

## Implementation Steps

### 1. Created Quiz 6 Config (`configs/quiz6_config.py`)

```python
QUIZ_CONFIG = {
    'quiz_id': 6,
    'quiz_name': 'Intractability',
    'abbr': 'intr',
    'rubric_folder': 'quiz6',
    
    'question_groups': [{
        'id': 'q1',
        'name': 'Reductions',
        'variant_tags': ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.', '11.'],
        'num_parts': 3,
        'num_versions': 11,
        'points': 9,
        'page_break': 'each-part',
        'image_map': {
            1: 'question1.png',
            2: 'question2.png',
            # ... etc
        }
    }],
    
    # NEW: Config-driven shared column detection
    'shared_patterns': {
        'q1_b': 'part b:',
        'q1_c': 'part c:'
    }
}
```

### 2. Updated CSV Parser (`core/csv_parser.py`)

**Changes to `_find_variant_columns()`:**
```python
# Before: Only matched X.Y format
match = re.match(r'^(\d+\.\d+)', col_text)

# After: Try both formats
match = re.match(r'^(\d+\.\d+)', col_text)  # Quiz 5: "1.1"
if not match:
    match = re.match(r'^(\d+\.)\s', col_text)  # Quiz 6: "1. "
```

**Changes to `_find_shared_subpart_columns()`:**
```python
# NEW: Check config for shared_patterns first
if 'shared_patterns' in self.config:
    for key, pattern in self.config['shared_patterns'].items():
        if col_text.startswith(pattern.lower()):  # STARTSWITH, not IN
            shared[key] = col_idx
    return shared

# FALLBACK: Hardcoded Quiz 5 patterns (backward compatibility)
if 'partition' in col_text and 'minimum' in col_text:
    shared['q1_b'] = col_idx
# ... etc
```

### 3. Created HTML Template (`templates/quiz6/q1_template.html`)

**Decision: Manual Creation vs. `rubric_converter.py`**

For Quiz 6, I chose to create the HTML template **manually** instead of using `core/rubric_converter.py`. Here's why:

**Why Manual Creation for Quiz 6:**
1. **Complex LaTeX (`algorithm2e`)** - The rubric contained `\algorithm2e` pseudo-code blocks that Pandoc couldn't convert properly. Previous attempts resulted in garbled output like:
   ```
   \ell \gets 0 X' \gets X \phi' \gets \phi For Each clause...
   ```
2. **Full Question Screenshots** - The user decided to use screenshots of the entire question (including algorithm) as images, making most of the LaTeX parsing unnecessary.
3. **Simpler Structure** - With images replacing the complex content, the template was just: image → solutions → placeholders. Manual creation was faster than debugging converter issues.

**When to Use `rubric_converter.py`:**
- LaTeX contains only standard elements (math, tables, lists, figures with `\includegraphics`)
- No `algorithm2e`, `tikzpicture`, or other complex environments
- You want automatic extraction of question sections by line range
- The rubric has many versions and manual creation would be tedious

**When to Create Templates Manually:**
- LaTeX has complex environments that break Pandoc
- You're using screenshots for problem statements
- The structure is simple/repetitive (copy-paste with modifications)
- You need precise control over the HTML output

**Using `rubric_converter.py` (when appropriate):**
```python
from core.rubric_converter import convert_rubric_to_templates, save_templates
from configs.quizN_config import QUIZ_CONFIG

templates = convert_rubric_to_templates(QUIZ_CONFIG)
save_templates(templates, QUIZ_CONFIG['quiz_id'])
```

The converter handles:
- Extracting LaTeX sections by line range
- Converting to HTML via Pandoc
- Replacing TikZ with images (via `image_map`)
- Adding `question-version` wrappers and answer placeholders
- Copying images to the templates folder

---

**Manual Template Structure** (used for Quiz 6):

```html
<div class="question-version" data-group="q1" data-version="1">
  <h1>Question 1: Reduction from 3SAT to Monotone-3SAT</h1>
  <img class="question-image" src="images/question1.png"/>
  
  <h2 class="page-break">Part A: Show that Monotone-3SAT ∈ NP</h2>
  <blockquote><strong>Solution:</strong> ...</blockquote>
  <div class="student-answer-section" data-part="a">
    <h3>Student Answer (Part A):</h3>
    <div class="answer-placeholder">{{PART_A}}</div>
  </div>
  
  <!-- Part B and C follow same pattern -->
</div>
```

### 4. Set Up Images

```bash
# Copy question screenshots to templates folder
mkdir -p templates/quiz6/images
cp rubrics/quiz6/images/*.png templates/quiz6/images/
```

---

## Common Pitfalls

### 1. Pattern Matching Too Loose
**Problem:** `'part b:' in col_text` matches any column containing "Part B:" anywhere in its text.
**Solution:** Use `col_text.startswith('part b:')` for columns that BEGIN with the pattern.

### 2. Regex Can't Parse Nested LaTeX
**Problem:** Trying to extract `\Input{...}` with regex fails when content has nested braces like `\{x_1, x_2\}`.
**Solution:** Don't parse—use screenshots or let Pandoc handle it.

### 3. Forgetting Backward Compatibility
**Problem:** Modifying core parsing logic breaks existing quizzes.
**Solution:** 
- Add new config options (like `shared_patterns`)
- Keep fallback to existing hardcoded logic
- Test both old and new quizzes after changes

### 4. Wrong Column Index for Shared Columns
**Problem:** Debug output shows `{'q1_b': 71, 'q1_c': 71}` (same column twice).
**Solution:** Check that pattern matching is specific enough to find the RIGHT columns.

### 5. Template Missing Required Structure
**Problem:** PDF generation fails or shows wrong content.
**Solution:** Ensure template has:
- `<div class="question-version" data-version="N">` wrappers
- `{{PART_A}}`, `{{PART_B}}`, `{{PART_C}}` placeholders
- `<div class="student-answer-section" data-part="a/b/c">` structure

---

## Step-by-Step Guide for New Quizzes

### Step 1: Analyze the CSV

```python
import pandas as pd
df = pd.read_csv('path/to/new_quiz.csv')

# 1. List all columns
for i, col in enumerate(df.columns):
    print(f'{i:3}: {str(col)[:60]}')

# 2. Find variant columns (contain question text)
# 3. Find shared columns (Part B, Part C, etc.)
# 4. Check one student's data to verify column mapping
```

**Key questions to answer:**
- How many question groups? (e.g., Q1, Q2)
- How many variants per group?
- What format are variant tags? (`X.Y` or `X.`)
- Which columns are shared across variants?
- How many parts per question?

### Step 2: Prepare Images

If the rubric has complex LaTeX (algorithms, TikZ diagrams):

1. Compile the LaTeX rubric to PDF
2. Take screenshots of each question's problem statement
3. Save as `rubrics/quizN/images/questionX.png`

### Step 3: Create Config File

Create `configs/quizN_config.py`:

```python
QUIZ_CONFIG = {
    'quiz_id': N,
    'quiz_name': 'Quiz Name',
    'abbr': 'abbr',  # Short name for filenames
    'rubric_folder': 'quizN',
    
    'question_groups': [
        {
            'id': 'q1',
            'name': 'Question Group Name',
            'variant_tags': ['1.', '2.', ...],  # Match CSV column prefixes
            'num_parts': 3,  # A, B, C
            'num_versions': 11,
            'points': 9,
            'page_break': 'each-part',
            'image_map': {
                1: 'question1.png',
                2: 'question2.png',
                # ...
            }
        }
    ],
    
    # If shared columns don't match Quiz 5 patterns:
    'shared_patterns': {
        'q1_b': 'part b:',  # Pattern that column header STARTS WITH
        'q1_c': 'part c:'
    }
}
```

### Step 4: Update Parser (If Needed)

If the new quiz has a different variant tag format, update `_find_variant_columns()` in `core/csv_parser.py`:

```python
# Add new pattern matching
match = re.match(r'^NEW_PATTERN', col_text)
if match and tag in all_expected_tags:
    variant_cols[tag] = col_idx
```

**Important:** Always keep existing patterns for backward compatibility.

### Step 5: Create HTML Template

Option A: Use `rubric_converter.py` if LaTeX is simple:
```python
from core.rubric_converter import convert_rubric_to_templates, save_templates
from configs.quizN_config import QUIZ_CONFIG

templates = convert_rubric_to_templates(QUIZ_CONFIG)
save_templates(templates, QUIZ_CONFIG['quiz_id'])
```

Option B: Create manually for complex LaTeX:
```html
<!DOCTYPE html>
<html>
<head>
  <!-- Copy styles from existing template -->
</head>
<body>
  <!-- For each version: -->
  <div class="question-version" data-group="q1" data-version="1">
    <h1>Question Title</h1>
    <img class="question-image" src="images/question1.png"/>
    
    <h2 class="page-break">Part A: ...</h2>
    <blockquote><strong>Solution:</strong> ...</blockquote>
    <div class="student-answer-section" data-part="a">
      <h3>Student Answer (Part A):</h3>
      <div class="answer-placeholder">{{PART_A}}</div>
    </div>
    
    <!-- Repeat for Parts B, C, etc. -->
  </div>
</body>
</html>
```

### Step 6: Copy Images to Templates

```bash
mkdir -p templates/quizN/images
cp rubrics/quizN/images/*.png templates/quizN/images/
```

### Step 7: Set Up Email Mapping (Optional but Recommended)

For student emails to appear on PDFs, you need a mapping file. This is typically auto-generated, but you can set it up manually:

**Automatic (Recommended):**
- Place a Canvas Grades CSV in `test_data/` (e.g., `2024-12-01T1234_Grades-CS_577.csv`)
- The system will auto-detect and generate `configs/student_emails.json` on first run

**Manual:**
```bash
# Generate from a specific Grades CSV
python utils/create_email_mapping.py "test_data/Grades-CS_577.csv" -o configs/student_emails.json
```

**Verify mapping exists:**
```bash
cat configs/student_emails.json | head -5
# Should show: {"UW108U211": "student@wisc.edu", ...}
```

**Note:** If no email mapping exists, PDFs will still generate but without email addresses in the header. The CLI will show a warning.

### Step 8: Test

```bash
# Test parsing only
python3 -c "
from configs.quizN_config import QUIZ_CONFIG
from core.csv_parser import CanvasCSVParser

parser = CanvasCSVParser('path/to/quiz.csv', QUIZ_CONFIG)
students = parser.get_student_data(limit=5)
for s in students:
    parser.print_student_summary(s)
"

# Test full pipeline
python3 run_quiz.py --quiz N --csv "path/to/quiz.csv" --limit 3 --no-zip
```

### Step 9: Verify Output

Check generated PDFs:
- Correct variant shown for each student?
- All parts (A, B, C) have correct student answers?
- Images rendering properly?
- Page breaks in right places?
- Student emails showing in header? (if email mapping configured)

---

## Summary

The key insight from Quiz 6 setup: **the system is config-driven, but the parser needed extension** to handle different CSV formats. The pattern is:

1. **Investigate** the CSV structure thoroughly before coding
2. **Extend** (don't replace) existing logic for backward compatibility
3. **Use config** to define quiz-specific patterns
4. **Use images** for complex LaTeX that Pandoc can't handle
5. **Test both** old and new quizzes after any parser changes

When in doubt, print the actual column indices and data to verify your assumptions match reality.

