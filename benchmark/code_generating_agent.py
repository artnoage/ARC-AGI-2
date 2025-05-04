import json
import logging
import re
# Import the retry decorator and response getter
from model_utils import get_model_response

class CodeGeneratingAgent:
    def __init__(self, model):
        """
        Initializes the CodeGeneratingAgent.

        Args:
            model: An initialized model object (e.g., from get_model)
                   that has an async `ainvoke` method.
        """
        self.model = model
        logging.debug(f"CodeGeneratingAgent initialized with model type: {type(model).__name__}")
        self.system_prompt = """
You are an expert programmer participating in a visual IQ test (ARC - Abstraction and Reasoning Corpus). You will be presented with a series of input-output grid pairs demonstrating a hidden pattern or transformation rule.

Your task is twofold:
1.  **Explain the Reasoning:** Analyze the examples and clearly explain the underlying logic, pattern, or transformation rule used to generate the output grid from the input grid.
2.  **Provide Python Code:** Write a Python function named `solve` that takes a single argument `input_grid` (represented as a list of lists of integers) and returns the corresponding `output_grid` (as a list of lists of integers) based on the identified pattern. The function should be self-contained and rely only on standard Python libraries.

**Output Format:**
Provide your reasoning first, followed by the Python code enclosed in a markdown code block like this:

```python
# Your Python code starts here
import numpy as np # Example import, use only if necessary

def solve(input_grid):
    # Your implementation here
    output_grid = input_grid # Placeholder
    return output_grid
```

**Color Mapping:**
The grids use numbers 0-9 to represent colors. If you refer to colors in your reasoning, please use this mapping:
0: black, 1: blue, 2: red, 3: green, 4: yellow, 5: grey, 6: fuschia, 7: orange, 8: teal, 9: brown
"""

    async def get_reasoning_and_code(self, task_data: dict) -> tuple[list | None, str | None, str | None]:
        """
        Processes a single ARC task's training examples and gets reasoning and Python code from the model.

        Args:
            task_data (dict): A dictionary containing the 'train' data for a task.

        Returns:
            A tuple containing:
            - The full list of message dictionaries sent to the model (or None if error).
            - The reasoning string extracted from the model's response (or None if error/not found).
            - The Python code string extracted from the model's response (or None if error/not found).
        """
        logging.debug(f"CodeGeneratingAgent.get_reasoning_and_code called with task data: {json.dumps(task_data)[:200]}...")

        if 'train' not in task_data or not task_data['train']:
            logging.warning("Task data does not contain valid 'train' examples.")
            return None, None, None

        train_examples = task_data['train']
        logging.debug(f"Found {len(train_examples)} training examples")

        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        logging.debug(f"Added system prompt: {self.system_prompt[:50]}...")

        user_content = "Here are the training examples:\n\n"
        for i, example in enumerate(train_examples):
            user_content += f"Example {i+1}:\n"
            input_grid = example.get('input', '[[Error: Missing input]]')
            output_grid = example.get('output', '[[Error: Missing output]]')
            try:
                user_content += f"Input: {json.dumps(input_grid)}\n"
                user_content += f"Output: {json.dumps(output_grid)}\n\n"
            except TypeError as e:
                 logging.error(f"JSON serialization error for example {i+1}: {e}")
                 user_content += f"Input: [Error: {e}]\n"
                 user_content += f"Output: [Error: {e}]\n\n"

        user_content += "Based on these examples, provide the reasoning and the Python `solve` function as requested."
        messages.append({"role": "user", "content": user_content})
        logging.debug(f"Added user content (length: {len(user_content)})")

        # Log message structure preview
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content_preview = msg.get("content", "")[:50] + "..." if msg.get("content") else "None"
            logging.debug(f"Message {i+1} - Role: {role}, Content preview: {content_preview}")

        try:
            logging.info(f"Sending request to model ({type(self.model).__name__}) for reasoning and code")
            full_response = await get_model_response(self.model, messages)

            if not full_response:
                logging.warning("Received empty response from model")
                return messages, None, None

            logging.info(f"Received model response (length: {len(full_response)})")
            logging.debug(f"Full response preview: {full_response[:200]}...")

            # --- Parse the response ---
            reasoning = None
            python_code = None

            # Try to extract Python code block
            code_match = re.search(r"```python\n(.*?)```", full_response, re.DOTALL)
            if code_match:
                python_code = code_match.group(1).strip()
                logging.debug(f"Extracted Python code (length: {len(python_code)}): {python_code[:100]}...")
                # Assume reasoning is everything before the code block
                reasoning = full_response[:code_match.start()].strip()
                logging.debug(f"Extracted reasoning (length: {len(reasoning)}): {reasoning[:100]}...")
            else:
                # If no code block found, assume the whole response is reasoning (or an error message)
                logging.warning("Could not find Python code block in response. Assuming entire response is reasoning.")
                reasoning = full_response.strip()

            return messages, reasoning, python_code

        except Exception as e:
            logging.error(f"Error getting model response or parsing: {e}", exc_info=True)
            # Return messages even on error for logging
            return messages, f"Error: {e}", None


# Example Async Usage (requires an async environment to run)
# import asyncio
# from config import ARCBenchmarkConfig
# from model_utils import get_model

# async def main():
#     # --- Dummy Task Data ---
#     dummy_task_data = {
#         "train": [
#             {"input": [[1,1],[1,0]], "output": [[2,2],[2,0]]},
#             {"input": [[0,3],[3,0]], "output": [[0,6],[6,0]]}
#         ],
#         "test": [
#             {"input": [[1,0],[0,1]], "output": [[2,0],[0,2]]}
#         ]
#     }
#     # --- ---

#     # --- Initialize Model (Example using GEMINI_FLASH) ---
#     try:
#         # Ensure .env file has OPENROUTER_API_KEY or necessary keys for the model
#         config = ARCBenchmarkConfig(model_identifier="GEMINI_FLASH")
#         model = get_model(config, role="main")
#     except Exception as e:
#         print(f"Failed to initialize model: {e}")
#         return
#     # --- ---

#     agent = CodeGeneratingAgent(model)
#     print("Getting reasoning and code...")
#     messages_sent, reasoning_str, code_str = await agent.get_reasoning_and_code(dummy_task_data)

#     print("\n--- Messages Sent (Preview) ---")
#     if messages_sent:
#         for msg in messages_sent:
#             print(f"Role: {msg.get('role')}, Content: {msg.get('content', '')[:100]}...")
#     else:
#         print("No messages were prepared.")

#     print("\n--- Model Reasoning ---")
#     print(reasoning_str if reasoning_str else "No reasoning received.")

#     print("\n--- Model Python Code ---")
#     print(code_str if code_str else "No code received.")

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO) # Basic logging for example
#     # Requires Python 3.7+
#     # Ensure .env has necessary API keys (e.g., OPENROUTER_API_KEY)
#     try:
#         asyncio.run(main())
#     except Exception as e:
#         print(f"An error occurred: {e}")
