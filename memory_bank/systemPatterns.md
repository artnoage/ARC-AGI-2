# System Patterns

## System architecture

The project encompasses three main architectural components:

**Synthetic Data Creation Interfaces**

```mermaid
graph TD
    subgraph Browser
        TestingUI[Testing Interface HTML/JS]
        DiscussUI[Discussion Interface HTML/JS]
    end
    subgraph Server_Data
        ARC[ARC Dataset Files]
        DS[Data_Storage_JSON_w_Metadata]
        CodeExec[Code Execution Endpoint]
    end
    subgraph Utilities
        CodeExecUtil[utilities/code_execution.py]
    end

    TestingUI -- Loads/Displays --> ARC
    TestingUI -- Saves Transformations/Traces --> DS
    DiscussUI -- Loads/Displays --> ARC
    DiscussUI -- Interacts with --> CodeExec
    CodeExec -- Uses --> CodeExecUtil
    ARC -- Provides Base Tasks --> TestingUI
    ARC -- Provides Base Tasks --> DiscussUI
```

* Two client-side web applications allow users to interact with ARC tasks:
  * The testing interface (`apps/testing_interface.html`) for task solving and synthetic data creation
  * The discussion interface (`apps/discuss_interface.html`) for AI-assisted task analysis and discussion, including a Python code execution environment
* User actions in the testing interface (solving, transforming, adding traces) generate new data stored alongside original tasks
* The discussion interface interacts with a server-side endpoint (`/arc2/execute_code`) for executing Python code in a sandbox environment

**Synthetic Data Generation & Verification**

```mermaid
graph LR
    subgraph Synthetic Data Generators [Python]
        ReasoningDataGen[synthetic_data_generators/generate_reasoning_data.py]
        CodeDataGen[synthetic_data_generators/generate_code_data.py]
        CodeVerifier[synthetic_data_generators/verify_generated_code.py]
    end
    subgraph Utilities [Root Level]
        Config[utilities/config.py]
        Loader[utilities/data_loader.py]
        ModelUtil[utilities/model_utils.py]
    end
    subgraph Agents [Root Level]
        ReasoningAgent[agents/reasoning_trace_generator.py]
        CodeAgent[agents/reasoning_code_generator.py]
    end
    subgraph External
        ARC_Files[ARC Dataset Files]
        Model[Language Model - Local/API]
        ResultsReasoning[Reasoning Data Results]
        ResultsCode[Code Data Results]
        Traces[Trace Store]
        VerificationResults[Verification Results]
    end

    ReasoningDataGen -- Uses --> Config
    CodeDataGen -- Uses --> Config
    ReasoningDataGen -- Uses --> Loader
    ReasoningDataGen -- Uses --> ReasoningAgent
    ReasoningDataGen -- Uses --> ModelUtil
    CodeDataGen -- Uses --> Loader
    CodeDataGen -- Uses --> CodeAgent
    CodeDataGen -- Uses --> ModelUtil
    Loader -- Reads --> ARC_Files
    ReasoningAgent -- Uses --> ModelUtil
    CodeAgent -- Uses --> ModelUtil
    ModelUtil -- Interacts with --> Model
    ReasoningDataGen -- Saves --> ResultsReasoning
    CodeDataGen -- Saves --> ResultsCode
    CodeVerifier -- Reads --> ResultsCode
    CodeVerifier -- Produces --> VerificationResults
```

* Two Python-based command-line applications orchestrate the synthetic data generation:
  * `synthetic_data_generators/generate_reasoning_data.py`: Generates reasoning traces using `agents/reasoning_trace_generator.py`
  * `synthetic_data_generators/generate_code_data.py`: Generates both reasoning and Python code using `agents/reasoning_code_generator.py`
* A third script handles code verification:
  * `synthetic_data_generators/verify_generated_code.py`: Executes generated Python code against task test cases
* Shared utility components handle configuration, data loading, and model interaction
* Both data generation scripts implement concurrency control, periodic saving, and graceful exit handling

**LLM Benchmarking**

```mermaid
graph LR
    subgraph Benchmarking [Python]
        CodeBenchmark[benchmark/run_code_benchmark.py]
        DirectBenchmark[benchmark/run_direct_benchmark.py]
    end
    subgraph Utilities [Root Level]
        Config[utilities/config.py]
        Loader[utilities/data_loader.py]
        ModelUtil[utilities/model_utils.py]
    end
    subgraph Agents [Root Level]
        CodeAgent[agents/reasoning_code_generator.py]
        DirectAgent[agents/direct_answer_generator.py]
    end
    subgraph External
        ARC_Files[ARC Dataset Files]
        Model[Language Model - Local/API]
        BenchmarkResults[Benchmark Results]
    end

    CodeBenchmark -- Uses --> Config
    DirectBenchmark -- Uses --> Config
    CodeBenchmark -- Uses --> Loader
    DirectBenchmark -- Uses --> Loader
    CodeBenchmark -- Uses --> CodeAgent
    DirectBenchmark -- Uses --> DirectAgent
    CodeBenchmark -- Uses --> ModelUtil
    DirectBenchmark -- Uses --> ModelUtil
    Loader -- Reads --> ARC_Files
    ModelUtil -- Interacts with --> Model
    CodeBenchmark -- Saves --> BenchmarkResults
    DirectBenchmark -- Saves --> BenchmarkResults
```

* Two Python scripts handle different benchmarking approaches:
  * `benchmark/run_code_benchmark.py`: Evaluates models on generating Python code solutions
  * `benchmark/run_direct_benchmark.py`: Evaluates models on directly generating grid answers
* Both scripts handle task loading, model interaction, result evaluation, and detailed reporting

## Key technical decisions

* **Synthetic Data Creation**: Client-side JavaScript for UI interactions and data manipulation. JSON for data storage.
* **Synthetic Data Generation**: 
  * Python for backend/scripting logic
  * Asynchronous programming (`asyncio`) for efficient model interaction
  * Concurrency control (`asyncio.Semaphore`) in data generation scripts
  * Modular design separating concerns (config, data, model, agents, generators, verifiers)
  * Command-line argument parsing for runtime configuration
  * Signal handling (`signal`, `atexit`) for graceful shutdown and result saving
  * Global state management for accumulating results across async tasks
* **LLM Benchmarking**: 
  * Python for scripting logic
  * Asynchronous model interaction
  * Configurable via command-line arguments
  * Support for "best-of" approach to generate multiple solutions per task

## Design patterns in use

* **Synthetic Data Creation**: Event-driven UI
* **Synthetic Data Generation**: 
  * Modular design
  * Configuration management pattern (config file + CLI overrides)
  * Factory pattern in `utilities/model_utils.py` (`get_model`)
  * Concurrency limiting pattern (`asyncio.Semaphore`)
  * Graceful shutdown/resource cleanup pattern
* **LLM Benchmarking**: 
  * Runner pattern within benchmark scripts
  * Configuration management pattern
  * Factory pattern from utilities

## Component relationships

* **Synthetic Data Creation**: UI depends on ARC data format. Data storage format defined in `data/nature_of_data.md`.
* **Synthetic Data Generation**:
  * Data generation scripts orchestrate the process using agents, utilities, and configuration
  * Both scripts depend on `utilities/config.py` for settings and select data loading method based on configuration
  * Agents implement distinct prompting strategies but rely on `utilities/model_utils.py` for API interaction
  * Auxiliary utilities process output from data generation scripts and update storage
* **LLM Benchmarking**:
  * Benchmark scripts orchestrate the evaluation process
  * Scripts use `utilities/data_loader.py` to load tasks (supporting filtering via `--task_ids`)
  * Scripts use `utilities/model_utils.py` to interact with models
  * Scripts implement their own logic for code execution and evaluation
