# Project Brief: ARC-AGI-2 Adaptation

This project adapts the original ARC-AGI dataset and interface for advanced AGI research, focusing on three core areas:

## Core Requirements & Goals

**Synthetic Data Creation**
* Adapt the ARC-AGI interface (`apps/testing_interface.html`) for collective synthetic data creation
* Implement features for task transformations (rotation, reflection)
* Add step-by-step reasoning traces for task solutions
* Introduce distance metrics to guide users during task solving
* Define data structure (`data/nature_of_data.md`) to store tasks, variations, traces, and contributions
* Create a discussion interface (`apps/discuss_interface.html`) for AI-assisted task analysis with:
  * Improved layout for better visibility of examples and chat
  * Automatic population of input grid with first test input
  * Code block formatting to preserve indentation in AI messages
  * Visual representation for input/output grids
  * Side-by-side display of matrix and visual output
  * Execution control buttons for testing solutions
* Integrate the discussion interface with language model API (OpenRouter)
* Implement Python code execution environment within the discussion interface

**Synthetic Data Generation & Verification**
* Develop tools (`synthetic_data_generators/`) for generating synthetic data from language models:
  * Reasoning traces generation
  * Code solutions generation
* Implement verification mechanisms for generated code
* Add functionality to filter tasks by specific task IDs

**LLM Benchmarking**
* Create benchmarking suite (`benchmark/`) to evaluate language model performance on ARC tasks
* Support both code-based and direct answer evaluation approaches
* Track success/failure with detailed metrics
* Support filtering tasks by specific task IDs

## Scope

* Development of interfaces for synthetic data creation and AI-assisted analysis
* Implementation of synthetic data generation tools and verification
* Implementation of benchmarking suite for LLM evaluation
* Creation and maintenance of Memory Bank documentation

## Stakeholders

* User (requestor)
* Cline (AI Assistant)
