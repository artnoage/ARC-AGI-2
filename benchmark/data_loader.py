import os
import json
import logging
from typing import List, Dict, Optional, Tuple

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_task_files(task_directory: str, task_ids: Optional[List[str]] = None, max_tasks: Optional[int] = None) -> List[str]:
    """
    Lists JSON task files in the specified directory.

    Args:
        task_directory: The absolute path to the directory containing task files.
        task_ids: An optional list of specific task IDs (filenames without .json) to include.
        max_tasks: An optional limit on the number of task files to return.

    Returns:
        A list of absolute paths to the task JSON files.
    """
    if not os.path.isdir(task_directory):
        logging.error(f"Task directory not found: {task_directory}")
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
        logging.info(f"Found {len(filtered_files)} total tasks in directory.")

    # Apply max_tasks limit if specified
    if max_tasks is not None and len(filtered_files) > max_tasks:
        filtered_files = filtered_files[:max_tasks]
        logging.info(f"Limiting to {max_tasks} tasks.")

    # Return absolute paths
    absolute_paths = [os.path.join(task_directory, f) for f in filtered_files]
    return absolute_paths

def load_task(file_path: str) -> Optional[Tuple[str, Dict]]:
    """
    Loads a single ARC task JSON file.

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
             logging.warning(f"Task file {file_path} is missing 'train' or 'test' key. Skipping.")
             return None
        return task_id, task_data
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from file: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error loading task file {file_path}: {e}")
        return None

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
