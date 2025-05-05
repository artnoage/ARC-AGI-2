import os
import json
import logging
import time
import asyncio
import argparse
import signal
import sys
import atexit

# Add project root to the Python path
# This allows imports like 'from utilities.config import ...' when running from the root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    # Using print for early debug as logging might not be configured yet
    # print(f"DEBUG: Added project root to sys.path: {project_root}")

from utilities.config import ARCBenchmarkConfig, ModelOption # Updated import path
# Only import the dataset loader function
from utilities.data_loader import load_tasks_from_dataset # Updated import path
from agents.reasoning_code_generator import CodeGeneratingAgent # Keep this path
# Import get_model
from utilities.model_utils import get_model # Updated import path

# Configure logging
# Define log path relative to this script's directory -> project_root/synthetic_data_generators/synthetic_data/
log_dir = os.path.join(project_root, "synthetic_data_generators", "synthetic_data")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "code_data_generation.log") # Specific log file name

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='w'),  # Save logs to the new path, overwrite each run
        logging.StreamHandler()  # Also output to console
    ]
)
logging.info(f"Logging configured at DEBUG level for Code Generation Benchmark. Log file: {log_file_path}")

# --- Global State for Saving (mostly the same) ---
g_results = []
g_config = None
g_start_time = None
g_model_value = None
g_successful_count = 0
g_failed_count = 0
g_skipped_count = 0
g_submitted_count = 0
g_is_saving = False
g_last_saved_results_len = 0
g_timestamp = time.strftime("%Y%m%d_%H%M%S")  # Generate timestamp once at the beginning
SAVE_INTERVAL = 10 # Save results every N successful tasks
# --- End Global State ---

# --- Helper Functions for Saving (adapted filenames) ---

def save_results_helper(output_data, output_path):
    """Handles the actual writing of the JSON file."""
    global g_is_saving
    if g_is_saving:
        logging.warning("Already saving, skipping concurrent save request.")
        return False
    g_is_saving = True
    try:
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        logging.info(f"Results saved to: {output_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save results to {output_path}: {e}", exc_info=True)
        return False
    finally:
        g_is_saving = False

def save_periodic_results():
    """Appends new results to the results file in JSON Lines format."""
    global g_is_saving, g_last_saved_results_len, g_timestamp

    if g_config is None or len(g_results) <= g_last_saved_results_len:
        logging.debug("Periodic save check: No new results to append.")
        return

    if g_is_saving:
        logging.warning("Already saving, skipping concurrent periodic save request.")
        return

    g_is_saving = True
    new_results_to_save = g_results[g_last_saved_results_len:]
    num_new_results = len(new_results_to_save)
    logging.debug(f"Attempting periodic save: Appending {num_new_results} new results...")

    try:
        # Define the subdirectory and filename
        subdirectory = "code_data"
        results_filename = f"code_data_results_{g_timestamp}.jsonl"
        # Construct the full path including the subdirectory
        results_path = os.path.join(g_config.output_directory, subdirectory, results_filename)

        # Ensure output directory exists (including subdirectory)
        output_dir = os.path.dirname(results_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

        with open(results_path, 'a', encoding='utf-8') as f:
            for result_entry in new_results_to_save:
                f.write(json.dumps(result_entry) + '\n')

        logging.info(f"Appended {num_new_results} results to file: {results_path}")
        g_last_saved_results_len = len(g_results)

    except Exception as e:
        logging.error(f"Failed to append results to {results_path}: {e}", exc_info=True)
    finally:
        g_is_saving = False

def save_final_results(interrupted=False):
    """Appends a metadata entry to the results file."""
    global g_timestamp
    
    if g_config is None:
        logging.info("No config loaded, skipping final metadata save.")
        return

    status = "interrupted" if interrupted else "completed"
    logging.info(f"Attempting final metadata save (status: {status})...")

    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0

    metadata = {
        "entry_type": "metadata",
        "benchmark_type": "code_generation",
        "status": status,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_identifier": g_config.model_identifier,
        "model_username": g_model_value,
        "max_tasks_requested": g_config.max_tasks,
        "tasks_submitted": g_submitted_count,
        "tasks_successful": g_successful_count,
        "tasks_failed": g_failed_count,
        "tasks_skipped": g_skipped_count,
        "task_source": "dataset.json",
        "max_concurrent_tasks": g_config.max_concurrent_tasks,
        "total_runtime_seconds": round(total_time, 2)
    }

    # Define the subdirectory and filename
    subdirectory = "code_data"
    results_filename = f"code_data_results_{g_timestamp}.jsonl"
    # Construct the full path including the subdirectory
    results_path = os.path.join(g_config.output_directory, subdirectory, results_filename)
    
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(results_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")
            
        # Append metadata entry to the results file
        with open(results_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(metadata) + '\n')
            
        logging.info(f"Appended final metadata to results file: {results_path}")
    except Exception as e:
        logging.error(f"Failed to append metadata to {results_path}: {e}", exc_info=True)

def signal_handler(sig, frame):
    """Handles SIGINT (Ctrl+C)."""
    logging.warning(f"Signal {sig} received, initiating graceful shutdown and saving results...")
    save_final_results(interrupted=True)
    logging.warning("Exiting due to signal.")
    sys.exit(1)

# --- End Helper Functions ---


async def process_single_task(item, config, agent, semaphore, index, total_tasks=None):
    """Processes a single task using CodeGeneratingAgent and updates global results."""
    global g_results, g_successful_count, g_failed_count, g_skipped_count
    task_id = None
    async with semaphore:
        try:
            # Item is now always a tuple (task_id, task_data) from load_tasks_from_dataset
            task_id, task_data = item
            log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" (Dataset: {task_id})"
            logging.debug(f"{log_prefix}: Acquired semaphore, processing...")

            # --- Agent Processing (Use CodeGeneratingAgent) ---
            prompt_messages, reasoning, python_code = await agent.get_reasoning_and_code(task_data)
            # --- ---

            # Prepare result entry (add python_code)
            result_entry = {
                "task_id": task_id,
                "task_data": {
                    "train": task_data.get("train", []),
                    "test": task_data.get("test", [])
                },
                "prompt_messages": prompt_messages,
                "reasoning": None, # Placeholder
                "python_code": None # Placeholder for code
            }

            # Check if both reasoning and code were successfully generated
            # (Handle cases where one or both might be None or contain errors)
            success = False
            if reasoning is not None and not reasoning.startswith("Error:") and \
               python_code is not None:
                result_entry["reasoning"] = reasoning
                result_entry["python_code"] = python_code
                g_results.append(result_entry)
                g_successful_count += 1
                logging.info(f"{log_prefix}: Finished processing successfully (got reasoning and code).")
                success = True
                # Check for periodic save
                if g_successful_count % SAVE_INTERVAL == 0:
                    save_periodic_results()
            else:
                # Log specific failure reason
                fail_reason = []
                if reasoning is None or reasoning.startswith("Error:"):
                    fail_reason.append("failed to get reasoning")
                    result_entry["reasoning"] = reasoning if reasoning else "ERROR: No reasoning received."
                else:
                     result_entry["reasoning"] = reasoning # Keep valid reasoning if code failed

                if python_code is None:
                    fail_reason.append("failed to get code")
                    result_entry["python_code"] = "ERROR: No Python code received."
                else:
                    result_entry["python_code"] = python_code # Keep code if reasoning failed? Maybe not useful.

                g_results.append(result_entry) # Append error result
                g_failed_count += 1
                logging.warning(f"{log_prefix}: Finished processing with error ({', '.join(fail_reason)}).")


        except Exception as e:
            error_task_id = task_id if task_id else f"task_{index+1}"
            log_prefix_err = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" ({error_task_id})"
            logging.error(f"{log_prefix_err}: Unexpected error processing task: {e}", exc_info=True)
            g_results.append({
                "task_id": error_task_id,
                "task_data": "Error during processing loop",
                "prompt_messages": None,
                "reasoning": f"ERROR: Exception during task processing loop: {e}",
                "python_code": None
            })
            g_failed_count += 1


async def generate_code_data(args): # Renamed function to remove 'benchmark'
    """Generates ARC code data with concurrency control.""" # Updated docstring
    global g_config, g_start_time, g_model_value, g_submitted_count
    logging.info("Starting ARC Code Data Generation...") # Updated log message

    # 1. Load Configuration (updated for dataset.json only)
    try:
        g_config = ARCBenchmarkConfig(
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks,
            # use_dataset_json is removed
            dataset_directory=args.dataset_directory, # Use the renamed argument
            max_concurrent_tasks=args.max_concurrent_tasks
        )
        logging.info(f"Configuration loaded. Output directory: {g_config.output_directory}")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}")
        # Always using dataset.json now
        logging.info(f"Using dataset file: {g_config.absolute_dataset_file}")
        logging.info(f"Using model: {g_config.model_identifier}")
        if g_config.max_tasks is not None:
            logging.info(f"Maximum tasks to process: {g_config.max_tasks}")
        else:
             logging.info("Processing all found/specified tasks (no max_tasks limit).")
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model (Use CodeGeneratingAgent)
    try:
        model_enum_member = ModelOption[g_config.model_identifier]
        g_model_value = model_enum_member.value

        model = get_model(g_config, role="main")
        # Instantiate the correct agent
        agent = CodeGeneratingAgent(model=model)
        logging.info(f"Initialized CodeGeneratingAgent with model: {g_config.model_identifier} ({g_model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return


    # 3. Prepare Task List/Iterator and Semaphore (same as before)
    semaphore = asyncio.Semaphore(g_config.max_concurrent_tasks)
    async_tasks = []
    g_submitted_count = 0

    # 4. Process Tasks Concurrently (same logic, uses updated process_single_task)
    g_start_time = time.time()
    logging.info(f"Starting task processing with concurrency limit {g_config.max_concurrent_tasks}...")

    # Always process from dataset.json
    task_source = g_config.absolute_dataset_file
    logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
    try:
        task_generator = load_tasks_from_dataset(
            dataset_path=task_source,
            task_ids=g_config.task_ids,
            max_tasks=g_config.max_tasks
        )
        for i, task_item in enumerate(task_generator):
            # Pass total_tasks=None as we don't know the total count upfront from the generator easily
            coro = process_single_task(task_item, g_config, agent, semaphore, i, total_tasks=None)
            async_tasks.append(coro)
            g_submitted_count += 1

        logging.info(f"Submitted {g_submitted_count} tasks from dataset generator for processing.")
        if g_submitted_count == 0:
             logging.warning("No tasks were yielded from the dataset generator. Check filters or file content.")
             results_raw = [] # Ensure results_raw exists even if no tasks
        else:
             results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Error while iterating through dataset {task_source}: {e}", exc_info=True)
        return # Exit if dataset loading fails

    # 5. Wait for all tasks to complete (same logic, but results_raw might be empty)
    for res in results_raw:
        if isinstance(res, Exception):
            logging.error(f"Task failed with exception during gather/scheduling: {res}", exc_info=res)
        elif res is not None:
             logging.warning(f"Unexpected non-None item in results_raw after gather: {type(res)} - {res}")

    # 6. Log Final Summary (same logic, saving handled by atexit/signal)
    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0

    log_summary = (
        f"Finished processing loop. Submitted: {g_submitted_count}, "
        f"Successful: {g_successful_count}, Failed: {g_failed_count}, Skipped: {g_skipped_count}. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)
    logging.info("Code data generation loop complete. Final results will be saved on exit.") # Updated log message


# Modify the generate_code_data function signature to accept task_range
async def generate_code_data(args, task_range=None): # Renamed function to remove 'benchmark'
    """Generates ARC code data with concurrency control.""" # Updated docstring
    global g_config, g_start_time, g_model_value, g_submitted_count
    logging.info("Starting ARC Code Data Generation...") # Updated log message

    # 1. Load Configuration (updated for dataset.json only)
    try:
        g_config = ARCBenchmarkConfig(
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks, # Keep max_tasks in config for logging/metadata
            # use_dataset_json is removed
            dataset_directory=args.dataset_directory, # Use the renamed argument
            max_concurrent_tasks=args.max_concurrent_tasks
        )
        logging.info(f"Configuration loaded. Output directory: {g_config.output_directory}")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}")
        # Always using dataset.json now
        logging.info(f"Using dataset file: {g_config.absolute_dataset_file}")
        logging.info(f"Using model: {g_config.model_identifier}")
        if g_config.max_tasks is not None:
            logging.info(f"Maximum tasks to process (from --max_tasks): {g_config.max_tasks}")
        if task_range is not None:
             logging.info(f"Processing tasks within index range (from --tasks): {task_range}")
        elif g_config.max_tasks is None:
             logging.info("Processing all found/specified tasks (no max_tasks or tasks range limit).")

    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model (Use CodeGeneratingAgent)
    try:
        model_enum_member = ModelOption[g_config.model_identifier]
        g_model_value = model_enum_member.value

        model = get_model(g_config, role="main")
        # Instantiate the correct agent
        agent = CodeGeneratingAgent(model=model)
        logging.info(f"Initialized CodeGeneratingAgent with model: {g_config.model_identifier} ({g_model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return


    # 3. Prepare Task List/Iterator and Semaphore (same as before)
    semaphore = asyncio.Semaphore(g_config.max_concurrent_tasks)
    async_tasks = []
    g_submitted_count = 0

    # 4. Process Tasks Concurrently (same logic, uses updated process_single_task)
    g_start_time = time.time()
    logging.info(f"Starting task processing with concurrency limit {g_config.max_concurrent_tasks}...")

    # Always process from dataset.json
    task_source = g_config.absolute_dataset_file
    logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
    try:
        # Pass the task_range to the data loader
        task_generator = load_tasks_from_dataset(
            dataset_path=task_source,
            task_ids=g_config.task_ids,
            max_tasks=g_config.max_tasks, # Keep max_tasks for backward compatibility if needed, though --tasks overrides
            task_range=task_range # Pass the new range
        )
        for i, task_item in enumerate(task_generator):
            # Pass total_tasks=None as we don't know the total count upfront from the generator easily
            coro = process_single_task(task_item, g_config, agent, semaphore, i, total_tasks=None)
            async_tasks.append(coro)
            g_submitted_count += 1

        logging.info(f"Submitted {g_submitted_count} tasks from dataset generator for processing.")
        if g_submitted_count == 0:
             logging.warning("No tasks were yielded from the dataset generator. Check filters, range, or file content.")
             results_raw = [] # Ensure results_raw exists even if no tasks
        else:
             results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Error while iterating through dataset {task_source}: {e}", exc_info=True)
        return # Exit if dataset loading fails

    # 5. Wait for all tasks to complete (same logic, but results_raw might be empty)
    for res in results_raw:
        if isinstance(res, Exception):
            logging.error(f"Task failed with exception during gather/scheduling: {res}", exc_info=res)
        elif res is not None:
             logging.warning(f"Unexpected non-None item in results_raw after gather: {type(res)} - {res}")

    # 6. Log Final Summary (same logic, saving handled by atexit/signal)
    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0

    log_summary = (
        f"Finished processing loop. Submitted: {g_submitted_count}, "
        f"Successful: {g_successful_count}, Failed: {g_failed_count}, Skipped: {g_skipped_count}. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)
    logging.info("Code data generation loop complete. Final results will be saved on exit.") # Updated log message


if __name__ == "__main__":
    # --- Register Exit Handlers FIRST ---
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(save_final_results)
    logging.info("Registered signal handler for SIGINT and atexit handler for final save.")
    # --- End Exit Handlers ---


    # --- Argument Parsing (Updated description) ---
    parser = argparse.ArgumentParser(description="Generate ARC Code Data") # Updated description
    parser.add_argument(
        "--model_identifier",
        type=str,
        default=ModelOption.LOCAL_0.name,
        choices=[option.name for option in ModelOption],
        help=f"Model identifier to use (default: {ModelOption.LOCAL_0.name})"
    )
    # Add a mutually exclusive group for --max_tasks and --tasks
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--max_tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to process (default: process all)"
    )
    group.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Specify a range of tasks to process by index, e.g., [20:40] (inclusive start, exclusive end)"
    )
    # Removed --use_dataset_json argument
    parser.add_argument(
        "--dataset_directory", # Renamed argument
        type=str,
        default="../data", # Default points to the directory containing dataset.json
        help="Path to the directory containing dataset.json"
    )
    parser.add_argument(
        "--max_concurrent_tasks",
        type=int,
        default=5,
        help="Maximum number of tasks to process concurrently (default: 5)"
    )
    # --- End Argument Parsing ---

    args = parser.parse_args()

    # Parse the --tasks argument if provided
    task_range = None
    if args.tasks:
        try:
            # Expecting format [start:end]
            if not args.tasks.startswith('[') or not args.tasks.endswith(']'):
                raise ValueError("Invalid format. Expected [start:end]")
            range_str = args.tasks[1:-1] # Remove brackets
            start_str, end_str = range_str.split(':')
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else None
            if start < 0 or (end is not None and end < start):
                 raise ValueError("Invalid range values.")
            task_range = (start, end)
            logging.info(f"Parsed task range: {task_range}")
        except ValueError as e:
            logging.error(f"Error parsing --tasks argument: {e}. Please use format [start:end], e.g., [0:10] or [20:].")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Unexpected error parsing --tasks argument: {e}", exc_info=True)
            sys.exit(1)

    # Run the async function
    try:
        # Call the renamed main async function and pass the task_range
        asyncio.run(generate_code_data(args, task_range=task_range)) # Updated function call
    except KeyboardInterrupt:
        logging.info("Code data generation interrupted by user.") # Log message is okay
    except Exception as e:
        logging.error(f"Code data generation failed with an unexpected error: {e}", exc_info=True) # Log message is okay
