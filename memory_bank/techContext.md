# Tech Context

## Technologies used

*   **Core:**
    *   ARC Dataset (JSON format): The fundamental data source.
*   **Phase 1 (Synthetic Data Generation Interface):**
    *   HTML, CSS, JavaScript: For the client-side testing interface (`apps/testing_interface.html`).
    *   JSON: For storing task data, transformations, and reasoning traces.
*   **Phase 2 (Synthetic Data Generation & Verification):**
    *   Python: Primary language for the synthetic data generation scripts and auxiliary utilities.
    *   `asyncio`: For asynchronous operations, especially model API calls.
    *   Standard Libraries: `json` (used for parsing `--task_ids` input), `os`, `argparse` (used for command-line argument parsing, including `--task_ids`), `logging`, `time` (used for timestamp generation, adjusted for concurrency), `signal`, `atexit`.
    *   External Libraries: `aiohttp` (used in `utilities/model_utils.py` for async API calls), `python-dotenv` (for loading `.env`).
    *   Language Models: Interaction with various models via local servers (e.g., Ollama) or APIs (e.g., OpenRouter).
        *   **Key Python Components:**
            *   `agents/reasoning_trace_generator.py`: Agent logic for reasoning traces.
            *   `agents/reasoning_code_generator.py`: Agent logic for reasoning and code generation.
            *   `synthetic_data_generators/generate_reasoning_data.py`: Runner script for reasoning data generation, **now supporting `--task_ids` input as a JSON string**.
            *   `synthetic_data_generators/generate_code_data.py`: Runner script for code generation data generation, **now supporting `--task_ids` input as a JSON string**.
            *   `synthetic_data_generators/verify_generated_code.py`: Script to verify generated code.
            *   `utilities/config.py`: Configuration management.
            *   `utilities/data_loader.py`: Data loading logic.
            *   `utilities/model_utils.py`: Model interaction utilities.
            *   `auxiliary_utilities/`: Folder containing helper scripts (e.g., `merge_reasoning.py`).
*   **Phase 3 (Real Benchmarking):**
    *   Python: Primary language for the benchmarking script.
    *   Will likely use `asyncio` for model interaction.
    *   Will utilize standard libraries like `json` (used for parsing `--task_ids` input), `os`, `argparse` (used for command-line argument parsing, including `--task_ids`), `logging`, `time`.
    *   Will likely use external libraries like `aiohttp` and `python-dotenv`.
    *   Language Models: Interaction with various models via local servers (e.g., Ollama) or APIs (e.g., OpenRouter).
        *   **Key Python Components:**
            *   `benchmark/run_benchmark.py`: The main benchmarking script, **now supporting `--task_ids` input as a JSON string**.
            *   Will likely utilize `utilities/config.py`, `utilities/data_loader.py`, and `utilities/model_utils.py`.

## Development setup

*   **Phase 1:** Web browser (Chrome recommended) for using the testing interface. Text editor for potential HTML/JS modifications.
*   **Phase 2 & 3:** Python environment (e.g., venv). Access to ARC dataset files (individual task files recommended). `.env` file for API keys. Access to `data/traces_store.json` for the merge utility (Phase 2). Potentially a local model server setup (e.g., Ollama).

## Technical constraints

*   ARC dataset size: Individual task files (`data/training/`, `data/evaluation/`) are preferred over the monolithic `data/dataset.json` due to memory constraints.
*   Model API rate limits and costs (if using external APIs).
*   Network latency for model API calls.
*   Requires Python environment capable of running `asyncio` and required libraries.

## Dependencies

*   **Phase 1:** None beyond a modern web browser.
*   **Phase 2 & 3:** Python 3.x, `aiohttp`, `python-dotenv`. No specific model client libraries currently needed as `utilities/model_utils.py` uses direct API calls.
