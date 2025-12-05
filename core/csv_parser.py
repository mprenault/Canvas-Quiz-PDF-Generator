"""
CSV Parser: Extract student data from Canvas exports (FINAL VERSION).

Canvas CSV structure:
- Each variant has a tagged column for Part A (e.g., [1.5])
- Subparts (B, C) are in SHARED columns used by all variants
- Example: All Q1 variants use the same "partition" column for Part B
"""

import pandas as pd
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class CanvasCSVParser:
    """
    Parse Canvas quiz CSV with variant-specific Part A and shared Part B/C columns.
    """
    
    def __init__(self, csv_path: str, config: dict, email_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize parser with CSV file and quiz configuration.
        
        Args:
            csv_path: Path to Canvas CSV export
            config: Quiz configuration dict
            email_mapping: Optional dict mapping SIS User ID -> Email
        """
        self.csv_path = csv_path
        self.config = config
        self.email_mapping = email_mapping or {}
        self.df = pd.read_csv(csv_path)
        
        # Build column mappings
        self.variant_columns = self._find_variant_columns()
        self.shared_columns = self._find_shared_subpart_columns()
        
        from rich.console import Console
        console = Console()
        
        console.print(f"\n[cyan]📊 Parsed CSV:[/cyan] {Path(csv_path).name}")
        console.print(f"   [green]✓[/green] {len(self.df)} students")
        console.print(f"   [green]✓[/green] {len(self.variant_columns)} question variants found")
        console.print(f"   [green]✓[/green] {len(self.shared_columns)} shared subpart columns")
    
    def _find_variant_columns(self) -> Dict[str, int]:
        """
        Find all tagged columns (Part A for each variant).
        
        Supports two tag formats:
        - Quiz 5 style: "1.1", "1.2", "2.3" (X.Y format)
        - Quiz 6 style: "1.", "2.", "10." (X. followed by space/text)
        
        Returns:
            Dict mapping tag → column index
            Example: {'1.1': 11, '1.5': 51} or {'1.': 11, '2.': 26}
        """
        variant_cols = {}
        
        # Get expected tags from config to determine format
        all_expected_tags = []
        for group in self.config['question_groups']:
            all_expected_tags.extend(group['variant_tags'])
        
        for col_idx, col_name in enumerate(self.df.columns):
            col_text = str(col_name).strip()
            
            # Try Quiz 5 format first: X.Y at start (e.g., "1.1", "2.3")
            match = re.match(r'^(\d+\.\d+)', col_text)
            if match:
                tag = match.group(1)
                if tag in all_expected_tags:
                    variant_cols[tag] = col_idx
                continue
            
            # Try Quiz 6 format: X. followed by space (e.g., "1. You will show...")
            match = re.match(r'^(\d+\.)\s', col_text)
            if match:
                tag = match.group(1)
                if tag in all_expected_tags:
                    variant_cols[tag] = col_idx
        
        return variant_cols
    
    def _find_shared_subpart_columns(self) -> Dict[str, int]:
        """
        Find shared subpart columns (Part B, Part C).
        
        These columns are used by ALL variants within a question group.
        
        Uses config's 'shared_patterns' if available (Quiz 6 style),
        otherwise falls back to hardcoded Quiz 5 patterns.
        
        Returns:
            Dict mapping identifier → column index
            Example: {
                'q1_b': 16,  # Q1 Part B (partition question)
                'q2_b': 26,  # Q2 Part B
                'q2_c': 31   # Q2 Part C
            }
        """
        shared = {}
        
        # Check if config has shared_patterns (Quiz 6 style)
        if 'shared_patterns' in self.config:
            patterns = self.config['shared_patterns']
            for col_idx, col_name in enumerate(self.df.columns):
                col_text = str(col_name).lower().strip()
                for key, pattern in patterns.items():
                    # Match columns that START with the pattern (not just contain it)
                    # This avoids false matches like "1. You will show... Part B:"
                    if col_text.startswith(pattern.lower()):
                        shared[key] = col_idx
            return shared
        
        # Fallback: Hardcoded Quiz 5 patterns (backward compatibility)
        for col_idx, col_name in enumerate(self.df.columns):
            col_text = str(col_name).lower().strip()
            
            # Q1 Part B: "partition" question
            if 'partition' in col_text and 'minimum' in col_text and 'cut' in col_text:
                shared['q1_b'] = col_idx
            
            # Q2 Part B/C: Starts with "Part B:" or "Part C:"
            if col_text.startswith('part b:'):
                shared['q2_b'] = col_idx
            elif col_text.startswith('part c:'):
                shared['q2_c'] = col_idx
        
        return shared
    
    def _map_tag_to_group(self, tag: str) -> Optional[Tuple[str, int]]:
        """
        Map a tag to its question group and variant number.
        
        Args:
            tag: Question tag like "1.9" or "2.3"
            
        Returns:
            (group_id, variant_number) or None
        """
        for group in self.config['question_groups']:
            if tag in group['variant_tags']:
                variant_num = group['variant_tags'].index(tag) + 1
                return (group['id'], variant_num)
        return None
    
    def _find_student_variant(self, row: pd.Series, group_id: str) -> Optional[str]:
        """
        Find which variant the student received for a question group.
        
        Args:
            row: Student's row from CSV
            group_id: Question group ID (e.g., 'q1')
            
        Returns:
            Tag string (e.g., '1.5') or None
        """
        # Check all tags for this group
        for tag, col_idx in self.variant_columns.items():
            result = self._map_tag_to_group(tag)
            if not result:
                continue
            
            gid, variant_num = result
            if gid != group_id:
                continue
            
            # Check Status column (+2 from question column)
            status_col_idx = col_idx + 2
            if status_col_idx < len(row):
                status = row.iloc[status_col_idx]
                if pd.notna(status) and str(status) not in ['Not Attempted', 'Not Shown']:
                    # This is the variant they received
                    return tag
        
        return None
    
    def _extract_subpart_answers(self, row: pd.Series, tag: str, group_id: str) -> Dict[str, str]:
        """
        Extract answers for all subparts of a variant.
        
        Args:
            row: Student's row from CSV
            tag: Variant tag (e.g., '1.5')
            group_id: Question group ID (e.g., 'q1')
            
        Returns:
            Dict mapping part letter → answer HTML
            Example: {'a': '<p>6</p>', 'b': '<p>{s},{t}</p>'}
        """
        answers = {}
        
        # Part A: from the tagged column
        if tag in self.variant_columns:
            col_idx = self.variant_columns[tag]
            answer = row.iloc[col_idx]
            if pd.notna(answer) and str(answer).strip():
                answers['a'] = str(answer)
        
        # Part B: from shared column
        part_b_key = f'{group_id}_b'
        if part_b_key in self.shared_columns:
            col_idx = self.shared_columns[part_b_key]
            answer = row.iloc[col_idx]
            if pd.notna(answer) and str(answer).strip():
                answers['b'] = str(answer)
        
        # Part C: from shared column (if exists)
        part_c_key = f'{group_id}_c'
        if part_c_key in self.shared_columns:
            col_idx = self.shared_columns[part_c_key]
            answer = row.iloc[col_idx]
            if pd.notna(answer) and str(answer).strip():
                answers['c'] = str(answer)
        
        return answers
    
    def get_student_data(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Extract data for all students (or limited subset).
        
        Returns:
            List of student dicts: [{
                'name': 'Alice Smith',
                'id': '12345',
                'q1': {
                    'variant': 9,
                    'tag': '1.9',
                    'answers': {'a': '<p>6</p>', 'b': '<p>...</p>'}
                },
                'q2': { ... }
            }, ...]
        """
        students = []
        df_subset = self.df.head(limit) if limit else self.df
        
        for idx, row in df_subset.iterrows():
            sisid = str(row['SISID']) if pd.notna(row.get('SISID')) else ''
            
            # Lookup email if mapping exists
            email = self.email_mapping.get(sisid, '')
            
            student = {
                'name': str(row['Name']),
                'sisid': sisid,
                'email': email,
                'id': str(row['ID']) if pd.notna(row.get('ID')) else '',
            }
            
            # Process each question group
            for group in self.config['question_groups']:
                group_id = group['id']
                
                # Find which variant they got
                tag = self._find_student_variant(row, group_id)
                
                if tag:
                    result = self._map_tag_to_group(tag)
                    if result:
                        _, variant_num = result
                        # Extract subpart answers
                        answers = self._extract_subpart_answers(row, tag, group_id)
                        
                        student[group_id] = {
                            'variant': variant_num,
                            'tag': tag,
                            'answers': answers
                        }
                else:
                    # Default fallback
                    student[group_id] = {
                        'variant': 1,
                        'tag': group['variant_tags'][0],
                        'answers': {}
                    }
            
            students.append(student)
        
        return students
    
    def print_student_summary(self, student: Dict) -> None:
        """Print a summary of one student's data (for debugging)."""
        print(f"\n  Student: {student['name']}")
        # Dynamically get group IDs from config instead of hardcoding
        for group in self.config['question_groups']:
            group_id = group['id']
            if group_id in student:
                data = student[group_id]
                print(f"    {group_id}: Variant {data['variant']} (tag: {data['tag']})")
                for part, answer in data['answers'].items():
                    answer_preview = answer[:50] + '...' if len(answer) > 50 else answer
                    answer_preview = answer_preview.replace('\n', ' ')
                    print(f"      Part {part}: {answer_preview}")
