# Architecture & Workflow

This document outlines the architecture of the Canvas Quiz PDF Generator, detailing the pipeline that transforms unstructured Canvas CSV exports into formatted, printable PDFs with high-fidelity math rendering.

## High-Level Overview

The system operates as a data processing pipeline. It handles the complexity of students receiving different question variants while ensuring that LaTeX equations are rendered correctly using a headless browser engine.

![Architecture Diagram](https://mermaid.ink/img/CmdyYXBoIFRECiAgICBBW0NhbnZhcyBDU1YgRXhwb3J0XSAtLT58SW5wdXR8IEIoQ1NWIFBhcnNlcikKICAgIENbUXVpeiBDb25maWddIC0tPnxSdWxlc3wgQgogICAgQyAtLT58U3RydWN0dXJlfCBEKFRlbXBsYXRlIEVuZ2luZSkKICAgIAogICAgQiAtLT4gRXtPcmNoZXN0cmF0b3J9CiAgICBEIC0tPiBFCiAgICAKICAgIEUgLS0-IEZbUGFyYWxsZWwgUHJvY2Vzc2luZyBMb29wXQogICAgCiAgICBzdWJncmFwaCBQcm9jZXNzaW5nIFtQZXIgU3R1ZGVudCAvIFBlciBRdWVzdGlvbl0KICAgICAgICBGIC0tPiBHW0hUTUwgR2VuZXJhdG9yXQogICAgICAgIEcgLS0-IEhbUERGIFJlbmRlcmVyIC0gUGxheXdyaWdodF0KICAgIGVuZAogICAgCiAgICBIIC0tPnxSZW5kZXJlZCBGaWxlc3wgSVtPdXRwdXQgUERGc10KICAgIEkgLS0-fFBhY2thZ2luZ3wgSltaaXAgQ3JlYXRvcl0K)

<details>
<summary>View Mermaid Source</summary>

```mermaid
graph TD
    A[Canvas CSV Export] -->|Input| B(CSV Parser)
    C[Quiz Config] -->|Rules| B
    C -->|Structure| D(Template Engine)
    
    B --> E{Orchestrator}
    D --> E
    
    E --> F[Parallel Processing Loop]
    
    subgraph "Per Student / Per Question"
        F --> G[HTML Generator]
        G --> H[PDF Renderer (Playwright)]
    end
    
    H -->|Rendered Files| I[Output PDFs]
    I -->|Packaging| J[Zip Creator]
```
</details>

## Detailed Workflow

### 1. Initialization & Configuration
*   **Entry Point**: `run_quiz.py` serves as the CLI driver. It accepts arguments for the quiz number, input CSV, concurrency settings, and workflow control flags (`--merge-only`, `--no-merge`).
*   **Config Loading**: The system loads a specific configuration file (e.g., `configs/quiz5_config.py`). This file defines the quiz structure, including:
    *   Question groups (e.g., "Question 1").
    *   Variant definitions (e.g., variants 1.1 through 1.9).
    *   Tag mappings for parsing.

### 2. Template Management
Located in `core/orchestrator.py`.
Before processing student data, the system ensures the document "skeletons" exist.
*   **Check**: Looks for HTML templates in `templates/quiz{id}/`.
*   **Generation**: If templates are missing, `rubric_converter.py` generates them dynamically from the rubric. This ensures the PDF structure strictly follows the grading rubric.

### 3. Data Extraction (CSV Parsing)
Located in `core/csv_parser.py`.
This step handles the complexity of Canvas exports where data is sparse and column locations vary by student.
*   **Variant Detection**: Scans CSV headers for variant tags (like `1.5` or `2.3`).
*   **Student Mapping**: For each student, identifies which columns contain data to determine their assigned variant.
*   **Answer Extraction**:
    *   **Part A**: Extracted from the variant-specific column.
    *   **Parts B/C**: Extracted from shared columns (common across variants within a group).

### 4. Parallel Processing
Located in `core/orchestrator.py`.
To optimize performance, the system processes students concurrently.
*   **Concurrency**: Uses `asyncio` with a `Semaphore` to limit active jobs (default: 2, max: 10). This prevents system overload since browser rendering is memory-intensive.

### 5. Email Integration
Located in `run_quiz.py` (auto-generation) and `core/csv_parser.py` (injection).
*   **Problem**: Student analysis reports contain SIS IDs but not emails.
*   **Solution**:
    1.  **Auto-Discovery**: On start, `run_quiz.py` checks for `configs/student_emails.json`.
    2.  **Auto-Generation**: If missing, it automatically scans `test_data/` for the latest Grades CSV (which contains emails) and generates the mapping file using `utils/create_email_mapping.py`.
    3.  **Injector**: During CSV parsing, emails are injected into the student data object via a lookup from this mapping.

### 6. HTML Generation
Located in `core/html_generator.py`.
For every student and every question:
1.  Loads the generic HTML template for the question group.
2.  Injects specific student data: **Name**, **Email**, **SISID**, **Variant Number**, and **Answers**.
3.  Saves a temporary HTML file (e.g., `output/.../html/q1v5_Alice.html`).

### 7. PDF Rendering
Located in `core/pdf_generator.py`.
This step ensures visual fidelity, particularly for math equations.
*   **Engine**: Uses **Playwright** to launch a headless Chromium browser.
*   **Process**:
    1.  Loads the generated HTML.
    2.  Waits for **MathJax** to fully render LaTeX equations ($x^2$) into visual vectors.
    3.  Prints the page to PDF.
*   **Why Browser?**: Standard HTML-to-PDF tools often fail to execute the JavaScript required for MathJax, leading to broken equations.

### 8. PDF Merging
Located in `core/pdf_merger.py`.
*   **Aggregation**: Combines all individual student PDFs for a specific question group into a single "Big PDF" (e.g., `q1_merged.pdf`).
*   **Sorting**: Ensures PDFs are merged in a specific order (e.g., all Variant 1s, then Variant 2s) to facilitate organized grading.
*   **Control**: Can be skipped with `--no-merge` or run independently with `--merge-only`.

### 9. Final Packaging
Located in `core/zip_creator.py`.
*   Walks the output directory.
*   Aggregates all generated PDFs into a single ZIP file, organized by question, ready for upload to grading platforms like Gradescope.

## Key Architecture Decisions

| Component | Choice | Reason |
| :--- | :--- | :--- |
| **PDF Engine** | **Playwright (Chromium)** | Critical for rendering **MathJax/LaTeX** correctly. Standard tools like `wkhtmltopdf` or `ReportLab` cannot handle dynamic JS-based math rendering effectively. |
| **Concurrency** | **Asyncio + Semaphores** | Browser instances are resource-heavy. Asyncio manages IO-bound tasks efficiently, while semaphores prevent resource exhaustion. |
| **Parsing** | **Pandas + Regex** | Canvas CSVs are sparse grids. Pandas handles the data structure efficiently, while Regex identifies dynamic column names (e.g., `1.5: Question Text...`). |

## Directory Structure Mapping

*   `core/`: **Logic** (Orchestrator, Parser, Generators).
*   `templates/`: **Skeleton** (HTML layouts, CSS).
*   `configs/`: **Rules** (Quiz definitions, Variant mappings).
*   `output/`: **Artifacts** (Intermediate HTML, Final PDFs).
