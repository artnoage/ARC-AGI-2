import os
import json
import logging
import time
import asyncio # Import asyncio
import argparse # Import argparse
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

# Removed DummyModel

async def process_single_task(item, config, agent, semaphore, index, total_tasks=None):
    """Processes a single task, acquiring the semaphore."""
    task_id = None
    async with semaphore: # Acquire semaphore before processing
        try:
            if config.use_dataset_json:
                # Item is already (task_id, task_data) from the generator
                task_id, task_data = item
                log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" (Dataset: {task_id})"
                logging.info(f"{log_prefix}: Acquired semaphore, processing...")
            else:
                # Item is a file_path, load the task
                file_path = item
                load_result = load_task(file_path) # is_dataset_json defaults to False
                if load_result is None:
                    logging.warning(f"Skipping task from file: {os.path.basename(file_path)}")
                    return None # Return None if task loading fails
                task_id, task_data = load_result
                log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" (File: {task_id})"
                logging.info(f"{log_prefix}: Acquired semaphore, processing...")

            # --- Agent Processing ---
            prompt_messages, reasoning = await agent.get_reasoning(task_data)
            # --- ---

            # Store results
            result_entry = {
                "task_id": task_id,
                "task_data": {
                    "train": task_data.get("train", []),
                    "test": task_data.get("test", [])
                },
                "prompt_messages": prompt_messages,
                "reasoning": None # Placeholder
            }

            if reasoning is not None:
                result_entry["reasoning"] = reasoning
                logging.info(f"{log_prefix}: Finished processing.")
            else:
                logging.warning(f"{log_prefix}: Skipping result due to processing error.")
                result_entry["reasoning"] = "ERROR: Failed to get reasoning."

            return result_entry

        except Exception as e:
            # Catch broader errors during the loop
            error_task_id = task_id if task_id else f"task_{index+1}" # Use index if task_id wasn't set yet
            log_prefix_err = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" ({error_task_id})"
            logging.error(f"{log_prefix_err}: Unexpected error processing task: {e}", exc_info=True) # Log traceback
            # Return error entry
            return {
                "task_id": error_task_id,
                "task_data": "Error during processing loop",
                "prompt_messages": None,
                "reasoning": f"ERROR: Exception during task processing loop: {e}"
            }
        # Semaphore is released automatically when exiting the 'async with' block


async def run_benchmark(args): # Make function async and accept args
    """Runs the ARC reasoning benchmark with concurrency control."""
    logging.info("Starting ARC Reasoning Benchmark...")

    # 1. Load Configuration using parsed args
    try:
        # Pass parsed arguments to the config constructor
        config = ARCBenchmarkConfig(
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks,
            use_dataset_json=args.use_dataset_json,
            task_directory=args.task_directory,
            max_concurrent_tasks=args.max_concurrent_tasks # Pass concurrency arg
            # Add other args here if needed, e.g., main_temp, main_port
        )
        logging.info(f"Configuration loaded. Output directory: {config.output_directory}")
        logging.info(f"Max concurrent tasks: {config.max_concurrent_tasks}") # Log concurrency limit
        if config.use_dataset_json:
            logging.info(f"Using dataset file: {config.absolute_dataset_file}")
        else:
            logging.info(f"Using task directory: {config.absolute_task_directory}")
        logging.info(f"Using model: {config.model_identifier}") # Log the actual model used
        if config.max_tasks is not None: # Check if max_tasks was set
            logging.info(f"Maximum tasks to process: {config.max_tasks}")
        else:
             logging.info("Processing all found/specified tasks (no max_tasks limit).")
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model
    try:
        # Get the model value (full name) from the ModelOption enum
        model_enum_member = ModelOption[config.model_identifier]
        model_value = model_enum_member.value  # e.g., "google/gemini-2.5-flash-preview"
        
        # Use get_model to initialize the actual model
        model = get_model(config, role="main")
        agent = SimpleAgent(model=model)
        logging.info(f"Initialized SimpleAgent with model: {config.model_identifier} ({model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return


    # 3. Prepare Task List/Iterator and Semaphore
    semaphore = asyncio.Semaphore(config.max_concurrent_tasks)
    async_tasks = [] # List to hold the asyncio tasks to be gathered
    submitted_count = 0 # Count tasks submitted for processing

    # 4. Process Tasks Concurrently
    start_time = time.time()
    logging.info(f"Starting task processing with concurrency limit {config.max_concurrent_tasks}...")

    if config.use_dataset_json:
        task_source = config.absolute_dataset_file
        logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
        try:
            # Iterate directly over the generator, don't load all into memory
            task_generator = load_tasks_from_dataset(
                dataset_path=task_source,
                task_ids=config.task_ids,
                max_tasks=config.max_tasks
            )
            for i, task_item in enumerate(task_generator):
                # Create the coroutine for this task
                coro = process_single_task(task_item, config, agent, semaphore, i) # Removed total_tasks arg
                async_tasks.append(coro)
                submitted_count += 1
            logging.info(f"Submitted {submitted_count} tasks from dataset for processing.")
            if submitted_count == 0:
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
        task_source = config.absolute_task_directory
        logging.info(f"Processing tasks from directory: {task_source}")
        try:
            task_files = get_task_files( # This returns a list of file paths
                task_directory=task_source,
                task_ids=config.task_ids,
                max_tasks=config.max_tasks
            )
            submitted_count = len(task_files) # We know the count upfront here
            if not task_files:
                logging.warning("No task files found or specified. Exiting.")
                return
            logging.info(f"Prepared {submitted_count} task files to process.")

            # Create coroutine tasks for each file path
            async_tasks = [
                process_single_task(file_path, config, agent, semaphore, i, submitted_count)
                for i, file_path in enumerate(task_files)
            ]
            # Run tasks concurrently and gather results
            results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

        except Exception as e:
            logging.error(f"Error processing tasks from directory {task_source}: {e}", exc_info=True)
            return

    # 5. Process Results
    results = []
    successful_count = 0
    failed_count = 0
    skipped_count = 0 # Count tasks that returned None (e.g., load_task failed)

    for res in results_raw:
        if isinstance(res, Exception):
            logging.error(f"Task failed with exception during gather: {res}", exc_info=res)
            failed_count += 1
            # Add an error entry to results
            results.append({
                "task_id": "UNKNOWN_TASK_ERROR",
                "task_data": "Error during asyncio.gather",
                "prompt_messages": None,
                "reasoning": f"ERROR: Exception during task execution: {res}"
            })
        elif res is None:
            # Task was likely skipped intentionally (e.g., load_task failed in process_single_task)
            skipped_count += 1
        elif isinstance(res, dict) and res.get("reasoning", "").startswith("ERROR:"):
             # Task processed but resulted in an error captured within process_single_task
             results.append(res)
             failed_count += 1
        elif isinstance(res, dict): # Successful result
            results.append(res)
            successful_count += 1
        else:
             logging.warning(f"Unexpected item in results_raw: {type(res)} - {res}")
             failed_count += 1 # Count unexpected results as failures

    end_time = time.time()
    total_time = end_time - start_time

    log_summary = (
        f"Finished processing. Submitted: {submitted_count}, "
        f"Successful: {successful_count}, Failed: {failed_count}, Skipped: {skipped_count}. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)


    # 6. Save Results
    # Add metadata to results
    metadata = {
        "model_identifier": config.model_identifier,
        "model_username": model_value,  # The full model name/path as it appears in the config
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "max_tasks_requested": config.max_tasks, # How many were asked for
        "tasks_submitted": submitted_count, # How many were actually submitted
        "tasks_successful": successful_count,
        "tasks_failed": failed_count,
        "tasks_skipped": skipped_count,
        "task_source": "dataset.json" if config.use_dataset_json else "directory",
        "max_concurrent_tasks": config.max_concurrent_tasks, # Add concurrency info to metadata
        "total_runtime_seconds": round(total_time, 2)
    }

    results_filename = f"benchmark_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    results_path = os.path.join(config.output_directory, results_filename)
    try:
        # Create the final output structure with metadata and results
        output = {
            "metadata": metadata,
            "results": results # Contains only successful or error-captured results
        }

        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        logging.info(f"Benchmark results saved to: {results_path}")
    except Exception as e:
        logging.error(f"Failed to save results: {e}")

    logging.info("Benchmark run complete.")

if __name__ == "__main__":
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
