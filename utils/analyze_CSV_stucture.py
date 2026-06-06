import pandas as pd
import re
import sys

df = pd.read_csv(sys.argv[1])

print(f"Total students: {len(df)}")
print(f"Total columns: {len(df.columns)}\n")

# Find all tagged columns
print("Tagged columns (variant identifiers):")
for i, col in enumerate(df.columns):
    match = re.match(r'^(\d+\.\d+)', str(col).strip())
    if match:
        print(f"  Col {i}: Tag {match.group(1)} - {str(col)[:60]}")

# Search for shared subpart columns
print("\nSearching for shared subpart patterns:")
for pattern in ['Part B', 'Part C', 'partition', 'explain', 'describe']:
    matches = [i for i, c in enumerate(df.columns) if pattern.lower() in str(c).lower()]
    if matches:
        print(f"  '{pattern}': columns {matches[:3]}")
        print(f"    Example: {df.columns[matches[0]][:60]}")
