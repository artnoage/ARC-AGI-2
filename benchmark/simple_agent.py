import json
import logging
# Import the retry decorator and response getter
from model_utils import get_model_response

class SimpleAgent:
    def __init__(self, model):
        """
        Initializes the SimpleAgent.

        Args:
            model: An initialized model object (e.g., from get_model)
                   that has an async `ainvoke` method.
        """
        self.model = model
        self.system_prompt = """
You are participating in a visual IQ test. You will be presented with a series of input-output grid pairs that demonstrate a hidden pattern or transformation rule. Your task is to analyze these examples, understand the underlying reasoning, and explain the logic you would use to generate the output grid from a given input grid based on the observed pattern.

Focus on explaining the reasoning process clearly and concisely.
"""

    async def get_reasoning(self, task_data: dict) -> tuple[str | None, str | None]:
        """
        Processes a single ARC task's training examples and gets reasoning from the model.

        Args:
            task_data (dict): A dictionary containing the 'train' data for a task.

        Returns:
            A tuple containing:
            - The generated prompt string (or None if error).
            - The reasoning string from the model (or None if error).
        """
        if 'train' not in task_data or not task_data['train']:
            logging.warning("Task data does not contain valid 'train' examples.")
            return None, None

        train_examples = task_data['train']

        # Prepare the prompt in a structured format suitable for model_utils
        # The model_utils classes expect a list of message dicts or LangChain objects.
        # We'll create a list with system and user messages.
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]

        user_content = "Here are the training examples:\n\n"
        for i, example in enumerate(train_examples):
            user_content += f"Example {i+1}:\n"
            # Ensure input/output are valid before dumping
            input_grid = example.get('input', '[[Error: Missing input]]')
            output_grid = example.get('output', '[[Error: Missing output]]')
            try:
                user_content += f"Input: {json.dumps(input_grid)}\n"
                user_content += f"Output: {json.dumps(output_grid)}\n\n"
            except TypeError as e:
                 logging.error(f"JSON serialization error for example {i+1}: {e}")
                 user_content += f"Input: [Error: {e}]\n"
                 user_content += f"Output: [Error: {e}]\n\n"


        user_content += "Based on these examples, explain the reasoning process to transform an input grid to an output grid."
        messages.append({"role": "user", "content": user_content})

        # Use the retry-enabled function to get the model response
        try:
            # Note: model_utils.ainvoke expects a list of messages
            # We use get_model_response which wraps the model's ainvoke with retries
            reasoning = await get_model_response(self.model, messages)
            # The prompt sent to the model might be formatted differently by model_utils,
            # so returning the structured 'messages' list might be more accurate than a single string.
            # For simplicity now, return the user_content part as the 'prompt'.
            return user_content, reasoning
        except Exception as e:
            logging.error(f"Error getting model response: {e}")
            return user_content, f"Error: {e}"


# Example Async Usage (requires an async environment to run)
# import asyncio
# from config import ARCBenchmarkConfig
# from model_utils import get_model # Assuming get_model is adapted

# async def main():
#     # --- Dummy Task Data ---
#     dummy_task_data = {
#         "train": [
#             {"input": [[1,1],[1,1]], "output": [[2,2],[2,2]]},
#             {"input": [[0,0],[0,0]], "output": [[0,0],[0,0]]}
#         ],
#         "test": [ # Test data not used by get_reasoning
#             {"input": [[1,0],[0,1]], "output": [[2,0],[0,2]]}
#         ]
#     }
#     # --- ---

#     # --- Initialize Model (Example using LOCAL_0) ---
#     try:
#         config = ARCBenchmarkConfig(model_identifier="LOCAL_0") # Specify model
#         # Make sure OPENROUTER_API_KEY is set if using non-local models
#         # Ensure local model server is running if using LOCAL_ models
#         model = get_model(config, role="main")
#     except Exception as e:
#         print(f"Failed to initialize model: {e}")
#         return
#     # --- ---

#     agent = SimpleAgent(model)
#     print("Getting reasoning...")
#     prompt_str, reasoning_str = await agent.get_reasoning(dummy_task_data)

#     if reasoning_str:
#         print("\n--- Prompt Sent (User Content) ---")
#         print(prompt_str)
#         print("\n--- Model Reasoning ---")
#         print(reasoning_str)
#     else:
#         print("Failed to get reasoning.")

# if __name__ == "__main__":
#     # Requires Python 3.7+
#     # Make sure a local model server is running at the configured port (e.g., 8000)
#     # or OPENROUTER_API_KEY is set in .env
#     try:
#         asyncio.run(main())
#     except RuntimeError as e:
#         print(f"Runtime Error (is a model server running?): {e}")
#     except Exception as e:
#         print(f"An error occurred: {e}")
