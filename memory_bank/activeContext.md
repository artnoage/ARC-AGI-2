# Active Context

## Current work focus

The project is currently focused on two main areas: **Phase 2: Synthetic Data Generation & Verification** and **Phase 3: Real Benchmarking**.

The refactoring of the synthetic data generation structure (formerly the `benchmark/` directory) to `synthetic_data_generators/` is complete. This included renaming directories and scripts, updating internal paths and output locations, and updating documentation.

A new `benchmark/` directory has been created for **Phase 3: Real Benchmarking**. This directory will contain scripts for directly benchmarking language model performance on ARC tasks.

## Recent changes

*   **Enhanced Benchmark and Synthetic Data Generation:**
    *   **Standardized JSON Structure:**
        *   Modified all scripts to use a single file for storing results
        *   Each script now appends new entries to a single JSONL file
        *   Metadata is added to the same file at the end of each run
        *   Future runs will continue to append to this file, preserving all previous results
    *   **Added Best-of Flag to Benchmark Script:**
        *   New `--best_of` command-line argument to specify the number of responses to generate
        *   All responses are stored as lists, even when best_of is 1, ensuring consistent data structure
        *   Provides the foundation for generating multiple answers with different parameters
    *   **Updated Merge Reasoning Script:**
        *   Modified `auxiliary_utilities/merge_reasoning.py` to handle both list-based and string-based reasoning formats
        *   Added support for JSONL files (detecting by file extension)
        *   Restructured the code for better readability and maintainability
*   **Completed Refactoring of Synthetic Data Generation Structure:**
    *   Renamed the main `benchmark/` directory to `synthetic_data_generators/`.
    *   Renamed the results subdirectory `benchmark/benchmark_results/` to `synthetic_data_generators/synthetic_data/`.
    *   Renamed data generation scripts:
        *   `generate_reasoning_benchmark_data.py` -> `generate_reasoning_data.py`
        *   `generate_code_benchmark_data.py` -> `generate_code_data.py`
    *   Updated the default `output_directory` in `utilities/config.py` to `../synthetic_data` (relative to `utilities/`).
    *   Updated log file paths in both data generation scripts to save within `synthetic_data_generators/synthetic_data/`.
    *   Updated output paths in both data generation scripts to save results into subdirectories (`reasoning_data/` and `code_data/`) within `synthetic_data_generators/synthetic_data/` using the new naming convention (e.g., `reasoning_data_results_*.json`).
    *   Updated help text in `synthetic_data_generators/verify_generated_code.py` to reflect the new results path structure.
    *   Updated import paths across all affected scripts (`synthetic_data_generators/*`, `agents/*`, `utilities/*`, `auxiliary_utilities/*`).
    *   Updated documentation (`readme.md`, `memory_bank/techContext.md`, `memory_bank/systemPatterns.md`, `memory_bank/activeContext.md`) to reflect the new structure, names, and paths.
*   **Created New Benchmark Directory:**
    *   A new `benchmark/` directory has been created for real benchmarking efforts (Phase 3).
    *   This directory currently contains a single file (`benchmark/run_code_benchmark.py`) that handles both generating model responses and evaluating them.
*   **Previous Work (Pre-Refactor):**
    *   Established core components for data generation (agents, utilities, scripts).
    *   Implemented features like concurrency, periodic saving, graceful exit, dataset.json loading, CLI arguments, enhanced logging, and refined JSON output.
    *   Successfully ran reasoning and code data generation scripts.
    *   Merged reasoning results into `data/traces_store.json`.
    *   Created and refined the code verification script.

## Next steps

*   **Phase 2 (Synthetic Data Generation & Verification):**
    *   **Run Code Verification Script:** Execute `synthetic_data_generators/verify_generated_code.py` on the results from the code generation run (e.g., `synthetic_data_generators/synthetic_data/code_data/code_data_results_20250504_165606.json`) to assess the correctness of the generated code. **(Next immediate step for Phase 2)**.
    *   **Analyze Verification Results:** Review the output and logs (`synthetic_data_generators/synthetic_data/code_verification.log`) from the verification script.
    *   **Analyze Reasoning Data:** Review the merged reasoning data in `data/traces_store.json` (from the reasoning data generation run).
    *   **Analyze Code Generation Results (Qualitative):** Review the raw output JSON (`synthetic_data_generators/synthetic_data/code_data/code_data_results_20250504_165606.json`) for qualitative insights into reasoning and code structure, especially for tasks that failed verification.
    *   **Update `.gitignore`:** Add `synthetic_data_generators/synthetic_data/` to `.gitignore`.
    *   **Consider Further Data Generation:** Decide if additional data generation runs are needed.
    *   **Refine Agents/Prompting:** Based on verification results and qualitative analysis, consider refinements.
*   **Phase 3 (Real Benchmarking):**
    *   Run the benchmarking script `benchmark/run_code_benchmark.py` to evaluate model performance on ARC tasks.
    *   Test the best-of flag to generate multiple responses for each task.
    *   Analyze the benchmark results, which include information about whether the generated code was successful.
    *   Consider refinements to the benchmarking process based on initial results.

## Active decisions and considerations

*   Model selection and parameters are centralized in `utilities/config.py`.
*   Error handling for model API calls and file I/O is implemented.
*   The data generation currently focuses on generating reasoning/code for 'train' examples only.
*   **Data Loading:**
    *   The data generation scripts (`generate_reasoning_data.py`, `generate_code_data.py`) load tasks *iteratively* from `data/dataset.json` by default.
    *   The generated results files embed the necessary `task_data` (including test cases) within each result entry.
    *   The real benchmarking script (`benchmark/run_code_benchmark.py`) also loads tasks iteratively from `data/dataset.json`.
*   **Code Verification (Phase 2):**
    *   The `verify_generated_code.py` script reads a code data results file (e.g., `synthetic_data_generators/synthetic_data/code_data/code_data_results_*.json`) and uses the `task_data` embedded within it for verification. It no longer requires a separate `dataset.json` input.
*   Configuration is now handled via a combination of `utilities/config.py` defaults and command-line argument overrides.
*   JSON output includes detailed metadata and the full prompt structure.
*   **Concurrency control:** `asyncio.Semaphore` is used in both data generation scripts to limit the number of tasks processed simultaneously, controlled by `max_concurrent_tasks` in the configuration (defaulting to 5, overrideable via CLI). The real benchmarking script (`benchmark/run_code_benchmark.py`) also uses `asyncio.Semaphore` for concurrency control.
*   **Result Saving:**
    *   **Synthetic Data Generation Scripts:**
        *   Results are accumulated in a global list (`g_results`).
        *   **Partial results:** New results are appended periodically (every `SAVE_INTERVAL` successful tasks) to fixed files (`synthetic_data_generators/synthetic_data/reasoning_data/reasoning_data_partial_results.jsonl` or `synthetic_data_generators/synthetic_data/code_data/code_data_partial_results.jsonl`) in JSON Lines format. Global counters (`g_last_saved_results_len`) prevent duplicate entries.
        *   **Final results:** All accumulated results (`g_results`) are saved upon normal exit (`atexit`) or interruption (`SIGINT`) to timestamped `.json` files (with distinct prefixes/paths: `synthetic_data_generators/synthetic_data/reasoning_data/reasoning_data_results_*.json` or `synthetic_data_generators/synthetic_data/code_data/code_data_results_*.json`, and `_interrupted` suffix if applicable), containing metadata and the full list of results.
        *   A simple file lock (`g_is_saving`) prevents concurrent save attempts during both periodic and final saves.
    *   **Real Benchmarking Script:**
        *   Uses a similar approach to the synthetic data generation scripts.
        *   Results are accumulated in a global list (`g_results`).
        *   **Partial results:** New results are appended periodically to `benchmark/benchmark_results/code_benchmark/code_benchmark_partial_results.jsonl`.
        *   **Final results:** All accumulated results are saved to a single JSONL file in `benchmark/benchmark_results/code_benchmark/code_benchmark_results.jsonl`.
        *   Includes detailed metadata about the benchmark run, including verification statistics.
*   **Data Structure Consistency:**
    *   All responses (prompt_messages, reasoning, python_code, etc.) are now stored as lists, even when best_of is 1.
    *   This ensures consistent data structure across all scripts and makes it easier to process the results programmatically.
    *   The `merge_reasoning.py` script has been updated to handle both list-based and string-based reasoning formats for backward compatibility.
*   **Agent Prompting:**
    *   The `ReasoningTraceGenerator` agent uses a system prompt that includes guidance on the number-to-color mapping.
    *   The `ReasoningCodeGenerator` agent uses a different prompt structure designed to elicit both reasoning and Python code.
    *   The real benchmarking script (`benchmark/run_code_benchmark.py`) uses the `CodeGeneratingAgent` to generate both reasoning and Python code, and then verifies the code against the task's test cases.
