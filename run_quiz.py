#!/usr/bin/env python3
"""
Canvas Quiz PDF Generator - Main CLI

Usage:
    python run_quiz.py --quiz 5 --csv "Quiz 5.csv" --limit 5
    
Generates individual PDFs per question type per student.
"""

import asyncio
import argparse
import sys
from importlib import import_module
from pathlib import Path
from core.orchestrator import process_quiz


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate Canvas quiz PDFs by question type',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 5 students
  python run_quiz.py --quiz 5 --csv "Quiz 5 - Network Flow.csv" --limit 5
  
  # Full run (all students)
  python run_quiz.py --quiz 5 --csv "Quiz 5 - Network Flow.csv"
  
  # Generate PDFs for one specific student
  python run_quiz.py --quiz 5 --csv "Quiz 5.csv" --student "Alice Smith"
  
  # Skip zip file creation (faster for testing)
  python run_quiz.py --quiz 5 --csv "Quiz 5.csv" --limit 3 --no-zip
  
  # Force regenerate templates
  python run_quiz.py --quiz 5 --csv "Quiz 5.csv" --regenerate

  # Build only blank Gradescope templates (no CSV needed)
  python run_quiz.py --quiz 5 --templates-only

  # Skip blank template generation for a faster student-only run
  python run_quiz.py --quiz 5 --csv "Quiz 5.csv" --no-templates
        """
    )
    
    parser.add_argument(
        '--quiz',
        type=int,
        required=True,
        help='Quiz number (1-6)'
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        help='Path to Canvas CSV export (required unless --templates-only)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of students (for testing, recommended: 10 or less)'
    )
    
    parser.add_argument(
        '--student',
        type=str,
        help='Generate PDFs for specific student by name (case-insensitive, partial match)'
    )

    parser.add_argument(
        '--question',
        type=int,
        help='Generate PDFs only for a specific question number (e.g. 1 for q1)'
    )
    
    parser.add_argument(
        '--templates-only',
        action='store_true',
        help='Only generate blank Gradescope templates and skip student PDFs'
    )

    parser.add_argument(
        '--no-templates',
        action='store_true',
        help='Skip generating blank Gradescope templates'
    )

    parser.add_argument(
        '--no-zip',
        action='store_true',
        help='Skip creating zip file at the end'
    )
    
    parser.add_argument(
        '--regenerate',
        action='store_true',
        help='Force regenerate HTML templates from rubric'
    )

    parser.add_argument(
        '--no-merge',
        action='store_true',
        help='Skip merging all student PDFs into one big file'
    )

    parser.add_argument(
        '--merge-only',
        action='store_true',
        help='Skip generation and only merge existing PDFs'
    )

    parser.add_argument(
        '--exclude-student',
        action='append',
        metavar='NAME',
        dest='exclude_students',
        help='Exclude a student from the merged PDF (by name, case-insensitive partial match). '
             'Can be specified multiple times. Excluded students go into a separate overflow PDF.'
    )
    
    parser.add_argument(
        '--jobs',
        type=int,
        default=2,
        help='Number of parallel jobs (1-10, default: 2)'
    )
    
    args = parser.parse_args()
    
    if args.templates_only and args.no_templates:
        print("❌ Cannot combine --templates-only and --no-templates")
        sys.exit(1)

    if args.jobs < 1 or args.jobs > 10:
        print("❌ --jobs must be between 1 and 10")
        sys.exit(1)
    
    if not args.templates_only and not args.merge_only:
        if not args.csv:
            print("❌ --csv is required unless --templates-only or --merge-only is set")
            sys.exit(1)
        if not Path(args.csv).exists():
            print(f"❌ Error: CSV file not found: {args.csv}")
            sys.exit(1)
            
    # Auto-load email mapping
    email_mapping = None
    mapping_path = Path("configs/student_emails.json")
    
    if mapping_path.exists():
        try:
            import json
            with open(mapping_path, 'r') as f:
                email_mapping = json.load(f)
            print(f"✅ Loaded email mapping for {len(email_mapping)} students")
        except Exception as e:
            print(f"❌ Error loading {mapping_path}: {e}")
            sys.exit(1)
    else:
        print(f"\n⚠️  Email mapping not found at {mapping_path}")
        print("   Attempting to auto-generate from Grades CSV...")
        
        # Try to find a Grades CSV in the current directory or test_data
        candidates = list(Path("test_data").glob("*Grades-*.csv"))
        
        if not candidates:
             print("❌ No Grades CSV found in test_data/ matching '*Grades-*.csv'")
             print("   Please run manually: python utils/create_email_mapping.py <grades_csv>")
             # We don't exit here, just continue without email mapping? 
             # Or exit? The user said "run it automatically". It's better to fail if we can't do it.
             # But if they don't have the file, we can't do it.
             print("   Continuing without email mapping (emails will be missing)...")
        else:
            # Pick the most recent one
            best_candidate = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            print(f"   Found candidate: {best_candidate}")
            
            try:
                # Import util logic dynamically
                import sys
                sys.path.append(str(Path("utils").absolute()))
                from create_email_mapping import create_mapping
                
                # Make sure configs dir exists
                mapping_path.parent.mkdir(parents=True, exist_ok=True)
                
                create_mapping(str(best_candidate), str(mapping_path))
                
                # Reload
                import json
                with open(mapping_path, 'r') as f:
                    email_mapping = json.load(f)
                print(f"✅ Generated and loaded email mapping for {len(email_mapping)} students")
                
            except Exception as e:
                print(f"❌ Failed to auto-generate mapping: {e}")
                print("   Continuing without email mapping...")

    # Load quiz config
    try:
        config_module = import_module(f'configs.quiz{args.quiz}_config')
        config = config_module.QUIZ_CONFIG
    except ImportError as e:
        print(f"❌ Error: configs/quiz{args.quiz}_config.py not found")
        print(f"   Create it by copying configs.example/quiz_config_template.py")
        print(f"   Error details: {e}")
        sys.exit(1)
    except AttributeError:
        print(f"❌ Error: configs/quiz{args.quiz}_config.py missing QUIZ_CONFIG variable")
        sys.exit(1)
    
    csv_path = args.csv if args.csv else None

    # Run workflow
    try:
        asyncio.run(process_quiz(
            csv_path,
            config,
            limit=args.limit,
            student_name=args.student,
            question_number=args.question,
            skip_zip=args.no_zip,
            force_regenerate=args.regenerate,
            templates_only=args.templates_only,
            generate_templates=not args.no_templates,
            jobs=args.jobs,
            skip_merge=args.no_merge,
            merge_only=args.merge_only,
            email_mapping=email_mapping,
            exclude_students=args.exclude_students,
        ))
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

