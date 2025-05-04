# Tech Context

## Technologies used

*   **Core:**
    *   ARC Dataset (JSON format): The fundamental data source.
*   **Phase 1 (Synthetic Data Generation Interface):**
    *   HTML, CSS, JavaScript: For the client-side testing interface (`apps/testing_interface.html`).
    *   JSON: For storing task data, transformations, and reasoning traces.
*   **Phase 2 (Benchmarking Agent Reasoning & Utilities):**
    *   Python: Primary language for the benchmarking suite and auxiliary utilities.
    *   `asyncio`: For asynchronous operations in the benchmark, especially model API calls.
    *   Standard Libraries: `json`, `os`, `argparse`, `logging`, `time`, `signal`, `atexit`.
    *   External Libraries: `aiohttp` (used in `model_utils.py` for async API calls), `python-dotenv` (for loading `.env`).
    *   Language Models: Interaction with various models via local servers (e.g., Ollama) or APIs (e.g., OpenRouter).

## Development setup

*   **Phase 1:** Web browser (Chrome recommended) for using the testing interface. Text editor for potential HTML/JS modifications.
*   **Phase 2:** Python environment (e.g., venv). Access to ARC dataset files (individual task files recommended). `.env` file for API keys. Access to `data/traces_store.json` for the merge utility. Potentially a local model server setup (e.g., Ollama).

## Technical constraints

*   ARC dataset size: Individual task files (`data/training/`, `data/evaluation/`) are preferred over the monolithic `data/dataset.json` due to memory constraints.
*   Model API rate limits and costs (if using external APIs).
*   Network latency for model API calls.
*   Requires Python environment capable of running `asyncio` and required libraries.

## Dependencies

*   **Phase 1:** None beyond a modern web browser.
*   **Phase 2:** Python 3.x, `aiohttp`, `python-dotenv`. No specific model client libraries currently needed as `model_utils.py` uses direct API calls.
