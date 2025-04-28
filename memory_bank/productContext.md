# Product Context

## Why this project exists

This project adapts the ARC-AGI framework for two primary purposes:
1.  **Phase 1:** To facilitate the collective generation of rich synthetic data (task variations, reasoning traces) around abstract reasoning problems.
2.  **Phase 2:** To develop tools for benchmarking the reasoning capabilities of language models on ARC tasks.

## Problems it solves

*   **Phase 1:** Addresses the need for more detailed data beyond simple input-output pairs for training and evaluating reasoning systems. Captures human problem-solving processes and explores task variations.
*   **Phase 2:** Provides a standardized way to evaluate and compare how well different language models can understand and explain the logic behind ARC tasks.

## How it should work

*   **Phase 1:** A web-based interface (`apps/testing_interface.html`) allows users to solve ARC tasks, apply transformations, and add step-by-step reasoning traces. This generated data is stored with metadata.
*   **Phase 2:** A benchmarking script (`benchmark/run_benchmark.py`) uses a `SimpleAgent` to feed ARC task training examples to a configured language model. The model is prompted to explain its reasoning, and this output is saved for evaluation.

## User experience goals

*   **Phase 1:** An intuitive interface for task interaction, transformation, and reasoning annotation. Clear feedback mechanisms (like the distance metric).
*   **Phase 2:** Easy configuration and execution of benchmarks. Clear, structured output of model reasoning for analysis.
