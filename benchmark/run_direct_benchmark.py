import os
import json
import logging
import time
import asyncio
import argparse
import signal
import sys
import atexit
import traceback

# --- Project Setup ---
# Add project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Imports ---
from utilities.config import ARCBenchmarkConfig, ModelOption
from utilities.data_loader import load_tasks_from_dataset
from agents.direct_answer_generator import DirectAnswerAgent
from utilities.model_utils import get_model
# Import the grid comparison utility
from utilities.code_execution import compare_grids

# --- Logging Configuration ---
# Define log path within the benchmark directory
log_dir = os.path.join(project_root, "benchmark", "benchmark_logs")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "direct_benchmark_run.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='w'),
        logging.StreamHandler()
    ]
)
logging.info(f"Logging configured for Direct Answer Benchmark Run. Log file: {log_file_path}")

# --- Global State for Saving ---
g_results = []
g_config = None
g_start_time = None
g_model_value = None
g_submitted_count = 0
# Counters specific to this benchmark run
g_generation_successful_count = 0
g_generation_failed_count = 0
g_answer_correct_count = 0
g_answer_incorrect_count = 0
g_is_saving = False
g_last_saved_results_len = 0
g_timestamp = time.strftime("%Y%m%d_%H%M%S")  # Generate timestamp once at the beginning
SAVE_INTERVAL = 5
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
        # Define the subdirectory and filename for benchmark results
        base_output_dir = os.path.join(project_root, "benchmark", "benchmark_results")
        subdirectory = "direct_benchmark"
        results_filename = f"direct_benchmark_results_{g_timestamp}.jsonl"
        results_path = os.path.join(base_output_dir, subdirectory, results_filename)

        # Ensure output directory exists
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

    # Calculate final answer accuracy stats
    total_answers = g_answer_correct_count + g_answer_incorrect_count
    accuracy_rate = (g_answer_correct_count / total_answers * 100) if total_answers > 0 else 0

    metadata = {
        "entry_type": "metadata",
        "benchmark_type": "direct_answer_generation",
        "status": status,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_identifier": g_config.model_identifier,
        "model_username": g_model_value,
        "max_tasks_requested": g_config.max_tasks,
        "tasks_submitted": g_submitted_count,
        "generation_successful": g_generation_successful_count,
        "generation_failed": g_generation_failed_count,
        "answer_correct": g_answer_correct_count,
        "answer_incorrect": g_answer_incorrect_count,
        "accuracy_rate_percent": round(accuracy_rate, 2),
        "task_source": "dataset.json",
        "max_concurrent_tasks": g_config.max_concurrent_tasks,
        "total_runtime_seconds": round(total_time, 2)
    }

    # Define the subdirectory and filename for benchmark results
    base_output_dir = os.path.join(project_root, "benchmark", "benchmark_results")
    subdirectory = "direct_benchmark"
    results_filename = f"direct_benchmark_results_{g_timestamp}.jsonl"
    # Construct the full path
    results_path = os.path.join(base_output_dir, subdirectory, results_filename)
    
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


async def process_single_task(item, config, agent, semaphore, index, total_tasks=None, best_of=1):
    """
    Processes a single task: generates direct answer, compares with expected output, and updates global results.
    Handles multiple generation attempts if best_of > 1.
    """
    global g_results, g_generation_successful_count, g_generation_failed_count, \
           g_answer_correct_count, g_answer_incorrect_count

    task_id = None
    task_start_time = time.time()
    log_prefix = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "")

    async with semaphore:
        try:
            task_id, task_data = item
            log_prefix += f" (Dataset: {task_id})"
            logging.debug(f"{log_prefix}: Acquired semaphore, processing...")

            # --- Prepare Base Result Entry ---
            result_entry = {
                "task_id": task_id,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "task_data": {
                    "train": task_data.get("train", []),
                    "test": task_data.get("test", [])
                },
                "best_of": best_of,
                "prompt_messages": [],
                "reasoning": [],
                "output_grid": [],
                "generation_time_seconds": [],
                "answer_correct": [],
                "comparison_details": []
            }

            # --- Direct Answer Generation and Verification (Loop for best_of) ---
            for attempt in range(best_of):
                attempt_log_prefix = f"{log_prefix} (Attempt {attempt+1}/{best_of})"
                logging.debug(f"{attempt_log_prefix}: Starting generation and verification...")

                generation_start_time = time.time()
                try:
                    prompt_messages, reasoning, output_grid = await agent.get_reasoning_and_answer(task_data)
                    generation_end_time = time.time()
                    generation_time = generation_end_time - generation_start_time
                    logging.debug(f"{attempt_log_prefix}: Answer generation took {generation_time:.2f}s")

                    result_entry["prompt_messages"].append(prompt_messages)
                    result_entry["reasoning"].append(reasoning if reasoning is not None else "ERROR: Failed to get reasoning.")
                    result_entry["output_grid"].append(output_grid if output_grid is not None else None)
                    result_entry["generation_time_seconds"].append(round(generation_time, 2))

                    if output_grid is not None:
                        g_generation_successful_count += 1
                        logging.info(f"{attempt_log_prefix}: Answer generation successful.")

                        # Compare with expected output
                        expected_output = task_data["test"][0]["output"]
                        is_correct = compare_grids(output_grid, expected_output)
                        
                        result_entry["answer_correct"].append(is_correct)
                        comparison_details = {
                            "expected_output": expected_output,
                            "actual_output": output_grid,
                            "match": is_correct
                        }
                        result_entry["comparison_details"].append(comparison_details)

                        # Update answer counters
                        if is_correct:
                            g_answer_correct_count += 1
                            logging.info(f"{attempt_log_prefix}: Answer is CORRECT.")
                        else:
                            g_answer_incorrect_count += 1
                            logging.warning(f"{attempt_log_prefix}: Answer is INCORRECT.")
                    else:
                        # Answer generation failed for this attempt
                        g_generation_failed_count += 1
                        logging.warning(f"{attempt_log_prefix}: Answer generation FAILED.")
                        result_entry["answer_correct"].append(False)
                        result_entry["comparison_details"].append({
                            "expected_output": task_data["test"][0]["output"],
                            "actual_output": None,
                            "match": False,
                            "error": "Failed to generate answer"
                        })

                except Exception as e:
                    # Catch errors during generation or verification for this attempt
                    error_message = f"ERROR: Exception during attempt {attempt+1}: {e}"
                    logging.error(f"{attempt_log_prefix}: {error_message}\n{traceback.format_exc()}")
                    result_entry["prompt_messages"].append(None)
                    result_entry["reasoning"].append(error_message)
                    result_entry["output_grid"].append(None)
                    result_entry["generation_time_seconds"].append(None)
                    result_entry["answer_correct"].append(False)
                    result_entry["comparison_details"].append({
                        "expected_output": task_data["test"][0]["output"] if "test" in task_data and task_data["test"] else None,
                        "actual_output": None,
                        "match": False,
                        "error": error_message
                    })
                    g_generation_failed_count += 1

            # --- Finalize Result for the Task ---
            task_end_time = time.time()
            total_processing_time = task_end_time - task_start_time
            result_entry["total_processing_time_seconds"] = round(total_processing_time, 2)
            g_results.append(result_entry)

            # Check for periodic save
            if len(g_results) % SAVE_INTERVAL == 0 and len(g_results) > g_last_saved_results_len:
                 save_periodic_results()

        except Exception as e:
            # Catch broader errors during the task processing loop itself
            error_task_id = task_id if task_id else f"task_{index+1}"
            log_prefix_err = f"Task {index+1}" + (f"/{total_tasks}" if total_tasks else "") + f" ({error_task_id})"
            logging.error(f"{log_prefix_err}: Unexpected error processing task: {e}\n{traceback.format_exc()}")
            # Append error entry with full structure, using lists for all response fields
            error_message = f"ERROR: Exception during task processing loop: {e}"
            g_results.append({
                "task_id": error_task_id,
                "task_data": {
                    "train": task_data.get("train", []) if 'task_data' in locals() else [],
                    "test": task_data.get("test", []) if 'task_data' in locals() else []
                },
                "best_of": best_of,
                "prompt_messages": [None],
                "reasoning": [error_message],
                "output_grid": [None],
                "generation_time_seconds": [None],
                "answer_correct": [False],
                "comparison_details": [{
                    "expected_output": None,
                    "actual_output": None,
                    "match": False,
                    "error": error_message
                }],
                "total_processing_time_seconds": round(time.time() - task_start_time, 2)
            })
            g_generation_failed_count += 1


async def run_direct_benchmark(args):
    """Runs the direct answer ARC benchmark."""
    global g_config, g_start_time, g_model_value, g_submitted_count
    logging.info("Starting ARC Direct Answer Benchmark...")

    # 1. Load Configuration
    try:
        g_config = ARCBenchmarkConfig(
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks,
            dataset_directory=args.dataset_directory,
            max_concurrent_tasks=args.max_concurrent_tasks
        )
        logging.info(f"Configuration loaded.")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}")
        logging.info(f"Using dataset file: {g_config.absolute_dataset_file}")
        logging.info(f"Using model: {g_config.model_identifier}")
        if g_config.max_tasks is not None:
            logging.info(f"Maximum tasks to process: {g_config.max_tasks}")
        else:
             logging.info("Processing all found/specified tasks (no max_tasks limit).")
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model
    try:
        model_enum_member = ModelOption[g_config.model_identifier]
        g_model_value = model_enum_member.value

        model = get_model(g_config, role="main")
        agent = DirectAnswerAgent(model=model)
        logging.info(f"Initialized DirectAnswerAgent with model: {g_config.model_identifier} ({g_model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return

    # 3. Prepare Task List/Iterator and Semaphore
    semaphore = asyncio.Semaphore(g_config.max_concurrent_tasks)
    async_tasks = []
    g_submitted_count = 0

    # 4. Process Tasks Concurrently
    g_start_time = time.time()
    logging.info(f"Starting task processing with concurrency limit {g_config.max_concurrent_tasks}...")

    task_source = g_config.absolute_dataset_file
    logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
    try:
        task_generator = load_tasks_from_dataset(
            dataset_path=task_source,
            task_ids=g_config.task_ids,
            max_tasks=g_config.max_tasks
        )
        for i, task_item in enumerate(task_generator):
            coro = process_single_task(task_item, g_config, agent, semaphore, i, total_tasks=None, best_of=args.best_of)
            async_tasks.append(coro)
            g_submitted_count += 1

        logging.info(f"Submitted {g_submitted_count} tasks from dataset generator for processing.")
        if g_submitted_count == 0:
             logging.warning("No tasks were yielded from the dataset generator. Check filters or file content.")
             results_raw = []
        else:
             results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Error while iterating through dataset {task_source}: {e}", exc_info=True)
        return

    # 5. Wait for all tasks to complete
    for res in results_raw:
        if isinstance(res, Exception):
            logging.error(f"Task failed with exception during gather/scheduling: {res}", exc_info=res)
        elif res is not None:
             logging.warning(f"Unexpected non-None item in results_raw after gather: {type(res)} - {res}")

    # 6. Log Final Summary
    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0

    # Calculate final answer accuracy stats
    total_answers = g_answer_correct_count + g_answer_incorrect_count
    accuracy_rate = (g_answer_correct_count / total_answers * 100) if total_answers > 0 else 0

    log_summary = (
        f"Finished processing loop. Submitted: {g_submitted_count}, "
        f"Gen Success: {g_generation_successful_count}, Gen Failed: {g_generation_failed_count}. "
        f"Answers Correct: {g_answer_correct_count}, Answers Incorrect: {g_answer_incorrect_count}. "
        f"Accuracy Rate: {accuracy_rate:.2f}%. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)
    logging.info("Benchmark run loop complete. Final results will be saved on exit.")


# Modify the run_direct_benchmark function signature to accept task_range
async def run_direct_benchmark(args, task_range=None):
    """Runs the direct answer ARC benchmark."""
    global g_config, g_start_time, g_model_value, g_submitted_count
    logging.info("Starting ARC Direct Answer Benchmark...")

    # 1. Load Configuration
    try:
        g_config = ARCBenchmarkConfig(
            model_identifier=args.model_identifier,
            max_tasks=args.max_tasks, # Keep max_tasks in config for logging/metadata
            dataset_directory=args.dataset_directory,
            max_concurrent_tasks=args.max_concurrent_tasks
        )
        logging.info(f"Configuration loaded.")
        logging.info(f"Max concurrent tasks: {g_config.max_concurrent_tasks}")
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

    # 2. Initialize Agent and Model
    try:
        model_enum_member = ModelOption[g_config.model_identifier]
        g_model_value = model_enum_member.value

        model = get_model(g_config, role="main")
        agent = DirectAnswerAgent(model=model)
        logging.info(f"Initialized DirectAnswerAgent with model: {g_config.model_identifier} ({g_model_value})")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return

    # 3. Prepare Task List/Iterator and Semaphore
    semaphore = asyncio.Semaphore(g_config.max_concurrent_tasks)
    async_tasks = []
    g_submitted_count = 0

    # 4. Process Tasks Concurrently
    g_start_time = time.time()
    logging.info(f"Starting task processing with concurrency limit {g_config.max_concurrent_tasks}...")

    task_source = g_config.absolute_dataset_file
    logging.info(f"Processing tasks iteratively from dataset file: {task_source}")
    try:
        # Pass the task_range to the data loader
        task_generator = load_tasks_from_dataset(
            dataset_path=task_source,
            task_ids=g_config.task_ids, # task_ids is always None in this script currently
            max_tasks=g_config.max_tasks, # Keep max_tasks for backward compatibility if needed, though --tasks overrides
            task_range=task_range # Pass the new range
        )
        for i, task_item in enumerate(task_generator):
            # The index 'i' here is the index within the *yielded* tasks,
            # not necessarily the original index in the dataset if a range was used.
            # We might need to adjust logging or tracking if we need the original index.
            # For now, use 'i' as the sequence number of tasks being processed in this run.
            coro = process_single_task(task_item, g_config, agent, semaphore, i, total_tasks=None, best_of=args.best_of)
            async_tasks.append(coro)
            g_submitted_count += 1

        logging.info(f"Submitted {g_submitted_count} tasks from dataset generator for processing.")
        if g_submitted_count == 0:
             logging.warning("No tasks were yielded from the dataset generator. Check filters, range, or file content.")
             results_raw = []
        else:
             results_raw = await asyncio.gather(*async_tasks, return_exceptions=True)

    except Exception as e:
        logging.error(f"Error while iterating through dataset {task_source}: {e}", exc_info=True)
        return

    # 5. Wait for all tasks to complete
    for res in results_raw:
        if isinstance(res, Exception):
            logging.error(f"Task failed with exception during gather/scheduling: {res}", exc_info=res)
        elif res is not None:
             logging.warning(f"Unexpected non-None item in results_raw after gather: {type(res)} - {res}")

    # 6. Log Final Summary
    end_time = time.time()
    total_time = end_time - g_start_time if g_start_time else 0

    # Calculate final answer accuracy stats
    total_answers = g_answer_correct_count + g_answer_incorrect_count
    accuracy_rate = (g_answer_correct_count / total_answers * 100) if total_answers > 0 else 0

    log_summary = (
        f"Finished processing loop. Submitted: {g_submitted_count}, "
        f"Gen Success: {g_generation_successful_count}, Gen Failed: {g_generation_failed_count}. "
        f"Answers Correct: {g_answer_correct_count}, Answers Incorrect: {g_answer_incorrect_count}. "
        f"Accuracy Rate: {accuracy_rate:.2f}%. "
        f"Total time: {total_time:.2f} seconds."
    )
    logging.info(log_summary)
    logging.info("Benchmark run loop complete. Final results will be saved on exit.")


if __name__ == "__main__":
    # --- Register Exit Handlers FIRST ---
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(save_final_results)
    logging.info("Registered signal handler for SIGINT and atexit handler for final save.")
    # --- End Exit Handlers ---

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run Direct Answer ARC Benchmark")
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
    parser.add_argument(
        "--dataset_directory",
        type=str,
        default="../data",
        help="Path to the directory containing dataset.json"
    )
    parser.add_argument(
        "--max_concurrent_tasks",
        type=int,
        default=5,
        help="Maximum number of tasks to process concurrently (default: 5)"
    )
    parser.add_argument(
        "--best_of",
        type=int,
        default=1,
        help="Number of responses to generate for each task (default: 1)"
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
        # Pass the parsed task_range to the benchmark function
        asyncio.run(run_direct_benchmark(args, task_range=task_range))
    except KeyboardInterrupt:
        logging.info("Benchmark run interrupted by user.")
    except Exception as e:
        logging.error(f"Benchmark run failed with an unexpected error: {e}", exc_info=True)

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run Direct Answer ARC Benchmark")
    parser.add_argument(
        "--model_identifier",
        type=str,
        default=ModelOption.LOCAL_0.name,
        choices=[option.name for option in ModelOption],
        help=f"Model identifier to use (default: {ModelOption.LOCAL_0.name})"
    )
    parser.add_argument(
        "--max_tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to process (default: process all)"
    )
    parser.add_argument(
        "--dataset_directory",
        type=str,
        default="../data",
        help="Path to the directory containing dataset.json"
    )
    parser.add_argument(
        "--max_concurrent_tasks",
        type=int,
        default=5,
        help="Maximum number of tasks to process concurrently (default: 5)"
    )
    parser.add_argument(
        "--best_of",
        type=int,
        default=1,
        help="Number of responses to generate for each task (default: 1)"
    )
    # --- End Argument Parsing ---

    args = parser.parse_args()

    # Run the async function
    try:
        asyncio.run(run_direct_benchmark(args))
    except KeyboardInterrupt:
        logging.info("Benchmark run interrupted by user.")
    except Exception as e:
        logging.error(f"Benchmark run failed with an unexpected error: {e}", exc_info=True)
