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
        Runner[run_benchmark.py]
        Loader[data_loader.py]
        Agent[simple_agent.py]
        ModelUtil[model_utils.py]
    end
    subgraph External
        ARC[ARC Dataset Files]
        Model[Language Model (Local/API)]
        Results[Benchmark Results (JSON)]
        Traces[Trace Store (JSON)]
        AuxUtil[Auxiliary Utilities (Python)]
    end

    Config -- Defines Parameters --> Runner
    Runner -- Uses --> Loader
    Runner -- Uses --> Agent
    Runner -- Uses --> ModelUtil
    Loader -- Reads --> ARC
    Agent -- Uses --> ModelUtil
    ModelUtil -- Interacts with --> Model
    Agent -- Processes Data from --> Loader
    Runner -- Saves --> Results
    AuxUtil -- Reads --> Results
    AuxUtil -- Reads/Writes --> Traces
```
*   A Python-based command-line application orchestrates the benchmarking process, configurable via `config.py` and command-line arguments.
*   Components handle configuration, data loading, agent logic, model interaction, and result saving (including metadata and full prompts).
*   Auxiliary utilities (e.g., `auxiliary_utilities/merge_reasoning.py`) process the benchmark results and integrate them with the trace store (`data/traces_store.json`), storing reasoning in the `text` field and creating new entries for each merged reasoning trace for an existing task ID.

## Key technical decisions

*   **Phase 1:** Client-side JavaScript for UI interactions and data manipulation. JSON for data storage.
*   **Phase 2:** Python for backend/scripting logic. Asynchronous programming (`asyncio`) for efficient model interaction. Modular design separating concerns (config, data, model, agent, runner, auxiliary utilities). Use of `.env` for sensitive keys. Command-line argument parsing (`argparse`) for runtime configuration. Detailed logging for debugging. `aiohttp` for async HTTP requests.

## Design patterns in use

*   **Phase 1:** Event-driven UI.
*   **Phase 2:** Modular design. Configuration management pattern (config file + CLI overrides). Factory pattern in `model_utils.py` (`get_model`).

## Component relationships

*   **Phase 1:** UI depends on ARC data format. Data storage format defined in `data/nature_of_data.md`.
*   **Phase 2:** `run_benchmark.py` orchestrates other benchmark modules. `SimpleAgent` depends on `model_utils.py` and data from `data_loader.py`. `model_utils.py` abstracts model interactions. Configuration (`config.py` + CLI args) drives behavior. `auxiliary_utilities/merge_reasoning.py` processes output from `run_benchmark.py` and updates `data/traces_store.json`, storing reasoning in the `text` field and creating new entries for each merged reasoning trace for an existing task ID.
