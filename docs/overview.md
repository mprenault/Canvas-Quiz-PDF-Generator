# Codebase Overview: Canvas Quiz CSV to PDF Generator

This is a **Python CLI application** that takes a Canvas LMS quiz export (CSV) and generates individual PDF documents for each student's quiz submission, organized by question type. It's designed for grading workflows like Gradescope.

---

## 📁 Project Structure

```
canvas-quiz-csv-html-pdf/
├── run_quiz.py              # Main CLI entry point
├── core/                    # Core processing modules
│   ├── orchestrator.py      # Main workflow coordinator
│   ├── csv_parser.py        # Parses Canvas CSV exports
│   ├── rubric_converter.py  # Converts LaTeX rubrics → HTML templates
│   ├── html_generator.py    # Merges student answers into templates
│   ├── pdf_generator.py     # HTML → PDF using Playwright/Chromium
│   ├── pdf_merger.py        # Combines PDFs into one file
│   └── zip_creator.py       # Creates organized zip archives
├── configs/                 # Quiz-specific configurations (gitignored)
│   └── quizX_config.py      # Config per quiz (variant tags, line ranges, etc.)
├── configs.example/         # Template for configs
├── rubrics/                 # Source LaTeX rubric files from course
├── templates/               # Generated HTML templates (intermediate)
├── output/                  # Final output (PDFs, zips)
├── test_data/               # Sample CSV files for testing
└── utils/                   # Helper scripts
    ├── create_email_mapping.py  # Creates SIS ID → email mapping
    └── create_quiz_zip.py       # Standalone zip utility
```

---

## 🧩 Core Modules Explained

| Module | Purpose |
|--------|---------|
| **`run_quiz.py`** | CLI entry point. Parses arguments, loads config, calls orchestrator |
| **`orchestrator.py`** | Main workflow coordinator. Ties all modules together |
| **`csv_parser.py`** | `CanvasCSVParser` class extracts student names, IDs, and answers by variant |
| **`rubric_converter.py`** | Converts LaTeX rubric `.tex` files → HTML templates via Pandoc |
| **`html_generator.py`** | Injects student answers into HTML templates, hides other variants |
| **`pdf_generator.py`** | Uses Playwright (headless Chromium) to render HTML → PDF with MathJax support |
| **`pdf_merger.py`** | Merges all student PDFs into one combined file per question |
| **`zip_creator.py`** | Packages all PDFs into an organized zip file |

---

## 🔄 CLI Execution Flow

When you run:
```bash
python run_quiz.py --quiz 6 --csv "Quiz 6.csv" --limit 5
```

Here's the **step-by-step execution path**:

```
┌─────────────────────────────────────────────────────────────────┐
│                         run_quiz.py                             │
│  1. Parse CLI arguments (--quiz, --csv, --limit, etc.)          │
│  2. Load email mapping from configs/student_emails.json         │
│     └─ If missing, auto-generate from test_data/*Grades-*.csv   │
│  3. Dynamically import configs/quiz{N}_config.py                │
│  4. Call asyncio.run(process_quiz(...))                         │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   orchestrator.process_quiz()                   │
│                                                                 │
│  STEP 1: LOAD OR GENERATE TEMPLATES                             │
│  ──────────────────────────────────                             │
│  └─ load_or_generate_templates(config)                          │
│     ├─ Check if templates/quiz{N}/*.html exist                  │
│     └─ If missing or --regenerate:                              │
│        └─ rubric_converter.convert_rubric_to_templates()        │
│           ├─ Find .tex file in rubrics/quiz{N}/                 │
│           ├─ Copy images to templates/quiz{N}/images/           │
│           ├─ Extract LaTeX line ranges per question             │
│           ├─ Replace TikZ with images (if configured)           │
│           ├─ Convert to HTML via Pandoc                         │
│           └─ Add variant wrappers + answer placeholders         │
│                                                                 │
│  STEP 2: GENERATE BLANK GRADESCOPE TEMPLATES (optional)         │
│  ───────────────────────────────────────────────────            │
│  └─ generate_blank_templates(config, templates)                 │
│     └─ Creates blank PDF templates for Gradescope setup         │
│                                                                 │
│  STEP 3: PARSE CSV                                              │
│  ─────────────────                                              │
│  └─ csv_parser.CanvasCSVParser(csv_path, config, email_mapping) │
│     ├─ Detect variant columns (e.g., [1.5] tags in headers)     │
│     ├─ Find shared subpart columns (Part B, C answers)          │
│     └─ parser.get_student_data(limit=N)                         │
│        └─ Returns: [{'name': '...', 'id': '...', 'email': '...',│
│                      'q1': {'variant': 5, 'answers': {...}},    │
│                      'q2': {...}}, ...]                         │
│                                                                 │
│  STEP 4: GENERATE PDFs (parallel workers)                       │
│  ─────────────────────────────────────────                      │
│  └─ For each student (via async workers):                       │
│        For each question group:                                 │
│        ├─ html_generator.generate_student_html()                │
│        │   ├─ hide_other_variants() - keeps only student's      │
│        │   └─ insert_student_answers() - replaces placeholders  │
│        ├─ Save HTML to output/quiz{N}/{qX}_name/html/           │
│        └─ pdf_generator.generate_pdf()                          │
│            ├─ Launch headless Chromium via Playwright           │
│            ├─ Wait for MathJax rendering                        │
│            └─ Save PDF to output/quiz{N}/{qX}_name/pdf/         │
│                                                                 │
│  STEP 5: MERGE PDFs                                             │
│  ─────────────────                                              │
│  └─ pdf_merger.merge_pdfs() per question group                  │
│     └─ Creates q1_merged.pdf, q2_merged.pdf, etc.               │
│                                                                 │
│  STEP 6: CREATE ZIP                                             │
│  ─────────────────                                              │
│  └─ zip_creator.create_quiz_zip()                               │
│     └─ Creates output/quiz{N}pdfs.zip                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Diagram

```
Canvas CSV Export          LaTeX Rubric (.tex)
       │                          │
       ▼                          ▼
 ┌──────────────┐         ┌────────────────────┐
 │ csv_parser   │         │ rubric_converter   │
 │              │         │  (uses Pandoc)     │
 └──────┬───────┘         └─────────┬──────────┘
        │                           │
        │ Student data:             │ HTML templates:
        │ - name, id, email         │ - variant wrappers
        │ - variants per Q          │ - answer placeholders
        │ - answers (HTML)          │ - MathJax support
        │                           │
        ▼                           ▼
     ┌──────────────────────────────────┐
     │       html_generator             │
     │  - Merge student answers into    │
     │    the correct variant template  │
     └───────────────┬──────────────────┘
                     │
                     ▼ Complete HTML per student
     ┌──────────────────────────────────┐
     │       pdf_generator              │
     │  - Playwright (headless Chrome)  │
     │  - MathJax equation rendering    │
     └───────────────┬──────────────────┘
                     │
                     ▼ Individual PDFs
     ┌──────────────────────────────────┐
     │       pdf_merger / zip_creator   │
     │  - Merge into combined PDF       │
     │  - Package into zip              │
     └──────────────────────────────────┘
                     │
                     ▼
              output/quiz{N}/
              ├── q1_flow/
              │   ├── html/*.html
              │   ├── pdf/*.pdf
              │   └── q1_merged.pdf
              └── quiz{N}pdfs.zip
```

---

## ⚙️ Key Configuration (quiz config)

Each quiz requires a config file at `configs/quiz{N}_config.py`:

```python
QUIZ_CONFIG = {
    'quiz_id': 6,
    'quiz_name': 'Intractability',
    'rubric_folder': 'quiz6',
    'question_groups': [
        {
            'id': 'q1',
            'name': 'Reduction',
            'variant_tags': ['1.', '2.', '3.'],  # CSV column tag patterns
            'num_parts': 2,                       # Parts A, B
            'latex_line_range': (45, 500),        # Lines in .tex file
            'num_versions': 3,
            'points': 5,
            'page_break': 'same-page'             # or 'each-part'
        },
        # ... more questions
    ]
}
```

---

## 🎯 Key CLI Options

| Flag | Description |
|------|-------------|
| `--quiz N` | Quiz number (required) |
| `--csv "path"` | Path to Canvas CSV export |
| `--limit N` | Process only N students (for testing) |
| `--student "name"` | Filter to specific student |
| `--question N` | Generate only for question N |
| `--templates-only` | Only generate blank Gradescope templates |
| `--no-templates` | Skip blank template generation |
| `--no-zip` | Skip zip file creation |
| `--no-merge` | Skip merging PDFs |
| `--regenerate` | Force regenerate HTML templates from rubric |
| `--jobs N` | Number of parallel workers (1-10, default: 2) |

---

This is a well-structured pipeline designed for processing Canvas LMS quiz exports into individual, grader-ready PDFs with proper math rendering.
