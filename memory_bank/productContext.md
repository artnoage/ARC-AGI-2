# Product Context

## Why this project exists

This project adapts the ARC-AGI framework for two primary purposes:
1.  **Synthetic Data Generation:** To facilitate the collective generation of rich synthetic data (task variations, reasoning traces) around abstract reasoning problems.
2.  **Real Benchmarking:** To develop tools for benchmarking the reasoning capabilities and performance of language models directly on ARC tasks.

## Problems it solves

*   **Synthetic Data Generation:** Addresses the need for more detailed data beyond simple input-output pairs for training and evaluating reasoning systems. Captures human problem-solving processes and explores task variations.
*   **Real Benchmarking:** Provides a standardized way to evaluate and compare how well different language models can solve ARC tasks and understand/explain the logic behind them.

## How it should work

*   **Synthetic Data Generation:** A web-based interface (`apps/testing_interface.html`) allows users to solve ARC tasks, apply transformations, and add step-by-step reasoning traces. This generated data is stored with metadata. Additionally, Python scripts (`synthetic_data_generators/`) generate synthetic reasoning and code data from models and provide verification.
*   **Real Benchmarking:** A dedicated benchmarking script within the `benchmark/` directory will handle loading ARC tasks, prompting models for solutions, executing generated code (if applicable), and evaluating the results. This script will be configurable and save detailed output for analysis. The saving mechanism has been made robust to ensure all results are captured even during concurrent execution.

## User experience goals

*   **Synthetic Data Generation Interface:** An intuitive interface for task interaction, transformation, and reasoning annotation. Clear feedback mechanisms (like the distance metric).
*   **Synthetic Data Generation Scripts:** Easy configuration and execution of data generation and verification processes. Detailed logging for troubleshooting. Clear, structured output for analysis, with a robust saving mechanism that correctly handles concurrent task execution.
*   **Real Benchmarking:** Easy configuration and execution of benchmarks. Clear, structured output for analysis of model performance, with a robust saving mechanism that correctly handles concurrent task execution.
