# Project Brief: ARC-AGI-2 Adaptation

This project involves adapting the original ARC-AGI dataset and interface for advanced AGI research, focusing initially on synthetic data generation and subsequently on model reasoning benchmarking.

## Core Requirements & Goals

**Phase 1: Synthetic Data Generation Interface**
*   Adapt the ARC-AGI interface (`apps/testing_interface.html`) for collective synthetic data creation.
*   Implement features for task transformations (e.g., rotation, reflection).
*   Implement features for adding and managing step-by-step reasoning traces for task solutions.
*   Introduce a distance metric to guide users during task solving.
*   Define a data structure (`data/nature_of_data.md`) to store tasks, variations, traces, and contributions.

**Phase 2: Benchmarking Agent Reasoning**
*   Create a benchmarking suite (`benchmark/`) to evaluate language model reasoning on ARC tasks.
*   Develop a `SimpleAgent` to present ARC 'train' examples to a model.
*   Prompt the model to explain its reasoning for the input-output transformations.
*   Save the model's reasoning output for analysis (`data/evaluation/`).
*   Make the benchmark configurable (`benchmark/config.py`) for different models (local/API) and parameters.

## Scope

*   **Phase 1:** Development of the modified testing interface, transformation/reasoning trace features, and data storage mechanisms.
*   **Phase 2:** Implementation of the benchmarking agent, model interaction utilities, configuration, execution script, and result saving.
*   Creation and maintenance of Memory Bank documentation throughout both phases.

## Stakeholders

*   User (requestor)
*   Cline (AI Assistant)

## Timeline & Milestones (Optional)

*   **Phase 1:** Complete development of the synthetic data generation interface and features.
*   **Phase 2:** Complete implementation and testing of the benchmarking suite.
