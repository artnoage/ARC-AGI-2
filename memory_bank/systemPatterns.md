# System Patterns

## System architecture

The project encompasses two distinct architectural phases:

**Phase 1: Synthetic Data Generation Interface**

```mermaid
graph TD
    subgraph Browser
        UI[Testing Interface HTML/JS]
    end
    subgraph Server/Data
        ARC[ARC Dataset Files]
        DS[Data Storage (JSON w/ Metadata)]
    end

    UI -- Loads/Displays --> ARC
    UI -- Saves Transformations/Traces --> DS
    ARC -- Provides Base Tasks --> UI
```
*   A client-side web application (`apps/testing_interface.html`) allows users to interact with ARC tasks.
*   User actions (solving, transforming, adding traces) generate new data stored alongside original tasks, often as enriched JSON files.

**Phase 2: Benchmarking Agent Reasoning**

```mermaid
graph LR
    subgraph Benchmark Suite (Python)
        Config[config.py]
        ReasoningRunner[generate_reasoning_traces.py (Async w/ Semaphore, Saving, Exit Handling)]
        CodeRunner[run_code_generation_benchmark.py (Async w/ Semaphore, Saving, Exit Handling)]
        Loader[data_loader.py]
        SimpleAgent[simple_agent.py (Async)]
        CodeAgent[code_generating_agent.py (Async)]
        ModelUtil[model_utils.py]
    end
    subgraph External
        ARC_Files[ARC Dataset Files (Individual)]
        ARC_Dataset[ARC Dataset (dataset.json)]
        Model[Language Model (Local/API)]
        Results[Benchmark Results (JSON)]
        Traces[Trace Store (JSON)]
        AuxUtil[Auxiliary Utilities (Python)]
    end

    Config -- Defines Parameters --> ReasoningRunner
    Config -- Defines Parameters --> CodeRunner
    ReasoningRunner -- Uses --> Loader
    ReasoningRunner -- Uses --> SimpleAgent
    ReasoningRunner -- Uses --> ModelUtil
    CodeRunner -- Uses --> Loader
    CodeRunner -- Uses --> CodeAgent
    CodeRunner -- Uses --> ModelUtil
    Loader -- Reads --> ARC_Files
    Loader -- Reads --> ARC_Dataset
    SimpleAgent -- Uses --> ModelUtil
    CodeAgent -- Uses --> ModelUtil
    ModelUtil -- Interacts with --> Model
    SimpleAgent -- Processes Data from --> Loader
    CodeAgent -- Processes Data from --> Loader
    ReasoningRunner -- Saves --> Results(Reasoning)
    CodeRunner -- Saves --> Results(Code+Reasoning)
    AuxUtil -- Reads --> Results(Reasoning)
    AuxUtil -- Reads/Writes --> Traces
```
*   Two Python-based command-line applications orchestrate the benchmarking processes, configurable via `config.py` and command-line arguments:
    *   `generate_reasoning_traces.py`: Focuses solely on generating reasoning traces using `SimpleAgent`.
    *   `run_code_generation_benchmark.py`: Generates both reasoning and Python code using `CodeGeneratingAgent`.
*   Shared components handle configuration (`config.py`), data loading (`data_loader.py` - supporting individual files or `dataset.json`), and model interaction (`model_utils.py`).
*   Distinct agent logic exists in `simple_agent.py` and `code_generating_agent.py`.
*   Both runner scripts implement result saving (including metadata and full prompts) with distinct output filenames.
*   **Concurrency:** Both runner scripts (`generate_reasoning_traces.py`, `run_code_generation_benchmark.py`) use `asyncio.Semaphore` to control the number of concurrent tasks processed, based on `config.max_concurrent_tasks`.
*   **Saving & Exit:** Both runner scripts implement periodic saving of partial results (appending to `.jsonl` files) and graceful saving of all results on normal exit (`atexit`) or interruption (`SIGINT`) to timestamped `.json` files. Global state variables manage results and saving status within each script.
*   Auxiliary utilities (e.g., `auxiliary_utilities/merge_reasoning.py`) process the reasoning benchmark results (`generate_reasoning_traces.py` output) and integrate them with the trace store (`data/traces_store.json`), storing reasoning in the `text` field and creating new entries for each merged reasoning trace for an existing task ID. Utilities for processing code generation results may be added later.

## Key technical decisions

*   **Phase 1:** Client-side JavaScript for UI interactions and data manipulation. JSON for data storage.
*   **Phase 2:** Python for backend/scripting logic. Asynchronous programming (`asyncio`) for efficient model interaction and **concurrency control (`asyncio.Semaphore`)** in both benchmark runners. Modular design separating concerns (config, data, model, agents, runners, auxiliary utilities). Use of `.env` for sensitive keys. Command-line argument parsing (`argparse`) for runtime configuration (including data source selection and concurrency limit). Detailed logging for debugging. `aiohttp` for async HTTP requests. Dual data loading methods implemented in `data_loader.py`. **Signal handling (`signal`, `atexit`)** for graceful shutdown and result saving in both runners. Global state management within each runner script (`generate_reasoning_traces.py`, `run_code_generation_benchmark.py`) for accumulating results across async tasks.

## Design patterns in use

*   **Phase 1:** Event-driven UI.
*   **Phase 2:** Modular design. Configuration management pattern (config file + CLI overrides). Factory pattern in `model_utils.py` (`get_model`). **Concurrency limiting pattern (`asyncio.Semaphore`)** applied in both benchmark runners. **Graceful shutdown/resource cleanup pattern** using `signal` and `atexit` applied in both benchmark runners.

## Component relationships

*   **Phase 1:** UI depends on ARC data format. Data storage format defined in `data/nature_of_data.md`.
*   **Phase 2:**
    *   `generate_reasoning_traces.py` orchestrates the reasoning benchmark, using `SimpleAgent`, `data_loader.py`, and `model_utils.py`. It manages task flow, concurrency, and saving for reasoning traces.
    *   `run_code_generation_benchmark.py` orchestrates the code generation benchmark, using `CodeGeneratingAgent`, `data_loader.py`, and `model_utils.py`. It manages task flow, concurrency, and saving for reasoning + code results.
    *   Both runners depend on `config.py` for settings and select the data loading method from `data_loader.py` based on configuration.
    *   `SimpleAgent` and `CodeGeneratingAgent` implement distinct prompting strategies but both rely on `model_utils.py` for API interaction.
    *   `auxiliary_utilities/merge_reasoning.py` processes output from `generate_reasoning_traces.py` and updates `data/traces_store.json`, storing reasoning in the `text` field and creating new entries for each merged reasoning trace for an existing task ID.
