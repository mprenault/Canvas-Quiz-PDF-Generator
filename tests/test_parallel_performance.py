import subprocess
import time
import sys
from pathlib import Path

def run_performance_test():
    # Configuration
    quiz_id = 5
    csv_file = "test_data/Quiz 5 - Network Flow Student Analysis Report.csv"
    limit = 10
    job_counts = [1, 2, 3, 4]
    
    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    script_path = project_root / "run_quiz.py"
    
    if not script_path.exists():
        print(f"Error: Could not find {script_path}")
        return

    print(f"🚀 Starting Parallel Performance Test")
    print(f"Target: {limit} students per run")
    print(f"CSV: {csv_file}")
    print("-" * 60)
    print(f"{'Jobs':<10} | {'Time (s)':<15} | {'Speedup':<15}")
    print("-" * 60)

    results = {}

    for jobs in job_counts:
        print(f"Running with {jobs} job(s)...", end="", flush=True)
        
        start_time = time.time()
        
        # Construct command
        # using sys.executable to ensure we use the same python interpreter
        cmd = [
            sys.executable,
            str(script_path),
            "--quiz", str(quiz_id),
            "--csv", csv_file,
            "--limit", str(limit),
            "--jobs", str(jobs),
            "--no-zip",  # Skip zip to focus on generation time
            "--no-templates" # Skip template generation to focus on PDF generation
        ]
        
        try:
            # Run command and capture output to suppress it (optional, maybe we want to see errors)
            result = subprocess.run(
                cmd, 
                cwd=project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"\n❌ Failed with exit code {result.returncode}")
                print(result.stderr)
                continue
                
            duration = time.time() - start_time
            results[jobs] = duration
            
            # Calculate speedup relative to 1 job
            speedup = results[1] / duration if 1 in results else 1.0
            
            # Clear the "Running..." line and print stats
            print(f"\r{jobs:<10} | {duration:<15.2f} | {speedup:<15.2f}x")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")

    print("-" * 60)
    
    # Summary
    if 1 in results and 4 in results:
        improvement = results[1] - results[4]
        percent = (improvement / results[1]) * 100
        print(f"\nSummary: 4 jobs saved {improvement:.1f}s ({percent:.1f}%) compared to sequential execution.")

if __name__ == "__main__":
    run_performance_test()
