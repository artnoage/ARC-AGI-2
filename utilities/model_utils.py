import os
import asyncio
import logging # Import logging
import json # Import json module
# Removed signal import
import aiohttp
from dotenv import load_dotenv
from functools import wraps
# Removed contextmanager import
from typing import Optional, Dict, List, Callable, Tuple, TypeVar, Any
# Explicitly import required classes from config
from .config import ARCBenchmarkConfig, ModelOption # Use relative import
T = TypeVar('T')
load_dotenv()
# Removed TimeoutException

class OpenRouterChat:
    """Chat model that makes direct requests to OpenRouter API"""

    def __init__(
        self,
        model: str,
        temperature: float = 0,
        api_key: str = None
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        logging.debug(f"OpenRouterChat initialized for model: {self.model}")

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
        """Async call to OpenRouter chat completion endpoint"""
        max_tokens = kwargs.get("max_tokens", None)
        logging.debug(f"OpenRouterChat.ainvoke called for model: {self.model}")

        # Simplified: Assume prompt is always a list of message dicts
        # as provided by SimpleAgent
        if not isinstance(prompt, list):
             raise TypeError("OpenRouterChat.ainvoke expects prompt to be a list of message dictionaries.")

        # OpenRouter API expects a list of messages directly
        payload = {
            "model": self.model,
            "messages": prompt, # Pass the list directly
            "temperature": self.temperature,
            "stream" : False
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            # Log headers without sensitive info for debugging
            "Authorization": f"Bearer {'*' * (len(self.api_key) - 4) + self.api_key[-4:] if self.api_key else 'None'}",
            "Content-Type": "application/json",
            # Add other non-sensitive headers if needed
        }
        logging.debug(f"OpenRouter Request Payload: {json.dumps(payload, indent=2)}") # Log payload
        logging.debug(f"OpenRouter Request Headers: {headers}") # Log headers (API key masked)


        # Create a new session for each request
        async with aiohttp.ClientSession() as session:
            try:
                logging.debug(f"Sending POST request to {self.base_url}")
                # Use original headers with full API key for the actual request
                actual_headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=actual_headers # Use actual headers here
                ) as response:
                    response_text = await response.text() # Read response text once
                    logging.info(f"OpenRouter Response Status: {response.status}")
                    logging.debug(f"OpenRouter Raw Response Body: {response_text}") # Log raw response

                    if response.status != 200:
                         # Log the error before raising
                        logging.error(f"Error from OpenRouter API ({response.status}): {response_text}")
                        raise ValueError(f"Error from OpenRouter API ({response.status}): {response_text}")

                    try:
                        result = json.loads(response_text) # Parse the stored text
                    except json.JSONDecodeError:
                        logging.error(f"Failed to decode JSON response from OpenRouter: {response_text}")
                        raise ValueError(f"Failed to decode JSON response from OpenRouter.")

                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logging.debug(f"Extracted content: '{content[:100]}...'") # Log extracted content snippet

                    # Return simple object with .content attribute
                    return type('Response', (), {'content': content})()
            except aiohttp.ClientError as e:
                logging.error(f"Network error during OpenRouter request: {e}", exc_info=True)
                raise # Re-raise network errors
            except Exception as e:
                logging.error(f"Exception in OpenRouterChat.ainvoke: {e}", exc_info=True) # Log other exceptions
                raise



class CustomChat:
    """Chat model that makes direct API requests to local endpoints using template 1"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "default",
        temperature: float = 0,
        api_key: str = "EMPTY"
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.api_key = api_key

    def _format_prompt(self, messages):
        """Format messages using the Phi chat template format (template 1)"""
        formatted_prompt = ""

        for message in messages:
            # Handle both dict-like messages and LangChain message objects
            if hasattr(message, 'type') and hasattr(message, 'content'):
                role = message.type if hasattr(message, 'type') else "user"
                content = message.content
            elif isinstance(message, dict):
                role = message.get("role", "").lower()
                content = message.get("content", "")
            else:
                role = "user"
                content = str(message)

            # Map roles consistently
            if role in ["system", "human", "user"]:
                role_mapped = "user" # Treat system and human as user for this template
            elif role == "assistant":
                role_mapped = "assistant"
            else:
                role_mapped = role # Keep other roles as is

            # Apply template formatting
            if role_mapped == "user":
                 formatted_prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
            elif role_mapped == "assistant":
                 formatted_prompt += f"<|im_start|>assistant\n{content}<|im_end|>" # Note: No trailing newline for assistant

        # Add the assistant prefix for the model to continue from
        if not formatted_prompt.endswith("<|im_start|>assistant\n"):
             formatted_prompt += "<|im_start|>assistant\n"

        return formatted_prompt

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
        """Async call to completion endpoint with direct API request"""
        max_tokens = kwargs.get("max_tokens", None)

        try:
            # Simplified: Assume prompt is always a list of message dicts
            if not isinstance(prompt, list):
                 raise TypeError("CustomChat.ainvoke expects prompt to be a list of message dictionaries.")

            formatted_prompt = self._format_prompt(prompt) # Pass the list directly

            # Create completion parameters
            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "temperature": self.temperature,
                "stop": ["<|im_end|>"] # Add stop token
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            # Make direct API request using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/completions",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Error from API: {error_text}")

                    result = await response.json()

                    # Create a response object with the same interface
                    return type('Response', (), {
                        'content': result.get("choices", [{}])[0].get("text", "")
                    })()
        except Exception as e:
            print(f"Exception in CustomChat.ainvoke: {str(e)}")
            raise

class CustomChat2:
    """Chat model that makes direct API requests to local endpoints using template 2"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "default",
        temperature: float = 0,
        api_key: str = "EMPTY"
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.api_key = api_key

    def _format_prompt(self, messages):
        """Format messages using the chat template format (template 2)"""
        formatted_prompt = ""

        for message in messages:
             # Handle both dict-like messages and LangChain message objects
            if hasattr(message, 'type') and hasattr(message, 'content'):
                role = message.type if hasattr(message, 'type') else "user"
                content = message.content
            elif isinstance(message, dict):
                role = message.get("role", "").lower()
                content = message.get("content", "")
            else:
                role = "user"
                content = str(message)

            # Apply template formatting
            if role == "system":
                formatted_prompt += f"<|im_start|>system<|im_sep|>{content}<|im_end|>"
            elif role == "user" or role == "human":
                formatted_prompt += f"<|im_start|>user<|im_sep|>{content}<|im_end|>"
            elif role == "assistant":
                formatted_prompt += f"<|im_start|>assistant<|im_sep|>{content}<|im_end|>"
            else:
                formatted_prompt += f"<|im_start|>{role}<|im_sep|>{content}<|im_end|>"

        # Add the assistant prefix for the model to continue from
        if not formatted_prompt.endswith("<|im_start|>assistant<|im_sep|>"):
            formatted_prompt += "<|im_start|>assistant<|im_sep|>"

        return formatted_prompt

    # Removed _create_modified_prompt and the complex logic from ainvoke
    # as it's not relevant for the simple reasoning task.
    async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
        """Async call to completion endpoint with direct API request"""
        max_tokens = kwargs.get("max_tokens", None)

        try:
            # Simplified: Assume prompt is always a list of message dicts
            if not isinstance(prompt, list):
                 raise TypeError("CustomChat2.ainvoke expects prompt to be a list of message dictionaries.")

            formatted_prompt = self._format_prompt(prompt) # Pass the list directly

            # Create completion parameters
            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "temperature": self.temperature,
                "stop": ["<|im_end|>"] # Add stop token
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            # Make direct API request using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/completions",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Error from API: {error_text}")

                    result = await response.json()

                    # Create a response object with the same interface
                    return type('Response', (), {
                        'content': result.get("choices", [{}])[0].get("text", "")
                    })()
        except Exception as e:
            print(f"Exception in CustomChat2.ainvoke: {str(e)}")
            raise

# Removed the Unix-specific time_limit context manager

def get_model(config: ARCBenchmarkConfig, role: str = "main"):
    """
    Initialize the Chat model based on configuration.
    For LOCAL models, it connects to a local endpoint.
    For other models, it uses the OpenRouter API.

    Args:
        config: The ARCBenchmarkConfig instance
        role: The role of the model (e.g. "main", "auxiliary", etc.) - currently only 'main' is relevant
    """
    logging.debug(f"get_model called for role: {role}, identifier: {config.model_identifier}")
    # Get model name string from config based on role
    # Assuming config will have attributes like 'main_model_name', 'aux_model_name' etc.
    # For now, using the single 'model_identifier' and hardcoding role='main' logic
    model_name_str = config.model_identifier # Example: "LOCAL_0", "CLAUDE"

    # Find the corresponding ModelOption enum member
    try:
        model_enum_member = ModelOption[model_name_str]
        model_value = model_enum_member.value # e.g., "/Home/stat/...", "anthropic/claude..."
        logging.debug(f"Resolved model enum: {model_enum_member.name}, value: {model_value}")
    except KeyError:
        logging.error(f"Invalid model identifier in config: {model_name_str}")
        raise ValueError(f"Invalid model identifier in config: {model_name_str}. Must be a valid ModelOption name.")

    # Get temperature and template based on role (simplified for now)
    if role == "main":
        temp = getattr(config, 'main_temp', 0) # Default if not set
        template = getattr(config, 'main_template', 1) # Default if not set
    # Add elif for other roles if needed later
    else: # Default to main settings if role is unknown
        temp = getattr(config, 'main_temp', 0)
        template = getattr(config, 'main_template', 1)


    # Check if it's a local model based on the enum member name
    if model_enum_member.name.startswith("LOCAL_"):
        port = getattr(config, f'{role}_port', 8000) # Default port if not set
        logging.info(f"Initializing LOCAL model: {model_enum_member.name} ({model_value}) on port {port} using template {template}")
        # Choose between CustomChat and CustomChat2 based on template setting
        if template == 2:
            model_instance = CustomChat2(
                model=model_value,
                temperature=temp,
                api_key="EMPTY",
                base_url=f"http://localhost:{port}/v1")
        else: # Default to template 1
            model_instance = CustomChat(
                model=model_value,
                temperature=temp,
                api_key="EMPTY",
                base_url=f"http://localhost:{port}/v1")
        logging.debug(f"Local model instance created: {type(model_instance).__name__}")
        return model_instance
    else: # Assume OpenRouter model
        logging.info(f"Initializing OpenRouter model: {model_enum_member.name} ({model_value})")
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            logging.error("OPENROUTER_API_KEY environment variable not found.")
            raise ValueError("OPENROUTER_API_KEY is not set in the environment variables.")
        else:
            # Log partial key for verification without exposing the full key
            masked_key = '*' * (len(openrouter_api_key) - 4) + openrouter_api_key[-4:]
            logging.info(f"Found OPENROUTER_API_KEY ending in: {masked_key}")

        model_instance = OpenRouterChat(
            model=model_value,
            temperature=temp,
            api_key=openrouter_api_key)
        logging.debug(f"OpenRouter model instance created: {type(model_instance).__name__}")
        return model_instance


def async_retry(max_retries: int = 3, timeout: int = 600):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # Use logging instead of print
                    logging.debug(f"Calling decorated function: {func.__name__}")
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                    logging.debug(f"Decorated function {func.__name__} completed successfully.")
                    return result
                except asyncio.TimeoutError:
                    retry_count += 1
                    logging.warning(f"Timeout occurred calling {func.__name__}. Retrying ({retry_count}/{max_retries})...")
                    if retry_count == max_retries:
                        logging.error(f"Max retries reached for {func.__name__} after timeout.")
                        raise
                    await asyncio.sleep(1) # Wait before retrying
                except Exception as e:
                    retry_count += 1
                    logging.warning(f"Error occurred calling {func.__name__}: {e}. Retrying ({retry_count}/{max_retries})...", exc_info=True) # Log traceback
                    if retry_count == max_retries:
                        logging.error(f"Max retries reached for {func.__name__} after error.")
                        raise
                    await asyncio.sleep(1) # Wait before retrying
            # This part should ideally not be reached if max_retries > 0
            logging.critical(f"Logic error: Exited retry loop for {func.__name__} without success or max retries exception.")
            raise Exception(f"Failed {func.__name__} after {max_retries} retries")
        return wrapper
    return decorator

@async_retry(max_retries=3, timeout=600)
async def get_model_response(model, prompt, max_tokens=None) -> str:
    """Get response from model with retry logic"""
    logging.debug(f"get_model_response called for model type: {type(model).__name__}")
    try:
        response = await model.ainvoke(prompt, max_tokens=max_tokens)
        # Log raw response content before returning
        raw_content = getattr(response, 'content', 'N/A') # Safely get content
        logging.debug(f"Raw response content from model.ainvoke: '{str(raw_content)[:200]}...'")
        return raw_content
    except Exception as e:
        # Error is already logged by the retry decorator or ainvoke, just re-raise
        logging.debug(f"get_model_response raising exception for retry: {e}")
        raise # Re-raise the exception for the retry decorator to catch
