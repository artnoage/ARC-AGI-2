# ARC-AGI-2: Synthetic Data Generation Interface

This repository is a modified version of the original [Abstraction and Reasoning Corpus (ARC-AGI-2)](https://github.com/fchollet/arc-agi), adapted to focus on the **collective creation of synthetic data** for advancing Artificial General Intelligence research.

*"ARC can be seen as a general artificial intelligence benchmark, as a program synthesis benchmark, or as a psychometric intelligence test. It is targeted at both humans and artificially intelligent systems that aim at emulating a human-like form of general fluid intelligence."*

A foundational description of the original dataset, its goals, and its underlying logic, can be found in: [On the Measure of Intelligence](https://arxiv.org/abs/1911.01547) and the [ARC-AGI-2 Presentation](https://docs.google.com/presentation/d/1hQrGh5YI6MK3PalQYSQs4CQERrYBQZue8PBLjjHIMgI/edit?usp=sharing).

## Project History: Synthetic Data Generation Interface (Phase 1)

The initial phase of this project focused on adapting the original ARC-AGI interface to facilitate the **collective creation of synthetic data**. The goal was to generate richer data capturing not just solutions, but also the reasoning process and task variations.

Key features developed during this phase include:

*   **Testing Interface (`apps/testing_interface.html`):** A web-based UI for solving ARC tasks.
*   **Task Transformations:** Tools within the interface to apply transformations (reflection, rotation, etc.) to tasks, generating variations.
*   **Reasoning Traces:** Functionality for users to add step-by-step explanations for their solutions.
*   **Distance Metric:** UI feedback indicating the closeness of an attempted solution to the target.
*   **Data Structure:** Defined in `data/nature_of_data.md`, tracking task versions and contributions.

This phase established the foundation for working with ARC tasks and exploring methods beyond simple solution finding.

## Focus: Collective Synthetic Data Generation

While leveraging the core ARC tasks, this interface introduces new features specifically designed to facilitate the generation of rich, structured synthetic data. This data aims to capture not just the solutions to reasoning problems, but also the process and variations involved.

Data generation occurs primarily in two ways:

1.  **Task Transformations:** Users can apply various transformations (e.g., reflection, rotation, swapping train/test pairs) to existing tasks. This allows exploring the logical consistency of the underlying reasoning patterns and generating task variations automatically.
2.  **Reasoning Traces:** Users can explicitly add step-by-step reasoning traces to explain how they arrive at a solution for a given task. This provides valuable meta-data about the problem-solving process itself.

A key addition to the UI is the **Distance Metric**, which provides feedback on how far the current attempt is from the target solution, offering guidance during the solving process.

## Dataset Composition

The repository retains the original ARC-AGI-2 dataset structure:

-   `data/training`: Contains 1,000 tasks for demonstrating the format and core concepts.
-   `data/evaluation`: Contains 120 public evaluation tasks.

These tasks serve as the foundation upon which new synthetic data (transformations, reasoning traces) is built. See `data/nature_of_data.md` for details on the JSON structure and metadata used, including how task versions and contributions are tracked.

## Usage of the Testing Interface

You can use the testing interface located at `apps/testing_interface.html`. Open it in a web browser (Chrome recommended). It will prompt you to select a task JSON file or load the combined `dataset.json`.

The modified interface includes tools for both solving tasks and generating synthetic data:

![New UI](UI.png)

Key sections of the interface:

-   **Task Demonstration:** Shows the input/output pairs demonstrating the task's logic.
-   **Test Input Grid:** Displays the current test input to be solved.
-   **Output Grid & Controls:** Allows users to construct the output grid using editing tools (Edit, Select, Flood fill), resize, copy from input, and reset.
    -   **Show Distance:** This checkbox toggles the display of the distance metric, indicating how close the current output attempt is to the solution.
-   **Reasoning Traces:** A dedicated section for adding, viewing, and removing step-by-step reasoning explanations for the current task. Users can upvote/downvote traces and download task data enriched with these traces.
-   **Task Transformations:** Allows applying predefined transformations (Transpose, Reflect, Swap Train/Test) to the current task, creating variations. Users can "Sign" these variations, contributing them to the dataset.

### Answer Validation

Click the "Submit!" button to check your answer for the current test input. After solving, you can move to the next test input or load a new task.

### Data Contribution

By adding reasoning traces or signing transformed task variations, users collectively contribute to building a richer, more informative dataset for AGI research.

## Benchmarking Agent Reasoning

This project now includes a benchmarking suite designed to evaluate the reasoning capabilities of language models on ARC tasks.

### Functionality

The benchmark works as follows:
1.  It loads ARC task files from a specified directory (`data/training/` by default).
2.  For each task, it uses a `SimpleAgent` to interact with a configured language model (e.g., a local model via Ollama or an external API like OpenRouter).
3.  The agent presents the 'train' examples from the task to the model.
4.  The model is prompted (using a system prompt defined in `benchmark/simple_agent.py`) to explain its reasoning process for deriving the output grids from the input grids based on the provided training examples.
5.  The generated reasoning is saved to a JSON file in the `data/evaluation/` directory (filename based on the task ID).

This allows for systematic evaluation of how well different models can understand and articulate the underlying logic of ARC tasks.

### Configuration

Model selection (local vs. OpenRouter, specific model names) and other parameters (temperature, API keys, task directory) are configured in `benchmark/config.py`. Ensure your `.env` file contains the necessary API keys (e.g., `OPENROUTER_API_KEY`) if using external models, or that your local model server is running.

### Running the Benchmark

To run the benchmark, execute the following command from the project's root directory:

```bash
python benchmark/run_benchmark.py
```
