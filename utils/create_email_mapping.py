import pandas as pd
import json
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

def create_mapping(grades_csv: str, output_path: str):
    """
    Parse Canvas Grades CSV and create SIS User ID -> Email mapping.
    
    Args:
        grades_csv: Path to Canvas Grades CSV export
        output_path: Path to write JSON output
    """
    try:
        # Read the Grades CSV
        # Note: Canvas data usually starts on row 0, but sometimes has header stuff.
        # Based on user's file inspection:
        # Row 0: Headers (Student, ID, SIS User ID, SIS Login ID, ...)
        # Row 1-2: Metadata (Points Possible, etc) - we should filter these out
        
        df = pd.read_csv(grades_csv)
        
        # Determine valid rows: Real students have numeric IDs usually, or at least valid SIS Login IDs
        # We need "SIS User ID" (e.g. UW108U211) and "SIS Login ID" (e.g. user@wisc.edu)
        
        # Filter out rows where "SIS User ID" or "SIS Login ID" is NaN
        # Also, sometimes the first few rows after header are stats, so we drop them if IDs are missing
        
        valid_students = df.dropna(subset=['SIS User ID', 'SIS Login ID'])
        
        mapping = {}
        for _, row in valid_students.iterrows():
            sis_id = str(row['SIS User ID']).strip()
            email = str(row['SIS Login ID']).strip().lower()
            
            # Simple validation
            if sis_id and email:
                mapping[sis_id] = email
                
        # Write to JSON
        with open(output_path, 'w') as f:
            json.dump(mapping, f, indent=2)
            
        console.print(Panel(f"[green]Successfully created mapping![/green]\n"
                          f"Source: {grades_csv}\n"
                          f"Output: {output_path}\n"
                          f"Mapped Students: {len(mapping)}",
                          title="Mapping Complete"))
                          
    except Exception as e:
        console.print(f"[red]Error creating mapping:[/red] {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create SISID -> Email mapping from Canvas Grades CSV")
    parser.add_argument("grades_csv", help="Path to Canvas Grades CSV file")
    parser.add_argument("--output", "-o", default="student_emails.json", help="Output JSON file path")
    
    args = parser.parse_args()
    
    create_mapping(args.grades_csv, args.output)
