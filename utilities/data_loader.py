import os
import json
import logging
from typing import List, Dict, Optional, Tuple, Iterator

# Configure basic logging
# Use logging level from run_benchmark to avoid conflicts if imported
logger = logging.getLogger(__name__) # Use a specific logger for this module

# Removed get_task_files and load_task as only dataset.json loading is supported now.

def load_tasks_from_dataset(dataset_path: str, task_ids: Optional[List[str]] = None, max_tasks: Optional[int] = None) -> Iterator[Tuple[str, Dict]]:
    """
    Loads tasks iteratively from a dataset.json file (expected to be a list of task objects,
    where each object is a dictionary containing a 'task_id' key and task data).

    Args:
        dataset_path: The absolute path to the dataset.json file.
        task_ids: An optional list of specific task IDs to include.
        max_tasks: An optional limit on the number of tasks to yield.

    Yields:
        Tuples of (task_id, task_data).
    """
    try:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            # Expecting List[Dict], where each Dict has 'task_id' and task data
            dataset: List[Dict] = json.load(f)
        logger.info(f"Loaded dataset.json containing {len(dataset)} task entries.")

        if not isinstance(dataset, list):
            logger.error(f"Dataset file {dataset_path} is not a JSON list as expected.")
            return # Stop iteration

        processed_count = 0
        task_id_set = set(task_ids) if task_ids else None

        for task_item in dataset:
            # 1. Basic validation of task_item structure
            if not isinstance(task_item, dict):
                logger.warning(f"Skipping non-dictionary item in dataset list: {type(task_item)}")
                continue

            # 2. Extract task_id (assuming a key like 'task_id')
            task_id = task_item.get("task_id") # Use .get() for safety
            if not task_id:
                logger.warning(f"Skipping task item missing 'task_id' key: {task_item}")
                continue

            # 3. Filter by task_ids if provided
            if task_id_set and task_id not in task_id_set:
                continue

            # 4. Treat the task_item itself as the task_data for validation
            task_data = task_item
            if 'train' not in task_data or 'test' not in task_data:
                logger.warning(f"Task '{task_id}' in dataset is missing 'train' or 'test' keys. Skipping.")
                continue

            # 5. Yield the valid task
            yield task_id, task_data
            processed_count += 1

            # 6. Check max_tasks limit after yielding
            if max_tasks is not None and processed_count >= max_tasks:
                logger.info(f"Reached max_tasks limit ({max_tasks}). Stopping iteration.")
                break # Stop yielding more tasks

        # --- Logging after iteration ---
        if task_ids and processed_count < len(task_ids):
             logger.warning(f"Found and yielded {processed_count} matching tasks, but {len(task_ids)} were requested. Some requested task IDs might not be in the dataset or were invalid.")
        elif processed_count == 0 and not task_ids:
             logger.warning(f"No tasks yielded from the dataset file: {dataset_path}. It might be empty, contain only invalid tasks, or lack 'task_id' keys.")
        elif processed_count == 0 and task_ids:
             logger.warning(f"No tasks yielded. None of the requested task IDs {task_ids} were found or valid in the dataset.")
        else:
            logger.info(f"Finished iterating dataset. Yielded {processed_count} tasks.")


    except FileNotFoundError:
        logger.error(f"Dataset file not found: {dataset_path}")
        # No return needed, generator just won't yield anything
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from dataset file: {dataset_path}")
        # No return needed
    except Exception as e:
        logger.error(f"Unexpected error loading dataset file {dataset_path}: {e}", exc_info=True)
        # No return needed

# Example usage (demonstrating the remaining function):
if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Define a dummy dataset path (replace with actual path if needed)
    # Assumes this script is run from the benchmark directory
    dummy_dataset_path = os.path.abspath("../data/dataset.json")
    print(f"Attempting to load from: {dummy_dataset_path}")

    # Create a dummy dataset file for testing if it doesn't exist
    if not os.path.exists(dummy_dataset_path):
        print("Creating dummy dataset.json for testing...")
        os.makedirs(os.path.dirname(dummy_dataset_path), exist_ok=True)
        dummy_data = [
            {"task_id": "task001", "train": [{"input": [[1]], "output": [[2]]}], "test": [{"input": [[3]], "output": [[4]]}]},
            {"task_id": "task002", "train": [{"input": [[5]], "output": [[6]]}], "test": [{"input": [[7]], "output": [[8]]}]},
            {"task_id": "invalid_task", "test": []}, # Missing 'train'
            {"task_id": "task003", "train": [{"input": [[9]], "output": [[0]]}], "test": [{"input": [[1]], "output": [[2]]}]},
        ]
        with open(dummy_dataset_path, 'w') as f:
            json.dump(dummy_data, f)

    print("\n--- Loading ALL tasks from dataset.json (limit 2) ---")
    loaded_count = 0
    for task_id, task_data in load_tasks_from_dataset(dummy_dataset_path, max_tasks=2):
        print(f"  Loaded task: {task_id} (Train examples: {len(task_data.get('train', []))})")
        loaded_count += 1
    print(f"Total loaded: {loaded_count}")

    print("\n--- Loading SPECIFIC tasks from dataset.json ---")
    loaded_count = 0
    specific_ids = ["task001", "task003", "nonexistent"]
    for task_id, task_data in load_tasks_from_dataset(dummy_dataset_path, task_ids=specific_ids):
        print(f"  Loaded task: {task_id} (Train examples: {len(task_data.get('train', []))})")
        loaded_count += 1
    print(f"Total loaded: {loaded_count}")

    # Clean up dummy file if created
    # if os.path.exists(dummy_dataset_path) and "dummy_data" in locals():
    #     print("\nCleaning up dummy dataset.json...")
    #     os.remove(dummy_dataset_path)
