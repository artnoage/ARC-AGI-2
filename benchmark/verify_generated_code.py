import json
import os
import argparse
import importlib.util
import sys
import traceback
import logging
import time
from data_loader import load_tasks_from_dataset # Reuse data loading logic

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log_filename = "code_verification_debug.log"
file_handler = logging.FileHandler(log_filename, mode='w') # Overwrite log each run
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logging.getLogger().addHandler(file_handler)
logging.info("Code verification script started.")

# --- Helper Functions ---

def compare_grids(grid1, grid2):
    """Compares two grids (lists of lists)."""
    if not isinstance(grid1, list) or not isinstance(grid2, list):
        return False
    if len(grid1) != len(grid2):
        return False
    for i in range(len(grid1)):
        if not isinstance(grid1[i], list) or not isinstance(grid2[i], list):
            return False
        if len(grid1[i]) != len(grid2[i]):
            return False
        for j in range(len(grid1[i])):
            if grid1[i][j] != grid2[i][j]:
                return False
    return True

def execute_generated_code(code_string, input_grid, task_id):
    """
    Executes the generated Python code string within a temporary module.
    Attempts to call the 'solve_task' function with the input_grid.
    Returns (output_grid, error_message). error_message is None on success.
    """
    module_name = f"generated_solver_{task_id}_{time.time_ns()}" # Unique module name

    spec = importlib.util.spec_from_loader(module_name, loader=None)
    if spec is None:
        error_msg = f"Error: Could not create spec for temporary module {module_name}"
        logging.error(f"Task {task_id}: {error_msg}")
        return None, error_msg

    module = importlib.util.module_from_spec(spec)

    # Add numpy to the module's namespace if needed by generated code
    try:
        import numpy as np
        module.np = np
    except ImportError:
        logging.warning(f"Task {task_id}: NumPy not installed, generated code using it might fail.")
        module.np = None # Or handle differently

    # Add other potentially useful libraries if needed
    # module.copy = copy

    try:
        # Execute the code string within the module's namespace
        exec(code_string, module.__dict__)

        if not hasattr(module, 'solve_task'):
            error_msg = "Function 'solve_task(input_grid)' not found in generated code."
            logging.warning(f"Task {task_id}: {error_msg}")
            return None, error_msg

        solve_func = getattr(module, 'solve_task')

        # Call the function, handling potential exceptions within it
        try:
            # Make a copy of the input grid to prevent modification?
            # input_grid_copy = [row[:] for row in input_grid] # Shallow copy
            output_grid = solve_func(input_grid) # Pass the original for now

            # --- Output Validation ---
            if not isinstance(output_grid, list):
                 error_msg = f"Generated function did not return a list (got {type(output_grid)})"
                 logging.warning(f"Task {task_id}: {error_msg}")
                 return None, error_msg
            if not all(isinstance(row, list) for row in output_grid):
                 error_msg = f"Generated function did not return a list of lists (got {type(output_grid)} containing {type(output_grid[0]) if output_grid else 'empty'})"
                 logging.warning(f"Task {task_id}: {error_msg}")
                 return None, error_msg
            # Optional: Check element types if needed (e.g., all ints)

            return output_grid, None # Success

        except Exception as e:
            error_msg = f"Error during generated code execution: {traceback.format_exc()}"
            logging.error(f"Task {task_id}: {error_msg}")
            return None, error_msg

    except SyntaxError as e:
        error_msg = f"Syntax error in generated code: {e}\n{traceback.format_exc()}"
        logging.error(f"Task {task_id}: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Error importing/executing generated code: {traceback.format_exc()}"
        logging.error(f"Task {task_id}: {error_msg}")
        return None, error_msg
    finally:
        # Clean up the temporary module
        if module_name in sys.modules:
            try:
                del sys.modules[module_name]
            except KeyError:
                pass # Might already be removed or failed to insert

# --- Main Verification Logic ---

def verify_results(results_file, arc_data_path, use_dataset_json):
    """Loads results, loads tasks, executes code, and reports verification."""
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

    logging.info(f"Loading ARC tasks from: {arc_data_path} (using_dataset_json={use_dataset_json})")
    try:
        if use_dataset_json:
            # Load all tasks into memory from dataset.json for easier lookup
            # Note: This might be memory intensive for very large datasets
            arc_tasks = {task['task_id']: task for task in load_tasks_from_dataset(arc_data_path)}
            logging.info(f"Loaded {len(arc_tasks)} tasks from {arc_data_path}")
        else:
            # Load tasks individually as needed (more memory efficient)
            arc_tasks = {} # Will populate on demand
            logging.info(f"Set up to load tasks individually from directory: {arc_data_path}")
    except Exception as e:
        logging.error(f"Error loading ARC tasks: {e}")
        print(f"Error loading ARC tasks: {e}")
        return

    # --- Verification Loop ---
    total_tasks_processed = 0
    tasks_with_code = 0
    successful_tasks = 0
    failed_tasks = 0
    error_tasks = 0
    tasks_missing_data = 0 # Count tasks where ARC data couldn't be loaded

    for result in results:
        task_id = result.get("task_id")
        python_code = result.get("python_code")
        model_response = result.get("model_response") # Backup if python_code key missing

        if not task_id:
            logging.warning("Skipping result with missing task_id.")
            continue

        total_tasks_processed += 1

        # Attempt to extract Python code if not directly available
        if not python_code and isinstance(model_response, str):
             # Basic extraction attempt - assumes code is in a ```python block
             if "```python" in model_response:
                 code_block = model_response.split("```python", 1)[1]
                 if "```" in code_block:
                     python_code = code_block.split("```", 1)[0].strip()
                     logging.info(f"Task {task_id}: Extracted Python code from model_response.")
                 else:
                     python_code = code_block.strip() # Assume rest is code if no closing ```
                     logging.info(f"Task {task_id}: Extracted Python code (no closing ```) from model_response.")


        if not python_code or not isinstance(python_code, str) or not python_code.strip():
            logging.info(f"Task {task_id}: No Python code found or code is empty. Skipping verification.")
            continue

        tasks_with_code += 1
        logging.info(f"Verifying Task ID: {task_id}")

        # --- Load ARC Task Data ---
        task_data = arc_tasks.get(task_id)
        if not task_data and not use_dataset_json:
            # Try loading individually from training/ or evaluation/ subdirs
            found_task_file = False
            for subdir in ["training", "evaluation"]:
                potential_path = os.path.join(arc_data_path, subdir, f"{task_id}.json")
                if os.path.exists(potential_path):
                    try:
                        with open(potential_path, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                        arc_tasks[task_id] = task_data # Cache it
                        logging.info(f"Task {task_id}: Loaded task data from {potential_path}")
                        found_task_file = True
                        break # Stop searching once found
                    except Exception as e:
                        logging.error(f"Task {task_id}: Error loading task file {potential_path}: {e}")
                        # Mark as missing data even if found but failed to load
                        tasks_missing_data += 1
                        task_data = None # Ensure task_data is None if loading failed
                        found_task_file = True # Treat loading error as finding it but failing
                        break

            if not found_task_file:
                logging.warning(f"Task {task_id}: ARC task file not found in {os.path.join(arc_data_path, 'training')} or {os.path.join(arc_data_path, 'evaluation')}")
                tasks_missing_data += 1
                continue
            elif task_data is None: # Handle case where file existed but failed to load
                # Error already logged, just continue to next result
                continue

        elif not task_data and use_dataset_json:
             logging.warning(f"Task {task_id}: Task data not found in the loaded dataset.json.")
             tasks_missing_data += 1
             continue

        # --- Execute and Compare Test Cases ---
        task_passed_all_tests = True
        task_had_execution_error = False
        test_cases = task_data.get("test", [])

        if not test_cases:
            logging.warning(f"Task {task_id}: No 'test' cases found in task data.")
            # How to classify this? Maybe error? Or skip? Let's skip for now.
            # error_tasks += 1 # Or a different counter?
            continue

        for i, test_case in enumerate(test_cases):
            input_grid = test_case.get("input")
            expected_output_grid = test_case.get("output")

            if input_grid is None or expected_output_grid is None:
                logging.warning(f"Task {task_id}: Test case {i} is missing input or output grid.")
                task_passed_all_tests = False # Consider this a failure?
                task_had_execution_error = True # Treat malformed data as an error?
                break # Stop processing this task

            # Execute the generated code for this test case
            actual_output_grid, error_msg = execute_generated_code(python_code, input_grid, task_id)

            if error_msg:
                logging.error(f"Task {task_id}: Test case {i}: Execution error: {error_msg}")
                task_passed_all_tests = False
                task_had_execution_error = True
                break # Stop processing this task's test cases on first error

            # Compare the actual output with the expected output
            if not compare_grids(actual_output_grid, expected_output_grid):
                logging.warning(f"Task {task_id}: Test case {i}: Output mismatch.")
                # Log the grids for debugging? Be careful with large grids.
                # logging.debug(f"Expected: {expected_output_grid}")
                # logging.debug(f"Actual: {actual_output_grid}")
                task_passed_all_tests = False
                # Don't break here, let it check other test cases unless an error occurred
            else:
                logging.info(f"Task {task_id}: Test case {i}: Passed.")

        # --- Tally Task Results ---
        if task_had_execution_error:
            error_tasks += 1
            logging.info(f"Task {task_id}: Classified as ERROR.")
        elif task_passed_all_tests:
            successful_tasks += 1
            logging.info(f"Task {task_id}: Classified as SUCCESS.")
        else:
            failed_tasks += 1
            logging.info(f"Task {task_id}: Classified as FAILED (output mismatch).")

    # --- Print Summary Report ---
    print("\n--- Code Verification Summary ---")
    print(f"Results File:          {results_file}")
    print(f"ARC Data Path:         {arc_data_path}")
    print(f"Using dataset.json:    {use_dataset_json}")
    print("-" * 30)
    print(f"Total Results Entries: {len(results)}")
    print(f"Tasks Processed:       {total_tasks_processed}")
    print(f"Tasks w/ Python Code:  {tasks_with_code}")
    print(f"Tasks Missing ARC Data:{tasks_missing_data}")
    print("-" * 30)
    print(f"Successful Tasks:      {successful_tasks} ({successful_tasks / tasks_with_code:.1%})" if tasks_with_code > 0 else "Successful Tasks:      0")
    print(f"Failed Tasks (Mismatch):{failed_tasks} ({failed_tasks / tasks_with_code:.1%})" if tasks_with_code > 0 else "Failed Tasks (Mismatch): 0")
    print(f"Error Tasks (Execution):{error_tasks} ({error_tasks / tasks_with_code:.1%})" if tasks_with_code > 0 else "Error Tasks (Execution): 0")
    print("-" * 30)
    logging.info("Verification process completed.")
    logging.info(f"Summary: Total={total_tasks_processed}, WithCode={tasks_with_code}, Success={successful_tasks}, Failed={failed_tasks}, Error={error_tasks}, MissingData={tasks_missing_data}")


# --- Command Line Interface ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify generated Python code for ARC tasks against test cases.")
    parser.add_argument("results_file", help="Path to the benchmark results JSON file (e.g., code_gen_benchmark_results_*.json).")
    parser.add_argument("--arc_data_path", default="data", help="Path to the ARC dataset (directory containing task .json files or the dataset.json file).")
    parser.add_argument("--use_dataset_json", action="store_true", help="Load tasks from a single 'dataset.json' file within the arc_data_path instead of individual task files.")

    args = parser.parse_args()

    # Determine the actual path to dataset.json if needed
    data_path_to_use = args.arc_data_path
    if args.use_dataset_json:
        dataset_json_path = os.path.join(args.arc_data_path, "dataset.json")
        if not os.path.exists(dataset_json_path):
             print(f"Error: --use_dataset_json specified, but {dataset_json_path} not found.")
             logging.error(f"--use_dataset_json specified, but {dataset_json_path} not found.")
             sys.exit(1)
        data_path_to_use = dataset_json_path # Pass the specific file path

    verify_results(args.results_file, data_path_to_use, args.use_dataset_json)
