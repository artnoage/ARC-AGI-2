import importlib.util
import sys
import traceback
import logging
import time
import copy

# Configure logging for this utility module if needed, or rely on the calling script's config
# For simplicity, let's use a basic logger instance here.
log = logging.getLogger(__name__)
# Example basic config if run standalone or if calling script doesn't configure root logger:
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Grid Comparison ---

def compare_grids(grid1, grid2):
    """
    Compares two grids (lists of lists).
    Returns True if they are identical, False otherwise.
    Handles basic type and dimension checks.
    """
    if not isinstance(grid1, list) or not isinstance(grid2, list):
        log.debug("Grid comparison failed: One or both inputs are not lists.")
        return False
    if len(grid1) != len(grid2):
        log.debug(f"Grid comparison failed: Row count mismatch ({len(grid1)} vs {len(grid2)}).")
        return False
    for i, row1 in enumerate(grid1):
        row2 = grid2[i]
        if not isinstance(row1, list) or not isinstance(row2, list):
            log.debug(f"Grid comparison failed: Row {i} is not a list in one or both grids.")
            return False
        if len(row1) != len(row2):
            log.debug(f"Grid comparison failed: Column count mismatch in row {i} ({len(row1)} vs {len(row2)}).")
            return False
        for j, cell1 in enumerate(row1):
            cell2 = row2[j]
            if cell1 != cell2:
                log.debug(f"Grid comparison failed: Mismatch at cell ({i},{j}): {cell1} != {cell2}.")
                return False
    log.debug("Grid comparison successful: Grids are identical.")
    return True

# --- Code Execution ---

def execute_generated_code(code_string, input_grid, task_id="unknown"):
    """
    Executes the generated Python code string within a temporary module.
    Attempts to call the 'solve_task' function with the input_grid.

    Args:
        code_string (str): The Python code to execute.
        input_grid (list): The input grid for the 'solve_task' function.
        task_id (str): An identifier for logging purposes.

    Returns:
        tuple: (output_grid, error_message)
               - output_grid (list or None): The grid returned by solve_task, or None on error.
               - error_message (str or None): A description of the error if one occurred, otherwise None.
    """
    module_name = f"generated_solver_{task_id}_{time.time_ns()}" # Unique module name
    log.debug(f"Task {task_id}: Attempting to execute code in temporary module {module_name}")

    spec = importlib.util.spec_from_loader(module_name, loader=None)
    if spec is None:
        error_msg = f"Error: Could not create spec for temporary module {module_name}"
        log.error(f"Task {task_id}: {error_msg}")
        return None, error_msg

    module = importlib.util.module_from_spec(spec)

    # Inject commonly used libraries into the module's namespace
    # This avoids forcing the generated code to include these imports itself.
    try:
        import numpy as np
        module.np = np
        log.debug(f"Task {task_id}: Injected numpy as 'np' into module {module_name}")
    except ImportError:
        log.warning(f"Task {task_id}: NumPy not installed, generated code using it might fail.")
        module.np = None

    # Inject copy module
    module.copy = copy
    log.debug(f"Task {task_id}: Injected copy module into module {module_name}")

    # Add other potentially useful libraries here if needed
    # e.g., math, collections, etc.

    try:
        # Execute the code string within the module's namespace
        exec(code_string, module.__dict__)
        log.debug(f"Task {task_id}: Successfully executed code string in module {module_name}")

        if not hasattr(module, 'solve_task'):
            error_msg = "Execution Error: Function 'solve_task(input_grid)' not found in generated code."
            log.warning(f"Task {task_id}: {error_msg}")
            return None, error_msg

        solve_func = getattr(module, 'solve_task')

        # Call the function, handling potential exceptions within it
        try:
            # Use deepcopy to prevent the user function from modifying the original input grid
            # This is crucial for verifying against multiple test cases with the same initial state.
            input_grid_copy = copy.deepcopy(input_grid)
            log.debug(f"Task {task_id}: Calling solve_task function...")
            output_grid = solve_func(input_grid_copy)
            log.debug(f"Task {task_id}: solve_task function returned.")

            # --- Output Validation ---
            if not isinstance(output_grid, list):
                 error_msg = f"Output Error: Generated function did not return a list (got {type(output_grid)})."
                 log.warning(f"Task {task_id}: {error_msg}")
                 return None, error_msg
            if not all(isinstance(row, list) for row in output_grid):
                 # Check if it's a list of something else (e.g., list of ints)
                 inner_type = type(output_grid[0]) if output_grid else 'empty'
                 error_msg = f"Output Error: Generated function did not return a list of lists (innermost type: {inner_type})."
                 log.warning(f"Task {task_id}: {error_msg}")
                 return None, error_msg
            # Optional: Add checks for cell types (e.g., all ints between 0-9) if required by ARC rules

            log.debug(f"Task {task_id}: solve_task execution successful, output grid validated.")
            return output_grid, None # Success

        except Exception as e:
            # Capture traceback for detailed error logging
            tb_str = traceback.format_exc()
            error_msg = f"Runtime Error: Exception during generated code execution: {e}\nTraceback:\n{tb_str}"
            log.error(f"Task {task_id}: {error_msg}")
            return None, error_msg

    except SyntaxError as e:
        tb_str = traceback.format_exc()
        error_msg = f"Syntax Error: Invalid syntax in generated code: {e}\nTraceback:\n{tb_str}"
        log.error(f"Task {task_id}: {error_msg}")
        return None, error_msg
    except Exception as e:
        tb_str = traceback.format_exc()
        error_msg = f"Import/Exec Error: Error importing/executing generated code: {e}\nTraceback:\n{tb_str}"
        log.error(f"Task {task_id}: {error_msg}")
        return None, error_msg
    finally:
        # Clean up the temporary module from sys.modules to prevent memory leaks
        if module_name in sys.modules:
            try:
                del sys.modules[module_name]
                log.debug(f"Task {task_id}: Cleaned up temporary module {module_name}")
            except KeyError:
                log.warning(f"Task {task_id}: Could not remove module {module_name} during cleanup.")
                pass # Might already be removed or failed to insert

# --- Verification Function ---

def verify_code_with_task_data(python_code, task_data, task_id="unknown"):
    """
    Verifies generated Python code against all test cases within the task_data.

    Args:
        python_code (str): The generated Python code string containing a 'solve_task' function.
        task_data (dict): The ARC task data dictionary, expected to have a 'test' key
                          containing a list of {'input': grid, 'output': grid} pairs.
        task_id (str): An identifier for the task, used for logging.

    Returns:
        tuple: (success, reason)
               - success (bool): True if the code passes all test cases, False otherwise.
               - reason (str): A description of why verification failed ('Passed', 'Execution Error',
                             'Output Mismatch', 'Missing Test Cases', 'Invalid Task Data').
    """
    log.info(f"Task {task_id}: Starting verification.")

    if not isinstance(task_data, dict) or "test" not in task_data:
        log.warning(f"Task {task_id}: Invalid or missing 'test' key in task_data.")
        return False, "Invalid Task Data"

    test_cases = task_data["test"]
    if not test_cases:
        log.warning(f"Task {task_id}: No test cases found in task_data.")
        return False, "Missing Test Cases" # Or should this be True if there are no tests? Arguably False.

    log.debug(f"Task {task_id}: Found {len(test_cases)} test cases.")

    for i, test_case in enumerate(test_cases):
        input_grid = test_case.get("input")
        expected_output_grid = test_case.get("output")

        if input_grid is None or expected_output_grid is None:
            log.warning(f"Task {task_id}: Test case {i} is missing input or output grid.")
            return False, f"Invalid Test Case {i}" # Fail fast on malformed test data

        log.debug(f"Task {task_id}: Running test case {i}...")
        actual_output_grid, error_msg = execute_generated_code(python_code, input_grid, f"{task_id}_test{i}")

        if error_msg:
            log.warning(f"Task {task_id}: Test case {i} failed due to execution error.")
            # The detailed error is already logged by execute_generated_code
            return False, f"Execution Error (Test Case {i})" # Fail fast on execution error

        if not compare_grids(actual_output_grid, expected_output_grid):
            log.warning(f"Task {task_id}: Test case {i} failed due to output mismatch.")
            # Optionally log expected vs actual here for debugging, but can be verbose
            # log.debug(f"Task {task_id}: Test Case {i} - Expected: {expected_output_grid}")
            # log.debug(f"Task {task_id}: Test Case {i} - Actual:   {actual_output_grid}")
            return False, f"Output Mismatch (Test Case {i})" # Fail fast on mismatch

        log.debug(f"Task {task_id}: Test case {i} passed.")

    log.info(f"Task {task_id}: Verification successful - all {len(test_cases)} test cases passed.")
    return True, "Passed"
