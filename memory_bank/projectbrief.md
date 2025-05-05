# Project Brief: ARC-AGI-2 Adaptation

This project involves adapting the original ARC-AGI dataset and interface for advanced AGI research. It has two main areas of focus: synthetic data generation and real benchmarking of model performance on ARC tasks.

## Core Requirements & Goals

**Phase 1: Synthetic Data Generation Interface**
*   Adapt the ARC-AGI interface (`apps/testing_interface.html`) for collective synthetic data creation.
*   Implement features for task transformations (e.g., rotation, reflection).
*   Implement features for adding and managing step-by-step reasoning traces for task solutions.
*   Introduce a distance metric to guide users during task solving.
*   Define a data structure (`data/nature_of_data.md`) to store tasks, variations, traces, and contributions.
*   Create a separate discussion interface (`apps/discuss_interface.html`) for AI-assisted task analysis and discussion.
*   Integrate the discussion interface with a language model API (OpenRouter) for AI responses.
*   Add features to the discussion interface for controlling API parameters (e.g., temperature).
*   Implement a Python code execution environment within the discussion interface for testing code solutions.

**Phase 2: Synthetic Data Generation & Verification**
*   Develop tools (`synthetic_data_generators/`) for generating synthetic data, including reasoning traces and code solutions, from language models.
*   Implement verification mechanisms for generated code.
*   Added functionality to filter tasks by a list of specific task IDs using a command-line argument (`--task_ids`).

**Phase 3: Real Benchmarking**
*   Create a dedicated benchmarking suite (`benchmark/`) to evaluate language model performance directly on ARC tasks.
*   This suite should handle both generating model responses and evaluating their correctness.
*   Added functionality to filter tasks by a list of specific task IDs using a command-line argument (`--task_ids`).

## Scope

*   **Phase 1:** Development of the modified testing interface, transformation/reasoning trace features, and data storage mechanisms.
*   **Phase 2:** Implementation of synthetic data generation tools and verification.
*   **Phase 3:** Implementation of the real benchmarking suite.
*   Creation and maintenance of Memory Bank documentation throughout all phases.

## Stakeholders

*   User (requestor)
*   Cline (AI Assistant)

## Timeline & Milestones (Optional)

*   **Phase 1:** Complete development of the synthetic data generation interface and features.
*   **Phase 2:** Complete implementation and testing of synthetic data generation and verification tools.
*   **Phase 3:** Complete implementation and testing of the real benchmarking suite.
