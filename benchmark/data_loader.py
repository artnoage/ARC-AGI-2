import os
import json
import logging
from typing import List, Dict, Optional, Tuple, Iterator

# Configure basic logging
# Use logging level from run_benchmark to avoid conflicts if imported
logger = logging.getLogger(__name__) # Use a specific logger for this module

def get_task_files(task_directory: str, task_ids: Optional[List[str]] = None, max_tasks: Optional[int] = None) -> List[str]:
    """
    Lists JSON task files in the specified directory.

    Args:
        task_directory: The absolute path to the directory containing task files.
        task_ids: An optional list of specific task IDs (filenames without .json) to include.
        max_tasks: An optional limit on the number of task files to return.

    Returns:
        A list of absolute paths to the task JSON files, or an empty list if errors occur.
    """
    if not os.path.isdir(task_directory):
        logger.error(f"Task directory not found: {task_directory}")
        return []

    all_files = [f for f in os.listdir(task_directory) if f.endswith('.json')]

    if task_ids:
        # Filter by specific task IDs
        task_id_set = set(task_ids)
        filtered_files = [f for f in all_files if os.path.splitext(f)[0] in task_id_set]
        logging.info(f"Found {len(filtered_files)} tasks matching specified IDs.")
    else:
        # Use all found JSON files
        filtered_files = all_files
        logger.info(f"Found {len(filtered_files)} total tasks in directory.")

    # Apply max_tasks limit if specified
    if max_tasks is not None and len(filtered_files) > max_tasks:
        filtered_files = filtered_files[:max_tasks]
        logger.info(f"Limiting to {max_tasks} tasks.")

    # Return absolute paths
    absolute_paths = [os.path.join(task_directory, f) for f in filtered_files]
    return absolute_paths

def load_task(file_path: str) -> Optional[Tuple[str, Dict]]:
    """
    Loads a single ARC task JSON file from its individual file.

    Args:
        file_path: The absolute path to the task JSON file.

    Returns:
        A tuple containing the task ID (filename without extension) and the loaded task data (dict),
        or None if loading fails.
    """
    task_id = os.path.splitext(os.path.basename(file_path))[0]
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            task_data = json.load(f)
        # Basic validation
        if 'train' not in task_data or 'test' not in task_data:
             logger.warning(f"Task file {file_path} is missing 'train' or 'test' key. Skipping.")
             return None
        return task_id, task_data
    except FileNotFoundError:
        logger.error(f"Task file not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error loading task file {file_path}: {e}")
        return None

def load_tasks_from_dataset(dataset_path: str, task_ids: Optional[List[str]] = None, max_tasks: Optional[int] = None) -> Iterator[Tuple[str, Dict]]:
    """
    Loads tasks from a dataset.json file (expected to be a list of task objects,
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

# Example usage:
# if __name__ == "__main__":
#     # Assuming config.py is in the same directory
#     from config import ARCBenchmarkConfig
#     config = ARCBenchmarkConfig(max_tasks=5) # Example: limit to 5 tasks

#     task_files = get_task_files(
#         task_directory=config.absolute_task_directory,
#         task_ids=config.task_ids,
#         max_tasks=config.max_tasks
#     )

#     print(f"\nFound {len(task_files)} task files to process:")
#     for file_path in task_files:
#         print(f"- {os.path.basename(file_path)}")

#     print("\nLoading tasks:")
#     loaded_tasks = 0
#     for file_path in task_files:
#         load_result = load_task(file_path)
#         if load_result:
#             task_id, task_data = load_result
#             print(f"  Successfully loaded task: {task_id} (Train examples: {len(task_data.get('train', []))})")
#             loaded_tasks += 1
#         else:
#             print(f"  Failed to load task from: {os.path.basename(file_path)}")
#     print(f"\nSuccessfully loaded {loaded_tasks} / {len(task_files)} tasks.")
