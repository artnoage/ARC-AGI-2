import json
import argparse
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def merge_reasoning_into_traces(benchmark_results_path: str, traces_path: str):
    """
    Merges reasoning from a benchmark results JSON into a traces JSON file.

    Args:
        benchmark_results_path: Path to the benchmark results JSON file.
        traces_path: Path to the traces JSON file (e.g., data/traces_store.json).
    """
    logging.info(f"Loading benchmark results from: {benchmark_results_path}")
    try:
        with open(benchmark_results_path, 'r', encoding='utf-8') as f:
            benchmark_data = json.load(f)
    except FileNotFoundError:
        logging.error(f"Benchmark results file not found: {benchmark_results_path}")
        return
    except json.JSONDecodeError:
        logging.error(f"Error decoding benchmark results JSON: {benchmark_results_path}")
        return
    except Exception as e:
        logging.error(f"An error occurred while reading benchmark results: {e}")
        return

    # Extract metadata and results
    metadata = benchmark_data.get("metadata", {})
    results = benchmark_data.get("results", [])
    model_username = metadata.get("model_username", "unknown_model")

    if not results:
        logging.warning("No results found in the benchmark file. Nothing to merge.")
        return

    logging.info(f"Loading traces from: {traces_path}")
    try:
        # Load existing traces
        if os.path.exists(traces_path):
            with open(traces_path, 'r', encoding='utf-8') as f:
                traces_data = json.load(f)
            logging.info(f"Loaded {len(traces_data)} existing trace entries.")
        else:
            traces_data = {}
            logging.warning(f"Traces file not found: {traces_path}. Starting with an empty traces dictionary.")

    except json.JSONDecodeError:
        logging.error(f"Error decoding traces JSON: {traces_path}. Starting with an empty traces dictionary to avoid data corruption.")
        traces_data = {}
    except Exception as e:
        logging.error(f"An error occurred while reading traces: {e}. Starting with an empty traces dictionary to avoid data corruption.")
        traces_data = {}


    logging.info(f"Merging reasoning for model: {model_username}")
    merged_count = 0
    for result_entry in results:
        task_id = result_entry.get("task_id")
        reasoning = result_entry.get("reasoning")

        if not task_id or not reasoning or reasoning.startswith("ERROR:"):
            logging.debug(f"Skipping task_id {task_id}: Missing ID, reasoning, or contains error.")
            continue

        # Check if the task_id exists in traces_data
        if task_id in traces_data:
            # If task_id exists, create a new trace entry for this reasoning
            logging.info(f"Task_id: {task_id} found. Creating a new trace entry for new reasoning.")
            import uuid
            import time

            new_trace_id = f"{task_id}_{model_username}_{uuid.uuid4().hex[:8]}"
            new_trace_entry = {
                "trace_id": new_trace_id,
                "task_id": task_id,
                "username": model_username,
                "text": reasoning, # Store reasoning directly in text
                "score": 0,
                "timestamp": time.time(),
                "voters": {}
            }
            traces_data[task_id].append(new_trace_entry)
            logging.info(f"Created new trace entry for task_id: {task_id} with trace_id: {new_trace_id}")
            merged_count += 1
        else:
            # Create a new entry for this task_id if it doesn't exist
            logging.info(f"No trace entry found for task_id: {task_id}. Creating a new entry.")
            import uuid
            import time

            new_trace_id = f"{task_id}_{model_username}_{uuid.uuid4().hex[:8]}"
            new_trace_entry = {
                "trace_id": new_trace_id,
                "task_id": task_id,
                "username": model_username,
                "text": reasoning, # Store reasoning directly in text
                "score": 0,
                "timestamp": time.time(),
                "voters": {}
            }

            # Add the new trace entry to traces_data
            traces_data[task_id] = [new_trace_entry]
            logging.info(f"Created new trace entry for task_id: {task_id} with trace_id: {new_trace_id}")
            merged_count += 1

    logging.info(f"Finished merging. Merged reasoning for {merged_count} tasks.")

    logging.info(f"Saving updated traces to: {traces_path}")
    try:
        with open(traces_path, 'w', encoding='utf-8') as f:
            json.dump(traces_data, f, indent=2)
        logging.info("Traces file updated successfully.")
    except Exception as e:
        logging.error(f"Failed to save updated traces: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge benchmark reasoning into traces file.")
    parser.add_argument(
        "benchmark_results_path",
        type=str,
        help="Path to the benchmark results JSON file."
    )
    parser.add_argument(
        "--traces_path",
        type=str,
        default="data/traces_store.json", # Default path to the traces file
        help="Path to the traces JSON file (default: data/traces_store.json)."
    )

    args = parser.parse_args()

    merge_reasoning_into_traces(args.benchmark_results_path, args.traces_path)
