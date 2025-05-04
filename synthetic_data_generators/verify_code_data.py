import json
import os
import argparse
import json
import os
import argparse
import sys
import logging
import traceback # Keep for potential extraction error logging

# Add project root to the Python path
# This allows imports like 'from utilities.config import ...'
# and ensures consistency with other benchmark scripts.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the new verification utility
from utilities.code_execution import verify_code_with_task_data, compare_grids # Keep compare_grids if needed elsewhere, otherwise remove

# Configure logging
# Keep existing logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log_filename = "code_verification_debug.log" # Consider making this configurable or timestamped
file_handler = logging.FileHandler(log_filename, mode='w') # Overwrite log each run
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logging.getLogger().addHandler(file_handler)
logging.info("Code verification script started.")

# --- Helper Functions (Now mostly in utilities.code_execution) ---
# Removed compare_grids and execute_generated_code

# --- Main Verification Logic ---

def verify_results(results_file):
    """Loads results (which include task data), executes code, and reports verification."""
    logging.info(f"Loading benchmark results from: {results_file}")
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            benchmark_data = json.load(f)
        results = benchmark_data.get("results", [])
        if not results:
             logging.warning(f"No 'results' key found or results list is empty in {results_file}.")
             print(f"Warning: No 'results' found in {results_file}.")
             return
        logging.info(f"Loaded {len(results)} results entries.")
    except FileNotFoundError:
        logging.error(f"Results file not found: {results_file}")
        print(f"Error: Results file not found: {results_file}")
        return
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {results_file}: {e}")
        print(f"Error: Could not decode JSON from {results_file}.")
        return
    except Exception as e:
        logging.error(f"Error loading results file {results_file}: {e}")
        print(f"Error loading results file: {e}")
        return

    # Removed loading of separate dataset.json

    # --- Verification Loop ---
    total_tasks_processed = 0
    tasks_with_code = 0
    successful_tasks = 0
    failed_tasks_mismatch = 0 # Specific counter for mismatch
    failed_tasks_execution_error = 0 # Specific counter for execution errors
    failed_tasks_invalid_data = 0 # Counter for invalid/missing task data issues
    tasks_missing_arc_data_in_results = 0 # Count results where ARC data wasn't embedded
    tasks_without_code = 0 # Count results skipped because no code was found

    for result in results:
        task_id = result.get("task_id")
        python_code = result.get("python_code")
        model_response = result.get("model_response") # Backup if python_code key missing

        if not task_id:
            logging.warning("Skipping result with missing task_id.")
            continue

        total_tasks_processed += 1

        # --- Attempt to extract Python code if not directly available ---
        # Keep the existing extraction logic
        if not python_code and isinstance(model_response, str):
            try:
                # Basic extraction attempt - assumes code is in a ```python block
                if "```python" in model_response:
                    code_block = model_response.split("```python", 1)[1]
                    if "```" in code_block:
                        python_code = code_block.split("```", 1)[0].strip()
                        logging.info(f"Task {task_id}: Extracted Python code from model_response.")
                    else:
                        python_code = code_block.strip() # Assume rest is code if no closing ```
                        logging.info(f"Task {task_id}: Extracted Python code (no closing ```) from model_response.")
                # Add more robust extraction logic here if needed (e.g., regex)
            except Exception as e:
                logging.error(f"Task {task_id}: Error during code extraction from model_response: {e}\n{traceback.format_exc()}")
                python_code = None # Ensure it's None if extraction fails

        if not python_code or not isinstance(python_code, str) or not python_code.strip():
            logging.info(f"Task {task_id}: No Python code found or code is empty. Skipping verification.")
            tasks_without_code += 1
            continue

        tasks_with_code += 1
        logging.info(f"Verifying Task ID: {task_id}")

        # --- Get Embedded ARC Task Data ---
        task_data = result.get("task_data") # Get data directly from result
        if not task_data or not isinstance(task_data, dict):
             logging.warning(f"Task {task_id}: Embedded 'task_data' not found or invalid in results file. Skipping verification.")
             tasks_missing_arc_data_in_results += 1
             continue # Skip if the necessary ARC data isn't in the results file

        # --- Use the new verification function ---
        success, reason = verify_code_with_task_data(python_code, task_data, task_id)

        # --- Tally Task Results Based on Verification Outcome ---
        if success:
            successful_tasks += 1
            logging.info(f"Task {task_id}: Classified as SUCCESS ({reason}).")
        else:
            # Categorize the failure based on the reason string
            if "Execution Error" in reason:
                failed_tasks_execution_error += 1
                logging.warning(f"Task {task_id}: Classified as FAILED (Execution Error: {reason}).")
            elif "Output Mismatch" in reason:
                failed_tasks_mismatch += 1
                logging.warning(f"Task {task_id}: Classified as FAILED (Output Mismatch: {reason}).")
            elif "Invalid Task Data" in reason or "Invalid Test Case" in reason or "Missing Test Cases" in reason:
                 failed_tasks_invalid_data += 1
                 logging.warning(f"Task {task_id}: Classified as FAILED (Invalid/Missing Data: {reason}).")
            else:
                # Catch-all for unexpected reasons
                failed_tasks_execution_error += 1 # Default to execution error? Or a new category?
                logging.error(f"Task {task_id}: Classified as FAILED (Unknown Reason: {reason}).")


    # --- Print Summary Report ---
    print("\n--- Code Verification Summary ---")
    print(f"Results File:          {results_file}")
    # Removed ARC Dataset File line
    print("-" * 30)
    print(f"Total Results Entries: {len(results)}")
    print(f"Tasks Processed:       {total_tasks_processed}")
    print(f"Tasks w/o Code Found:  {tasks_without_code}")
    print(f"Tasks w/ Code Verified:{tasks_with_code}")
    print(f"Tasks Missing ARC Data:{tasks_missing_arc_data_in_results}") # Renamed counter
    print("-" * 30)
    # Calculate percentages based on tasks_with_code
    if tasks_with_code > 0:
        success_pct = successful_tasks / tasks_with_code * 100
        mismatch_pct = failed_tasks_mismatch / tasks_with_code * 100
        exec_error_pct = failed_tasks_execution_error / tasks_with_code * 100
        invalid_data_pct = failed_tasks_invalid_data / tasks_with_code * 100
        print(f"Successful Tasks:      {successful_tasks} ({success_pct:.1f}%)")
        print(f"Failed (Mismatch):     {failed_tasks_mismatch} ({mismatch_pct:.1f}%)")
        print(f"Failed (Exec Error):   {failed_tasks_execution_error} ({exec_error_pct:.1f}%)")
        print(f"Failed (Invalid Data): {failed_tasks_invalid_data} ({invalid_data_pct:.1f}%)")
    else:
        print("Successful Tasks:      0")
        print("Failed (Mismatch):     0")
        print("Failed (Exec Error):   0")
        print("Failed (Invalid Data): 0")
    print("-" * 30)
    logging.info("Verification process completed.")
    # Log summary with new counters
    logging.info(f"Summary: Total={total_tasks_processed}, NoCode={tasks_without_code}, Verified={tasks_with_code}, Success={successful_tasks}, Mismatch={failed_tasks_mismatch}, ExecError={failed_tasks_execution_error}, InvalidData={failed_tasks_invalid_data}, MissingARC={tasks_missing_arc_data_in_results}")


# --- Command Line Interface ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify generated Python code for ARC tasks using task data embedded in the results file.")
    parser.add_argument("results_file", help="Path to the benchmark results JSON file containing generated code and embedded task data (e.g., synthetic_data_generators/synthetic_data/code_data/code_data_results_*.json).")
    # No longer needs --arc_data_dir

    args = parser.parse_args()

    # Call verify_results with the results file path
    verify_results(args.results_file)
