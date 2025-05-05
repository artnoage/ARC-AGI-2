import json
import logging
import re
# Import the retry decorator and response getter
from utilities.model_utils import get_model_response

class DirectAnswerAgent:
    def __init__(self, model):
        """
        Initializes the DirectAnswerAgent.

        Args:
            model: An initialized model object (e.g., from get_model)
                   that has an async `ainvoke` method.
        """
        self.model = model
        logging.debug(f"DirectAnswerAgent initialized with model type: {type(model).__name__}")
        self.system_prompt = """
You are an expert at solving visual IQ test puzzles (ARC - Abstraction and Reasoning Corpus). You will be presented with a series of input-output grid pairs demonstrating a hidden pattern or transformation rule.

Your task is to:
1. Analyze the examples and understand the underlying logic, pattern, or transformation rule.
2. Apply this rule to a new input grid and provide the correct output grid.

**Output Format:**
Provide your reasoning first, followed by the output grid enclosed in a JSON format like this:

```json
[
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8]
]
```

**Color Mapping:**
The grids use numbers 0-9 to represent colors. If you refer to colors in your reasoning, please use this mapping:
0: black, 1: blue, 2: red, 3: green, 4: yellow, 5: grey, 6: fuschia, 7: orange, 8: teal, 9: brown
"""

    async def get_reasoning_and_answer(self, task_data: dict) -> tuple[list | None, str | None, list | None]:
        """
        Processes a single ARC task's training examples and gets reasoning and direct answer from the model.

        Args:
            task_data (dict): A dictionary containing the 'train' data and 'test' data for a task.

        Returns:
            A tuple containing:
            - The full list of message dictionaries sent to the model (or None if error).
            - The reasoning string extracted from the model's response (or None if error/not found).
            - The output grid as a list of lists of integers (or None if error/not found).
        """
        logging.debug(f"DirectAnswerAgent.get_reasoning_and_answer called with task data: {json.dumps(task_data)[:200]}...")

        if 'train' not in task_data or not task_data['train']:
            logging.warning("Task data does not contain valid 'train' examples.")
            return None, None, None

        if 'test' not in task_data or not task_data['test'] or not task_data['test'][0].get('input'):
            logging.warning("Task data does not contain valid 'test' input.")
            return None, None, None

        train_examples = task_data['train']
        test_input = task_data['test'][0]['input']
        logging.debug(f"Found {len(train_examples)} training examples and test input")

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

        user_content += "Now, apply the pattern to this new input grid:\n\n"
        try:
            user_content += f"Input: {json.dumps(test_input)}\n\n"
        except TypeError as e:
            logging.error(f"JSON serialization error for test input: {e}")
            user_content += f"Input: [Error: {e}]\n\n"

        user_content += "Based on these examples, provide your reasoning and the output grid as requested."
        messages.append({"role": "user", "content": user_content})
        logging.debug(f"Added user content (length: {len(user_content)})")

        # Log message structure preview
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content_preview = msg.get("content", "")[:50] + "..." if msg.get("content") else "None"
            logging.debug(f"Message {i+1} - Role: {role}, Content preview: {content_preview}")

        try:
            logging.info(f"Sending request to model ({type(self.model).__name__}) for reasoning and answer")
            full_response = await get_model_response(self.model, messages)

            if not full_response:
                logging.warning("Received empty response from model")
                return messages, None, None

            logging.info(f"Received model response (length: {len(full_response)})")
            logging.debug(f"Full response preview: {full_response[:200]}...")

            # --- Parse the response ---
            reasoning = None
            output_grid = None

            # Try to extract JSON grid
            grid_match = re.search(r"```json\n(.*?)```", full_response, re.DOTALL)
            if grid_match:
                grid_json = grid_match.group(1).strip()
                try:
                    output_grid = json.loads(grid_json)
                    logging.debug(f"Extracted output grid: {output_grid}")
                    # Assume reasoning is everything before the grid
                    reasoning = full_response[:grid_match.start()].strip()
                    logging.debug(f"Extracted reasoning (length: {len(reasoning)}): {reasoning[:100]}...")
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON grid: {e}")
                    reasoning = full_response
            else:
                # Try to find any JSON-like structure in the response
                json_pattern = r"\[\s*\[.*?\]\s*\]"
                grid_match = re.search(json_pattern, full_response, re.DOTALL)
                if grid_match:
                    grid_json = grid_match.group(0).strip()
                    try:
                        output_grid = json.loads(grid_json)
                        logging.debug(f"Extracted output grid from plain text: {output_grid}")
                        # Assume reasoning is everything before the grid
                        reasoning = full_response[:grid_match.start()].strip()
                        logging.debug(f"Extracted reasoning (length: {len(reasoning)}): {reasoning[:100]}...")
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse JSON-like grid: {e}")
                        reasoning = full_response
                else:
                    # If no grid found, assume the whole response is reasoning (or an error message)
                    logging.warning("Could not find output grid in response. Assuming entire response is reasoning.")
                    reasoning = full_response.strip()

            return messages, reasoning, output_grid

        except Exception as e:
            logging.error(f"Error getting model response or parsing: {e}", exc_info=True)
            # Return messages even on error for logging
            return messages, f"Error: {e}", None
