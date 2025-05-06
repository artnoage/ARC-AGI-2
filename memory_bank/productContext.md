# Product Context

## Why this project exists

The ARC-AGI-2 project exists to advance AGI research through three interconnected components:

1. **Synthetic Data Creation**: Providing interfaces for humans to create, analyze, and annotate ARC tasks with reasoning traces and solutions
2. **Synthetic Data Generation**: Automating the creation of reasoning traces and code solutions using language models
3. **LLM Benchmarking**: Evaluating language model performance on ARC tasks to measure reasoning capabilities

## Problems it solves

* **Data Scarcity**: Creates a larger corpus of annotated ARC tasks with reasoning traces and solutions
* **Collaborative Analysis**: Enables researchers to collectively analyze and solve ARC tasks
* **Model Evaluation**: Provides standardized benchmarking for assessing LLM reasoning capabilities
* **AI-Assisted Research**: Facilitates human-AI collaboration in solving complex reasoning tasks

## How it should work

* **Synthetic Data Creation**: Users interact with web interfaces to:
  * Analyze and transform ARC tasks
  * Add reasoning traces explaining solution steps
  * Discuss tasks with AI assistants
  * Test Python code solutions directly in the browser

* **Synthetic Data Generation**: Automated scripts:
  * Generate reasoning traces for ARC tasks using language models
  * Create Python code solutions for tasks
  * Verify generated code against test cases
  * Store results in structured JSON format

* **LLM Benchmarking**: Evaluation scripts:
  * Test language models on ARC tasks
  * Evaluate both code-based solutions and direct grid answers
  * Track success/failure metrics
  * Generate detailed performance reports

## User experience goals

* **Synthetic Data Creation Interfaces**:
  * Intuitive task interaction, transformation, and reasoning annotation
  * Clear feedback mechanisms (like distance metrics)
  * AI-assisted task analysis with preserved code formatting
  * Visual representation of input/output grids
  * Integrated Python code execution environment
  * User control over AI parameters (temperature, model selection)
  * Persistent chat history for ongoing task analysis

* **Synthetic Data Generation Scripts**:
  * Easy configuration and execution
  * Detailed logging for troubleshooting
  * Structured output for analysis
  * Robust handling of concurrent task execution
  * Task filtering capabilities via command-line arguments

* **LLM Benchmarking**:
  * Simple configuration and execution
  * Clear performance metrics and analysis
  * Support for multiple evaluation approaches
  * Robust saving of results during concurrent execution
  * Task filtering capabilities via command-line arguments
