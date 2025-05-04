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
    Runner[run_benchmark.py (Async w/ Semaphore)]
    Loader[data_loader.py]
    Agent[simple_agent.py (Async)]
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

    Config -- Defines Parameters --> Runner
    Runner -- Uses --> Loader
    Runner -- Uses --> Agent
    Runner -- Uses --> ModelUtil
    Loader -- Reads --> ARC_Files
    Loader -- Reads --> ARC_Dataset
    Agent -- Uses --> ModelUtil
    ModelUtil -- Interacts with --> Model
    Agent -- Processes Data from --> Loader
    Runner -- Saves --> Results
    AuxUtil -- Reads --> Results
    AuxUtil -- Reads/Writes --> Traces
```
*   A Python-based command-line application orchestrates the benchmarking process, configurable via `config.py` and command-line arguments.
*   Components handle configuration, data loading (from individual files or a single `dataset.json`), agent logic, model interaction, and result saving (including metadata and full prompts).
*   **Concurrency:** `run_benchmark.py` uses `asyncio.Semaphore` to control the number of concurrent tasks processed, based on `config.max_concurrent_tasks`.
*   Auxiliary utilities (e.g., `auxiliary_utilities/merge_reasoning.py`) process the benchmark results and integrate them with the trace store (`data/traces_store.json`), storing reasoning in the `text` field and creating new entries for each merged reasoning trace for an existing task ID.

## Key technical decisions

*   **Phase 1:** Client-side JavaScript for UI interactions and data manipulation. JSON for data storage.
*   **Phase 2:** Python for backend/scripting logic. Asynchronous programming (`asyncio`) for efficient model interaction and **concurrency control (`asyncio.Semaphore`)**. Modular design separating concerns (config, data, model, agent, runner, auxiliary utilities). Use of `.env` for sensitive keys. Command-line argument parsing (`argparse`) for runtime configuration (including data source selection and concurrency limit). Detailed logging for debugging. `aiohttp` for async HTTP requests. Dual data loading methods implemented in `data_loader.py`.

## Design patterns in use

*   **Phase 1:** Event-driven UI.
*   **Phase 2:** Modular design. Configuration management pattern (config file + CLI overrides). Factory pattern in `model_utils.py` (`get_model`). **Concurrency limiting pattern (`asyncio.Semaphore`)** in `run_benchmark.py`.

## Component relationships

*   **Phase 1:** UI depends on ARC data format. Data storage format defined in `data/nature_of_data.md`.
*   **Phase 2:** `run_benchmark.py` orchestrates other benchmark modules, managing task execution flow and **applying concurrency limits via `asyncio.Semaphore`**. `SimpleAgent` depends on `model_utils.py` and data provided by `data_loader.py`. `data_loader.py` now offers two methods: loading individual files or loading from `dataset.json`. `run_benchmark.py` selects the loading method based on configuration (`config.py` + CLI args). `model_utils.py` abstracts model interactions. `auxiliary_utilities/merge_reasoning.py` processes output from `run_benchmark.py` and updates `data/traces_store.json`, storing reasoning in the `text` field and creating new entries for each merged reasoning trace for an existing task ID.
