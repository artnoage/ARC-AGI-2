from dataclasses import dataclass, field
import os
from enum import Enum

class ModelOption(Enum):
    """Enum class representing different model options."""
    # Add model options based on old_project/model_utils.py or user needs
    CLAUDE = "anthropic/claude-3.7-sonnet"
    GEMINI_PRO = "google/gemini-2.5-pro-preview-03-25"
    GEMINI_FLASH="google/gemini-2.5-flash-preview"
    LOCAL_0= "/Home/stat/laschos/math/AIMO2_initial/models/7BSR2" # Example path, adjust as needed
    LOCAL_1= "/Home/stat/laschos/math/AIMO2_initial/models/14BR1" # Example path, adjust as needed
    LOCAL_2= "/Home/stat/laschos/math/AIMO2_initial/models/14BR2" # Example path, adjust as needed
    # Add other models from the old config if needed
    CODER="qwen/qwen-2.5-coder-32b-instruct"
    QWEN="qwen/qwen3-235b-a22b"


@dataclass
class ARCBenchmarkConfig:
    """Configuration for the ARC reasoning benchmark."""

    # --- Model Settings ---
    # Use ModelOption enum names, e.g., "CLAUDE", "LOCAL_0"
    model_identifier: str = ModelOption.LOCAL_0.name # Default to LOCAL_0
    main_temp: float = 0.1 # Temperature for the main model (Default: 0.0 for deterministic output)
    main_port: int = 8000 # Port if using a local model for the 'main' role
    main_template: int = 1 # Template type (1 or 2) for local models
    max_tokens: int = 40000 # Maximum number of tokens to generate (Default: None for no limit)

    # --- Dataset Settings ---
    # Path to the directory containing ARC task JSON files
    task_directory: str = "../data/training" # Relative path from benchmark/ to data/training/
    # Optional: List specific task IDs (filenames without .json) to run. If None, runs all.
    task_ids: list[str] = None
    # Optional: Limit the number of tasks to process. If None, runs all specified (or found).
    max_tasks: int = None

    # --- Output Settings ---
    # Directory to save benchmark results
    output_directory: str = "benchmark_results"

    # --- Internal ---
    # Field to store the absolute path to the task directory after initialization
    _task_dir_absolute: str = field(init=False, repr=False)

    def __post_init__(self):
        """Validate paths and create output directory."""
        # Resolve the task directory path relative to this config file's location
        config_dir = os.path.dirname(os.path.abspath(__file__))
        self._task_dir_absolute = os.path.abspath(os.path.join(config_dir, self.task_directory))

        if not os.path.isdir(self._task_dir_absolute):
            raise ValueError(f"Task directory not found: {self._task_dir_absolute}")

        # Resolve and create the output directory relative to the config file's location
        self.output_directory = os.path.abspath(os.path.join(config_dir, self.output_directory))
        os.makedirs(self.output_directory, exist_ok=True)

    @property
    def absolute_task_directory(self) -> str:
        """Returns the validated absolute path to the task directory."""
        return self._task_dir_absolute

# Example usage:
# if __name__ == "__main__":
#     config = ARCBenchmarkConfig(max_tasks=10)
#     print(f"Using model: {config.model_identifier}")
#     print(f"Task Directory (Absolute): {config.absolute_task_directory}")
#     print(f"Output Directory: {config.output_directory}")
#     if config.task_ids:
#         print(f"Specific Task IDs: {config.task_ids}")
#     if config.max_tasks:
#         print(f"Max Tasks: {config.max_tasks}")
