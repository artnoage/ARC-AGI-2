# Nature of the ARC Dataset JSON Files

This document describes the structure and content of the JSON files used in the Abstract Reasoning Corpus (ARC) dataset, typically found in directories like `data/training/` and `data/evaluation/`.

## File Structure

Each JSON file (e.g., `009d5c81.json`) represents a single ARC task. The root of the JSON is an object containing two main keys:

1.  **`train`**: An array (list) of demonstration examples for the task.
2.  **`test`**: An array (list) of test problems to be solved based on the pattern learned from the `train` examples.

```json
{
  "train": [ ... ],
  "test": [ ... ]
}
```

## Task Instance Structure

Both the `train` and `test` arrays contain one or more *task instances*. Each task instance is an object with two keys:

1.  **`input`**: A 2D array (list of lists) representing the input grid for the task instance.
2.  **`output`**: A 2D array (list of lists) representing the corresponding output grid for the task instance.

```json
{
  "input": [
    [0, 0, 0, ...],
    [0, 8, 8, ...],
    ...
  ],
  "output": [
    [0, 0, 0, ...],
    [0, 2, 2, ...],
    ...
  ]
}
```

### Grid Representation

-   The `input` and `output` grids are represented as lists of lists, where each inner list is a row in the grid.
-   The values within the grid are integers, typically ranging from 0 to 9. These integers represent different "colors" or states in the visual reasoning puzzle. `0` usually represents the background color.
-   The dimensions (height and width) of the input and output grids can vary between task instances and even between the input and output of a single instance.

## Purpose and Analogy

The dataset is designed for evaluating abstract reasoning capabilities. Each JSON file presents a unique reasoning challenge:

-   The `train` array provides 3-4 examples demonstrating a specific abstract pattern or transformation rule. The goal is to infer this rule.
-   The `test` array provides one or more input grids. The objective is to apply the inferred rule to these test inputs to generate the correct output grids.

This format is analogous to visual IQ tests where one must identify a pattern from examples and apply it to a new case.

## Merging and Metadata (`auxilary_utilities/merge_json.py`)

The script `auxilary_utilities/merge_json.py` is used to combine multiple individual task JSON files (like the ones in `data/evaluation/` or `data/training/`) into a single unified JSON file (e.g., `data/dataset.json`).

During this merging process, the script ensures each task entry has the following metadata fields:

1.  **`id`**: A string representing a unique identifier for the task. If not present in the source file, it attempts to use the filename (without extension).
2.  **`version`**: An integer representing the version of the task entry. If not present, it defaults to `0`. This allows multiple entries with the same `id` but different versions.
3.  **`signed_by`**: A list of strings indicating the creator(s) or source(s) of this specific task version. If not present, it defaults to a list containing a default signer (e.g., `["gkamradt"]`). If the source file provides a string, it's converted into a single-element list.

### Duplicate Handling

The script handles entries with the same `id` and `version` intelligently:
- It keeps track of entries based on their `(id, version)` tuple.
- If an incoming entry has the same `id` and `version` as an already processed entry, it compares their `train` and `test` content.
- **If the content is identical**: The script merges the `signed_by` lists, adding any unique signers from the incoming entry to the existing entry's list.
- **If the content differs**: A warning is logged, and the script keeps the *first* entry it encountered for that specific `id` and `version`.

Example structure after merging (conceptual, showing one task object within the merged list):

```json
[
  {
    "train": [ ... ],
    "test": [ ... ],
    "id": "009d5c81",
    "version": 0,
    "signed_by": ["gkamradt", "another_user"] // Example with merged signers
  },
  {
    "train": [ ... ], // Potentially different content
    "test": [ ... ],
    "id": "009d5c81",
    "version": 1,
    "signed_by": ["new_contributor"]
  },
  ... // Other task objects
]
```

This structure allows tracking different versions of tasks and attributing contributions via the `signed_by` list, while consolidating identical versions signed by different people.
