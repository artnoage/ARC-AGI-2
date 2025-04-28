import os
import json
import logging
import time
import asyncio # Import asyncio
from config import ARCBenchmarkConfig
from data_loader import get_task_files, load_task
from simple_agent import SimpleAgent
# Import get_model
from model_utils import get_model

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Removed DummyModel

async def run_benchmark(): # Make function async
    """Runs the ARC reasoning benchmark."""
    logging.info("Starting ARC Reasoning Benchmark...")

    # 1. Load Configuration
    try:
        config = ARCBenchmarkConfig()
        logging.info(f"Configuration loaded. Output directory: {config.output_directory}")
        logging.info(f"Task directory: {config.absolute_task_directory}")
        if config.max_tasks:
            logging.info(f"Maximum tasks to process: {config.max_tasks}")
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        return

    # 2. Initialize Agent and Model
    try:
        # Use get_model to initialize the actual model
        model = get_model(config, role="main")
        agent = SimpleAgent(model=model)
        logging.info(f"Initialized SimpleAgent with model: {config.model_identifier}")
    except ValueError as e:
        logging.error(f"Model initialization failed: {e}")
        logging.error("Ensure OPENROUTER_API_KEY is set in .env for non-local models, or a local server is running for LOCAL models.")
        return
    except Exception as e:
        logging.error(f"Unexpected error during model initialization: {e}")
        return


    # 3. Get Task Files
    task_files = get_task_files(
        task_directory=config.absolute_task_directory,
        task_ids=config.task_ids,
        max_tasks=config.max_tasks
    )

    if not task_files:
        logging.warning("No task files found or specified. Exiting.")
        return

    logging.info(f"Found {len(task_files)} tasks to process.")

    # 4. Process Tasks
    results = []
    start_time = time.time()
    for i, file_path in enumerate(task_files):
        task_id, task_data = load_task(file_path)
        if task_data is None:
            logging.warning(f"Skipping task from file: {os.path.basename(file_path)}")
            continue

        logging.info(f"Processing task {i+1}/{len(task_files)}: {task_id}")

        try:
            # --- Agent Processing ---
            # Use the async get_reasoning method
            prompt_content, reasoning = await agent.get_reasoning(task_data)
            # --- ---

            # Store results, including task data
            result_entry = {
                "task_id": task_id,
                "task_data": { # Include the original task data
                    "train": task_data.get("train", []),
                    "test": task_data.get("test", [])
                },
                "prompt_user_content": prompt_content, # The user part of the prompt sent
                "reasoning": None # Placeholder
            }

            if reasoning is not None:
                result_entry["reasoning"] = reasoning
                logging.info(f"Finished task {task_id}.")
            else:
                # Error handled within get_reasoning, just log skip
                logging.warning(f"Skipping result for task {task_id} due to processing error.")
                result_entry["reasoning"] = "ERROR: Failed to get reasoning."

            results.append(result_entry)

        except Exception as e:
            # Catch broader errors during the await or result handling
            logging.error(f"Unexpected error processing task {task_id}: {e}")
            # Append error entry, still including task_id and data if available
            results.append({
                "task_id": task_id,
                 "task_data": {
                    "train": task_data.get("train", []) if task_data else "Error loading task data",
                    "test": task_data.get("test", []) if task_data else "Error loading task data"
                },
                "prompt_user_content": None, # Prompt might not have been generated
                "reasoning": f"ERROR: Exception during task processing loop: {e}"
            })

    end_time = time.time()
    total_time = end_time - start_time
    logging.info(f"Finished processing {len(results)} tasks in {total_time:.2f} seconds.")

    # 5. Save Results
    results_filename = f"benchmark_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    results_path = os.path.join(config.output_directory, results_filename)
    try:
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        logging.info(f"Benchmark results saved to: {results_path}")
    except Exception as e:
        logging.error(f"Failed to save results: {e}")

    logging.info("Benchmark run complete.")

if __name__ == "__main__":
    # Run the async function using asyncio.run()
    try:
        asyncio.run(run_benchmark())
    except KeyboardInterrupt:
        logging.info("Benchmark run interrupted by user.")
    except Exception as e:
        logging.error(f"Benchmark failed with an unexpected error: {e}", exc_info=True)
