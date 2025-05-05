from dataclasses import dataclass, field
import os
from enum import Enum
from typing import Optional

class ModelOption(Enum):
    """Enum class representing different model options."""
    # Add model options based on old_project/model_utils.py or user needs
    CLAUDE = "anthropic/claude-3.7-sonnet"
    GEMINI_PRO = "google/gemini-2.5-pro-preview-03-25"
    GEMINI_FLASH="google/gemini-2.5-flash-preview"
    GPT="openai/gpt-4o-mini"
    LOCAL_0= "/Home/stat/laschos/math/AIMO2_initial/models/7BSR2" # Example path, adjust as needed
    LOCAL_1= "/Home/stat/laschos/math/AIMO2_initial/models/14BR1" # Example path, adjust as needed
    LOCAL_2= "/Home/stat/laschos/math/AIMO2_initial/models/14BR2" # Example path, adjust as needed
    # Add other models from the old config if needed
    CODER="qwen/qwen-2.5-coder-32b-instruct"
    PHI="microsoft/phi-4-reasoning-plus"    
    QWEN="qwen/qwen3-235b-a22b"


@dataclass
class ARCBenchmarkConfig:
    """Configuration for the ARC reasoning benchmark."""

    # --- Model Settings ---
    # Use ModelOption enum names, e.g., "CLAUDE", "LOCAL_0"
    model_identifier: str = ModelOption.LOCAL_0.name # Default to LOCAL_0
    main_temp: float = 0.7 # Temperature for the main model (Default: 0.0 for deterministic output)
    main_port: int = 8000 # Port if using a local model for the 'main' role
    main_template: int = 1 # Template type (1 or 2) for local models
    max_tokens: int = None # Maximum number of tokens to generate (Default: None for no limit)

    # --- Dataset Settings ---
    # Path to the *directory containing* the dataset.json file
    dataset_directory: str = "../data" # Relative path from benchmark/ to the directory holding dataset.json
    # Optional: List specific task IDs (keys in dataset.json) to run. If None, runs all.
    task_ids: list[str] = None
    # Optional: Limit the number of tasks to process. If None, runs all specified (or found).
    max_tasks: int = None
    # NOTE: Benchmarks now ONLY support loading from dataset.json

    # --- Concurrency Settings ---
    # Maximum number of tasks to process concurrently
    max_concurrent_tasks: int = 5 # Default concurrency limit

    # --- Output Settings ---
    # Directory to save benchmark results (relative to the utilities directory where this config is defined)
    # Defaulting to a directory named 'synthetic_data' one level up from 'utilities/'
    output_directory: str = "../synthetic_data" # Changed default

    # --- Internal ---
    # Field to store the absolute path to the dataset.json file after initialization
    _dataset_file_absolute: str = field(init=False, repr=False)

    def __post_init__(self):
        """Validate paths and create output directory."""
        config_dir = os.path.dirname(os.path.abspath(__file__))

        # Resolve and validate dataset file path
        # dataset_directory now always points to the directory containing dataset.json
        parent_dir = os.path.abspath(os.path.join(config_dir, self.dataset_directory))
        self._dataset_file_absolute = os.path.join(parent_dir, "dataset.json")
        if not os.path.isfile(self._dataset_file_absolute):
            raise ValueError(f"Dataset file not found: {self._dataset_file_absolute}")

        # Resolve and create the output directory relative to the config file's location
        self.output_directory = os.path.abspath(os.path.join(config_dir, self.output_directory))
        os.makedirs(self.output_directory, exist_ok=True)

    # Removed absolute_task_directory property as it's no longer needed

    @property
    def absolute_dataset_file(self) -> str:
        """Returns the validated absolute path to the dataset.json file."""
        return self._dataset_file_absolute

# Example usage:
if __name__ == "__main__":
    # Example: Load from dataset.json (now the only option)
    config_dataset = ARCBenchmarkConfig(dataset_directory="../data", max_tasks=5)
    print("\n--- Loading from dataset.json ---")
    print(f"Using model: {config_dataset.model_identifier}")
    print(f"Dataset File (Absolute): {config_dataset.absolute_dataset_file}")
    print(f"Output Directory: {config_dataset.output_directory}")
    if config_dataset.task_ids:
        print(f"Specific Task IDs: {config_dataset.task_ids}")
    if config_dataset.max_tasks:
        print(f"Max Tasks: {config_dataset.max_tasks}")
