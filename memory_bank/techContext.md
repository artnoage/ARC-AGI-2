# Tech Context

## Technologies used

**Core**
* ARC Dataset (JSON format): The fundamental data source, located at `apps/static/dataset.json`.

**Synthetic Data Creation Interfaces**
* HTML, CSS, JavaScript: For client-side interfaces
* jQuery: For DOM manipulation and AJAX calls
* localStorage API: For client-side storage of chat memory and API settings
* OpenRouter API: For AI responses in the discussion interface
* Python (Flask): For server-side code execution endpoint

**Synthetic Data Generation & Verification**
* Python: Primary language for scripts and utilities
* asyncio: For asynchronous operations and concurrency control
* Standard Libraries: json, os, argparse, logging, time, signal, atexit
* External Libraries: aiohttp (for async API calls), python-dotenv (for loading .env)
* Language Models: Via local servers (e.g., Ollama) or APIs (e.g., OpenRouter)

**Key Python Components**:
* `agents/reasoning_trace_generator.py`: Agent logic for reasoning traces
* `agents/reasoning_code_generator.py`: Agent logic for reasoning and code generation
* `agents/direct_answer_generator.py`: Agent logic for direct grid answers
* `synthetic_data_generators/generate_reasoning_data.py`: Script for reasoning trace generation
* `synthetic_data_generators/generate_code_data.py`: Script for code generation
* `synthetic_data_generators/verify_generated_code.py`: Script for code verification
* `benchmark/run_code_benchmark.py`: Script for code-based benchmarking
* `benchmark/run_direct_benchmark.py`: Script for direct answer benchmarking
* `utilities/config.py`: Configuration management
* `utilities/data_loader.py`: Data loading logic
* `utilities/model_utils.py`: Model interaction utilities
* `utilities/code_execution.py`: Code execution sandbox
* `auxiliary_utilities/`: Helper scripts for data processing

## Development setup

**Synthetic Data Creation Interfaces**
* Web browser (Chrome recommended)
* Text editor for HTML/JS modifications

**Synthetic Data Generation & Benchmarking**
* Python environment (e.g., venv)
* Access to the ARC dataset file (`apps/static/dataset.json`).
* .env file for API keys
* Potentially a local model server setup (e.g., Ollama)

## Technical constraints

* ARC dataset: The project uses a monolithic `apps/static/dataset.json` file. Memory constraints related to its size should be considered if it grows very large.
* Model API rate limits and costs (if using external APIs)
* Network latency for model API calls
* Requires Python environment capable of running asyncio and required libraries
* WebSocket connections when deployed under the `/arc2/` URL prefix require specific reverse proxy configuration

## Dependencies

**Synthetic Data Creation Interfaces**
* Modern web browser
* jQuery library
* OpenRouter API (for AI responses)

**Synthetic Data Generation & Benchmarking**
* Python 3.x
* aiohttp
* python-dotenv
* Access to language models (local or API)
