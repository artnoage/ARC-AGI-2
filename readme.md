# ARC-AGI-2: Synthetic Data Generation Interface

This repository is a modified version of the original [Abstraction and Reasoning Corpus (ARC-AGI-2)](https://github.com/fchollet/arc-agi), adapted to focus on the **collective creation of synthetic data** for advancing Artificial General Intelligence research.

*"ARC can be seen as a general artificial intelligence benchmark, as a program synthesis benchmark, or as a psychometric intelligence test. It is targeted at both humans and artificially intelligent systems that aim at emulating a human-like form of general fluid intelligence."*

A foundational description of the original dataset, its goals, and its underlying logic, can be found in: [On the Measure of Intelligence](https://arxiv.org/abs/1911.01547) and the [ARC-AGI-2 Presentation](https://docs.google.com/presentation/d/1hQrGh5YI6MK3PalQYSQs4CQERrYBQZue8PBLjjHIMgI/edit?usp=sharing).

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
