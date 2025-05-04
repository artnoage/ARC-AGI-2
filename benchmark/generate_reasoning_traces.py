import os
import json
import logging
import time
import asyncio # Import asyncio
import argparse # Import argparse
import signal # Import signal for handling Ctrl+C
import sys # Import sys for exiting from signal handler
import atexit # Import atexit for saving on normal exit
from config import ARCBenchmarkConfig, ModelOption # Import ModelOption for choices
from data_loader import get_task_files, load_task, load_tasks_from_dataset # Ensure load_tasks_from_dataset is imported
from simple_agent import SimpleAgent
# Import get_model
from model_utils import get_model

# Configure logging
# Set to DEBUG level to capture all the detailed logs we've added
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("benchmark_debug.log"),  # Save logs to a file
        logging.StreamHandler()  # Also output to console
    ]
)
logging.info("Logging configured at DEBUG level")

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
        # Ensure output directory exists
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
        g_is_saving = False # Release lock

def save_periodic_results():
    """Appends new results to a partial file in JSON Lines format."""
    global g_is_saving, g_last_saved_results_len # Need to modify global lock and index tracker

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
        partial_filename = "benchmark_partial_results.jsonl" # Use .jsonl extension
        partial_path = os.path.join(g_config.output_directory, partial_filename)

        # Ensure output directory exists
        output_dir = os.path.dirname(partial_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

        # Append new results line by line
        with open(partial_path, 'a', encoding='utf-8') as f:
            for result_entry in new_results_to_save:
                f.write(json.dumps(result_entry) + '\n')

        logging.info(f"Appended {num_new_results} results to partial file: {partial_path}")
        g_last_saved_results_len = len(g_results) # Update the index tracker

    except Exception as e:
        logging.error(f"Failed to append results to {partial_path}: {e}", exc_info=True)
    finally:
        g_is_saving = False # Release lock

def save_final_results(interrupted=False):
    """Saves the final, complete results to a timestamped JSON file."""
    if g_config is None or not g_results:
        logging.info("No results to save or config not loaded.")
        return # Nothing to save

    status = "interrupted" if interrupted else "completed"
    logging.info(f"Attempting final save (status: {status})...")

    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0

    metadata = {
        "status": status,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_identifier": g_config.model_identifier,
        "model_username": g_model_value,
        "max_tasks_requested": g_config.max_tasks,
        "tasks_submitted": g_submitted_count,
        "tasks_successful": g_successful_count,
        "tasks_failed": g_failed_count,
        "tasks_skipped": g_skipped_count,
        "task_source": "dataset.json" if g_config.use_dataset_json else "directory",
        "max_concurrent_tasks": g_config.max_concurrent_tasks,
        "total_runtime_seconds": round(total_time, 2)
    }
    output = {"metadata": metadata, "results": g_results} # Use global results
    final_filename_suffix = "_interrupted" if interrupted else ""
    final_filename = f"benchmark_results_{time.strftime('%Y%m%d_%H%M%S')}{final_filename_suffix}.json"
    final_path = os.path.join(g_config.output_directory, final_filename)
    save_results_helper(output, final_path)

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
            if config.use_dataset_json:
                # Item is already (task_id, task_data) from the generator
                task_id, task_data = item
                log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" (Dataset: {task_id})"
                logging.debug(f"{log_prefix}: Acquired semaphore, processing...") # Changed to debug for less noise
            else:
                # Item is a file_path, load the task
                file_path = item
                load_result = load_task(file_path) # is_dataset_json defaults to False
                if load_result is None:
                    logging.warning(f"Skipping task from file: {os.path.basename(file_path)}")
                    g_skipped_count += 1 # Increment skipped count
                    return None # Return None if task loading fails
                task_id, task_data = load_result
                log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" (File: {task_id})"
                logging.debug(f"{log_prefix}: Acquired semaphore, processing...") # Changed to debug

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

    # 1. Load Configuration using parsed args
    try:
        # Pass parsed arguments to the config constructor
        g_config = ARCBenchmarkConfig( # Assign to global config
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks,
            use_dataset_json=args.use_dataset_json,
            task_directory=args.task_directory,
            max_concurrent_tasks=args.max_concurrent_tasks # Pass concurrency arg
            # Add other args here if needed, e.g., main_temp, main_port
        )
        logging.info(f"Configuration loaded. Output directory: {g_config.output_directory}")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}") # Log concurrency limit
        if g_config.use_dataset_json:
            logging.info(f"Using dataset file: {g_config.absolute_dataset_file}")
        else:
            logging.info(f"Using task directory: {g_config.absolute_task_directory}")
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

    if g_config.use_dataset_json: # Use global config
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
                coro = process_single_task(task_item, g_config, agent, semaphore, i) # Use global config
                async_tasks.append(coro)
                g_submitted_count += 1 # Use global count
            logging.info(f"Submitted {g_submitted_count} tasks from dataset for processing.")
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

    else: # Processing from directory
        task_source = g_config.absolute_task_directory # Use global config
        logging.info(f"Processing tasks from directory: {task_source}")
        try:
            task_files = get_task_files( # This returns a list of file paths
                task_directory=task_source,
                task_ids=g_config.task_ids, # Use global config
                max_tasks=g_config.max_tasks # Use global config
            )
            g_submitted_count = len(task_files) # Assign to global count
            if not task_files:
                logging.warning("No task files found or specified. Exiting.")
                return
            logging.info(f"Prepared {g_submitted_count} task files to process.")

            # Create coroutine tasks for each file path
            async_tasks = [
                process_single_task(file_path, g_config, agent, semaphore, i, g_submitted_count) # Use global config and count
                for i, file_path in enumerate(task_files)
            ]
            # Run tasks concurrently and gather results
            results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

        except Exception as e:
            logging.error(f"Error processing tasks from directory {task_source}: {e}", exc_info=True)
            return

    # 5. Wait for all tasks to complete
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
    parser.add_argument(
        "--max_tasks",
        type=int,
        default=None, # Default from config
        help="Maximum number of tasks to process (default: process all)"
    )
    parser.add_argument(
        "--use_dataset_json",
        action='store_true', # Makes it a boolean flag
        help="Load tasks from dataset.json instead of individual files in task_directory"
    )
    parser.add_argument(
        "--task_directory",
        type=str,
        default="../data/training", # Default from config
        help="Path to task directory (if not using --use_dataset_json) or parent directory of dataset.json (if using --use_dataset_json)"
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
