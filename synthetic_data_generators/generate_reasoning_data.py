import os
import json
import logging
import time
import asyncio # Import asyncio
import argparse # Import argparse
import signal # Import signal for handling Ctrl+C
import sys # Import sys for exiting from signal handler
import atexit # Import atexit for saving on normal exit

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
from agents.reasoning_trace_generator import SimpleAgent # Keep this path
# Import get_model
from utilities.model_utils import get_model # Updated import path

# Configure logging
# Set to DEBUG level to capture all the detailed logs we've added
# Define log path relative to this script's directory -> project_root/synthetic_data_generators/synthetic_data/
log_dir = os.path.join(project_root, "synthetic_data_generators", "synthetic_data")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "reasoning_data_generation.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='w'),  # Save logs to the new path, overwrite each run
        logging.StreamHandler()  # Also output to console
    ]
)
logging.info(f"Logging configured at DEBUG level. Log file: {log_file_path}")

# --- Global State for Saving ---
g_results = []
g_config = None
g_start_time = None
g_model_value = None
g_successful_count = 0
g_failed_count = 0
g_skipped_count = 0
g_submitted_count = 0
g_is_saving = False # Lock to prevent concurrent saves
g_last_saved_results_len = 0 # Track length of g_results at last periodic save
g_timestamp = time.strftime("%Y%m%d_%H%M%S")  # Generate timestamp once at the beginning
SAVE_INTERVAL = 10 # Save results every N successful tasks
# --- End Global State ---

# --- Helper Functions for Saving ---

def save_results_helper(output_data, output_path):
    """Handles the actual writing of the JSON file."""
    global g_is_saving
    if g_is_saving:
        logging.warning("Already saving, skipping concurrent save request.")
        return False
    g_is_saving = True
    try:
        # Define the subdirectory and filename
        subdirectory = "reasoning_data" # Subdirectory for reasoning results
        partial_filename = "reasoning_data_partial_results.jsonl" # Use .jsonl extension, removed 'benchmark'
        # Construct the full path including the subdirectory within the main output directory
        partial_path = os.path.join(g_config.output_directory, subdirectory, partial_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        logging.info(f"Results saved to: {output_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save results to {output_path}: {e}", exc_info=True)
        return False
    finally:
        g_is_saving = False # Release lock

def save_periodic_results():
    """Appends new results to the results file in JSON Lines format."""
    global g_is_saving, g_last_saved_results_len, g_timestamp # Need to modify global lock and index tracker

    if g_config is None or len(g_results) <= g_last_saved_results_len:
        logging.debug("Periodic save check: No new results to append.")
        return # Nothing new to save

    if g_is_saving:
        logging.warning("Already saving, skipping concurrent periodic save request.")
        return

    g_is_saving = True # Acquire lock
    new_results_to_save = g_results[g_last_saved_results_len:]
    num_new_results = len(new_results_to_save)
    logging.debug(f"Attempting periodic save: Appending {num_new_results} new results...")

    try:
        # Define the subdirectory and filename
        subdirectory = "reasoning_data" # Subdirectory for reasoning results
        results_filename = f"reasoning_data_results_{g_timestamp}.jsonl"
        # Construct the full path including the subdirectory within the main output directory
        results_path = os.path.join(g_config.output_directory, subdirectory, results_filename)

        # Ensure output directory exists (including subdirectory)
        output_dir = os.path.dirname(results_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

        # Append new results line by line
        with open(results_path, 'a', encoding='utf-8') as f:
            for result_entry in new_results_to_save:
                f.write(json.dumps(result_entry) + '\n')

        logging.info(f"Appended {num_new_results} results to file: {results_path}")
        g_last_saved_results_len = len(g_results) # Update the index tracker

    except Exception as e:
        logging.error(f"Failed to append results to {results_path}: {e}", exc_info=True)
    finally:
        g_is_saving = False # Release lock

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
        "benchmark_type": "reasoning_generation",
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
    subdirectory = "reasoning_data" # Subdirectory for reasoning results
    results_filename = f"reasoning_data_results_{g_timestamp}.jsonl"
    # Construct the full path including the subdirectory within the main output directory
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
    sys.exit(1) # Exit after saving

# --- End Helper Functions ---


# Removed DummyModel

async def process_single_task(item, config, agent, semaphore, index, total_tasks=None):
    """Processes a single task, acquiring the semaphore, and updates global results."""
    global g_results, g_successful_count, g_failed_count, g_skipped_count # Declare globals we modify
    task_id = None
    async with semaphore: # Acquire semaphore before processing
        try:
            # Item is now always a tuple (task_id, task_data) from load_tasks_from_dataset
            task_id, task_data = item
            log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" (Dataset: {task_id})"
            logging.debug(f"{log_prefix}: Acquired semaphore, processing...")

            # --- Agent Processing ---
            prompt_messages, reasoning = await agent.get_reasoning(task_data)
            # --- ---

            # Prepare result entry
            result_entry = {
                "task_id": task_id,
                "task_data": { # Store only necessary parts if needed, or keep full data
                    "train": task_data.get("train", []),
                    "test": task_data.get("test", [])
                },
                "prompt_messages": prompt_messages,
                "reasoning": None # Placeholder
            }

            if reasoning is not None:
                result_entry["reasoning"] = reasoning
                g_results.append(result_entry) # Append successful result
                g_successful_count += 1
                logging.info(f"{log_prefix}: Finished processing successfully.")
                # Check if it's time for a periodic save
                if g_successful_count % SAVE_INTERVAL == 0:
                    save_periodic_results()
            else:
                # Agent failed to get reasoning
                result_entry["reasoning"] = "ERROR: Failed to get reasoning."
                g_results.append(result_entry) # Append error result
                g_failed_count += 1
                logging.warning(f"{log_prefix}: Finished processing with error (failed to get reasoning).")

            # No need to return the result entry, it's added to the global list

        except Exception as e:
            # Catch broader errors during the loop
            error_task_id = task_id if task_id else f"task_{index+1}"
            log_prefix_err = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" ({error_task_id})"
            logging.error(f"{log_prefix_err}: Unexpected error processing task: {e}", exc_info=True)
            # Append error entry to global results
            g_results.append({
                "task_id": error_task_id,
                "task_data": "Error during processing loop",
                "prompt_messages": None,
                "reasoning": f"ERROR: Exception during task processing loop: {e}"
            })
            g_failed_count += 1
        # Semaphore is released automatically when exiting the 'async with' block
        # No return value needed as results are handled globally


async def run_benchmark(args): # Make function async and accept args
    """Runs the ARC reasoning benchmark with concurrency control."""
    global g_config, g_start_time, g_model_value, g_submitted_count # Declare globals we modify
    logging.info("Starting ARC Reasoning Benchmark...")

    # 1. Load Configuration using parsed args (updated for dataset.json only)
    try:
        # Pass parsed arguments to the config constructor
        g_config = ARCBenchmarkConfig( # Assign to global config
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks,
            # use_dataset_json is removed
            dataset_directory=args.dataset_directory, # Use the renamed argument
            max_concurrent_tasks=args.max_concurrent_tasks # Pass concurrency arg
            # Add other args here if needed, e.g., main_temp, main_port
        )
        logging.info(f"Configuration loaded. Output directory: {g_config.output_directory}")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}") # Log concurrency limit
        # Always using dataset.json now
        logging.info(f"Using dataset file: {g_config.absolute_dataset_file}")
        logging.info(f"Using model: {g_config.model_identifier}") # Log the actual model used
        if g_config.max_tasks is not None: # Check if max_tasks was set
            logging.info(f"Maximum tasks to process: {g_config.max_tasks}")
        else:
             logging.info("Processing all found/specified tasks (no max_tasks limit).")
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model
    try:
        # Get the model value (full name) from the ModelOption enum
        model_enum_member = ModelOption[g_config.model_identifier]
        g_model_value = model_enum_member.value  # Assign to global
        
        # Use get_model to initialize the actual model
        model = get_model(g_config, role="main") # Use global config
        agent = SimpleAgent(model=model)
        logging.info(f"Initialized SimpleAgent with model: {g_config.model_identifier} ({g_model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return


    # 3. Prepare Task List/Iterator and Semaphore
    semaphore = asyncio.Semaphore(g_config.max_concurrent_tasks) # Use global config
    async_tasks = [] # List to hold the asyncio tasks to be gathered
    g_submitted_count = 0 # Use global count

    # 4. Process Tasks Concurrently
    g_start_time = time.time() # Assign to global start time
    logging.info(f"Starting task processing with concurrency limit {g_config.max_concurrent_tasks}...")

    # Always process from dataset.json
    task_source = g_config.absolute_dataset_file # Use global config
    logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
    try:
        # Iterate directly over the generator, don't load all into memory
        task_generator = load_tasks_from_dataset(
            dataset_path=task_source,
            task_ids=g_config.task_ids, # Use global config
            max_tasks=g_config.max_tasks # Use global config
        )
        for i, task_item in enumerate(task_generator):
            # Create the coroutine for this task
            # Pass total_tasks=None as we don't know the total count upfront from the generator easily
            coro = process_single_task(task_item, g_config, agent, semaphore, i, total_tasks=None)
            async_tasks.append(coro)
            g_submitted_count += 1 # Use global count

        logging.info(f"Submitted {g_submitted_count} tasks from dataset generator for processing.")
        if g_submitted_count == 0:
             logging.warning("No tasks were yielded from the dataset generator. Check filters or file content.")
             # No need to run gather if no tasks were submitted
             results_raw = []
        else:
             # Run tasks concurrently and gather results
             results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Error while iterating through dataset {task_source}: {e}", exc_info=True)
        return # Exit if dataset iteration fails

    # 5. Wait for all tasks to complete (same logic, but results_raw might be empty)
    # The results_raw variable now primarily holds exceptions if any occurred during gather,
    # or None if the coroutine finished without returning (which is our case now).
    # Actual results are in g_results. We just need to log any gather-level exceptions.
    for res in results_raw:
        if isinstance(res, Exception):
            # These are exceptions that happened *outside* the try/except in process_single_task,
            # likely during the asyncio scheduling or semaphore handling itself.
            logging.error(f"Task failed with exception during gather/scheduling: {res}", exc_info=res)
            # We don't have task_id here, but the error is logged.
            # We could potentially increment g_failed_count here too, but it might double-count
            # if the exception also caused process_single_task to log an error.
            # Let's rely on the logging within process_single_task for counts.
        elif res is not None:
             # This shouldn't happen anymore as process_single_task doesn't return.
             logging.warning(f"Unexpected non-None item in results_raw after gather: {type(res)} - {res}")

    # 6. Log Final Summary (Saving is handled by atexit/signal)
    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0 # Use global start time

    log_summary = (
        f"Finished processing loop. Submitted: {g_submitted_count}, "
        f"Successful: {g_successful_count}, Failed: {g_failed_count}, Skipped: {g_skipped_count}. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)
    # Final saving will be triggered by atexit handler automatically now.
    logging.info("Benchmark run loop complete. Final results will be saved on exit.")


# Modify the run_benchmark function signature to accept task_range
async def run_benchmark(args, task_range=None): # Make function async and accept args
    """Runs the ARC reasoning benchmark with concurrency control."""
    global g_config, g_start_time, g_model_value, g_submitted_count # Declare globals we modify
    logging.info("Starting ARC Reasoning Benchmark...")

    # 1. Load Configuration using parsed args (updated for dataset.json only)
    try:
        # Pass parsed arguments to the config constructor
        g_config = ARCBenchmarkConfig( # Assign to global config
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks, # Keep max_tasks in config for logging/metadata
            # use_dataset_json is removed
            dataset_directory=args.dataset_directory, # Use the renamed argument
            max_concurrent_tasks=args.max_concurrent_tasks # Pass concurrency arg
            # Add other args here if needed, e.g., main_temp, main_port
        )
        logging.info(f"Configuration loaded. Output directory: {g_config.output_directory}")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}") # Log concurrency limit
        # Always using dataset.json now
        logging.info(f"Using dataset file: {g_config.absolute_dataset_file}")
        logging.info(f"Using model: {g_config.model_identifier}") # Log the actual model used
        if g_config.max_tasks is not None: # Check if max_tasks was set
            logging.info(f"Maximum tasks to process (from --max_tasks): {g_config.max_tasks}")
        if task_range is not None:
             logging.info(f"Processing tasks within index range (from --tasks): {task_range}")
        elif g_config.max_tasks is None:
             logging.info("Processing all found/specified tasks (no max_tasks or tasks range limit).")

    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model
    try:
        # Get the model value (full name) from the ModelOption enum
        model_enum_member = ModelOption[g_config.model_identifier]
        g_model_value = model_enum_member.value  # Assign to global
        
        # Use get_model to initialize the actual model
        model = get_model(g_config, role="main") # Use global config
        agent = SimpleAgent(model=model)
        logging.info(f"Initialized SimpleAgent with model: {g_config.model_identifier} ({g_model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return


    # 3. Prepare Task List/Iterator and Semaphore
    semaphore = asyncio.Semaphore(g_config.max_concurrent_tasks) # Use global config
    async_tasks = [] # List to hold the asyncio tasks to be gathered
    g_submitted_count = 0 # Use global count

    # 4. Process Tasks Concurrently
    g_start_time = time.time() # Assign to global start time
    logging.info(f"Starting task processing with concurrency limit {g_config.max_concurrent_tasks}...")

    # Always process from dataset.json
    task_source = g_config.absolute_dataset_file # Use global config
    logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
    try:
        # Iterate directly over the generator, don't load all into memory
        # Pass the task_range to the data loader
        task_generator = load_tasks_from_dataset(
            dataset_path=task_source,
            task_ids=g_config.task_ids, # Use global config
            max_tasks=g_config.max_tasks, # Keep max_tasks for backward compatibility if needed, though --tasks overrides
            task_range=task_range # Pass the new range
        )
        for i, task_item in enumerate(task_generator):
            # Create the coroutine for this task
            # Pass total_tasks=None as we don't know the total count upfront from the generator easily
            coro = process_single_task(task_item, g_config, agent, semaphore, i, total_tasks=None)
            async_tasks.append(coro)
            g_submitted_count += 1 # Use global count

        logging.info(f"Submitted {g_submitted_count} tasks from dataset generator for processing.")
        if g_submitted_count == 0:
             logging.warning("No tasks were yielded from the dataset generator. Check filters, range, or file content.")
             # No need to run gather if no tasks were submitted
             results_raw = []
        else:
             # Run tasks concurrently and gather results
             results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Error while iterating through dataset {task_source}: {e}", exc_info=True)
        return # Exit if dataset iteration fails

    # 5. Wait for all tasks to complete (same logic, but results_raw might be empty)
    # The results_raw variable now primarily holds exceptions if any occurred during gather,
    # or None if the coroutine finished without returning (which is our case now).
    # Actual results are in g_results. We just need to log any gather-level exceptions.
    for res in results_raw:
        if isinstance(res, Exception):
            # These are exceptions that happened *outside* the try/except in process_single_task,
            # likely during the asyncio scheduling or semaphore handling itself.
            logging.error(f"Task failed with exception during gather/scheduling: {res}", exc_info=res)
            # We don't have task_id here, but the error is logged.
            # We could potentially increment g_failed_count here too, but it might double-count
            # if the exception also caused process_single_task to log an error.
            # Let's rely on the logging within process_single_task for counts.
        elif res is not None:
             # This shouldn't happen anymore as process_single_task doesn't return.
             logging.warning(f"Unexpected non-None item in results_raw after gather: {type(res)} - {res}")

    # 6. Log Final Summary (Saving is handled by atexit/signal)
    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0 # Use global start time

    log_summary = (
        f"Finished processing loop. Submitted: {g_submitted_count}, "
        f"Successful: {g_successful_count}, Failed: {g_failed_count}, Skipped: {g_skipped_count}. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)
    # Final saving will be triggered by atexit handler automatically now.
    logging.info("Benchmark run loop complete. Final results will be saved on exit.")


if __name__ == "__main__":
    # --- Register Exit Handlers FIRST ---
    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    # Register the final save function to be called on normal exit
    atexit.register(save_final_results)
    logging.info("Registered signal handler for SIGINT and atexit handler for final save.")
    # --- End Exit Handlers ---


    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run ARC Reasoning Benchmark")
    parser.add_argument(
        "--model_identifier",
        type=str,
        default=ModelOption.LOCAL_0.name, # Default from config
        choices=[option.name for option in ModelOption], # Use enum names as choices
        help=f"Model identifier to use (default: {ModelOption.LOCAL_0.name})"
    )
    # Add a mutually exclusive group for --max_tasks and --tasks
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--max_tasks",
        type=int,
        default=None, # Default from config
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
        default=5, # Default from config
        help="Maximum number of tasks to process concurrently (default: 5)"
    )
    # Add arguments for other config options if needed, e.g.:
    # parser.add_argument("--main_temp", type=float, default=0.0, help="Main model temperature")


    args = parser.parse_args()
    # --- End Argument Parsing ---

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

    # Run the async function using asyncio.run() and pass parsed args and task_range
    try:
        asyncio.run(run_benchmark(args, task_range=task_range))
    except KeyboardInterrupt:
        logging.info("Benchmark run interrupted by user.")
    except Exception as e:
        logging.error(f"Benchmark failed with an unexpected error: {e}", exc_info=True)


    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run ARC Reasoning Benchmark")
    parser.add_argument(
        "--model_identifier",
        type=str,
        default=ModelOption.LOCAL_0.name, # Default from config
        choices=[option.name for option in ModelOption], # Use enum names as choices
        help=f"Model identifier to use (default: {ModelOption.LOCAL_0.name})"
    )
    parser.add_argument(
        "--max_tasks",
        type=int,
        default=None, # Default from config
        help="Maximum number of tasks to process (default: process all)"
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
        default=5, # Default from config
        help="Maximum number of tasks to process concurrently (default: 5)"
    )
    # Add arguments for other config options if needed, e.g.:
    # parser.add_argument("--main_temp", type=float, default=0.0, help="Main model temperature")


    args = parser.parse_args()
    # --- End Argument Parsing ---

    # Run the async function using asyncio.run() and pass parsed args
    try:
        asyncio.run(run_benchmark(args))
    except KeyboardInterrupt:
        logging.info("Benchmark run interrupted by user.")
    except Exception as e:
        logging.error(f"Benchmark failed with an unexpected error: {e}", exc_info=True)
