import os
import asyncio
# Removed signal import
import aiohttp
from dotenv import load_dotenv
from functools import wraps
# Removed contextmanager import
from typing import Optional, Dict, List, Callable, Tuple, TypeVar, Any
# Explicitly import required classes from config
from config import ARCBenchmarkConfig, ModelOption
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

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
        """Async call to OpenRouter chat completion endpoint"""
        max_tokens = kwargs.get("max_tokens", None)

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
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Create a new session for each request
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        raise ValueError(f"Error from OpenRouter API: {await response.text()}")

                    result = await response.json()
                    # Return simple object with .content attribute
                    return type('Response', (), {
                        'content': result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    })()
            except Exception as e:
                print(f"Exception in OpenRouterChat.ainvoke: {str(e)}")
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
    # Get model name string from config based on role
    # Assuming config will have attributes like 'main_model_name', 'aux_model_name' etc.
    # For now, using the single 'model_identifier' and hardcoding role='main' logic
    model_name_str = config.model_identifier # Example: "LOCAL_0", "CLAUDE"

    # Find the corresponding ModelOption enum member
    try:
        model_enum_member = ModelOption[model_name_str]
        model_value = model_enum_member.value # e.g., "/Home/stat/...", "anthropic/claude..."
    except KeyError:
        raise ValueError(f"Invalid model identifier in config: {model_name_str}. Must be a valid ModelOption name.")

    # Get temperature and template based on role (simplified for now)
    if role == "main":
        temp = getattr(config, 'main_temp', 0.7) # Default if not set
        template = getattr(config, 'main_template', 1) # Default if not set
    # Add elif for other roles if needed later
    else: # Default to main settings if role is unknown
        temp = getattr(config, 'main_temp', 0.7)
        template = getattr(config, 'main_template', 1)


    # Check if it's a local model based on the enum member name
    if model_enum_member.name.startswith("LOCAL_"):
        port = getattr(config, f'{role}_port', 8000) # Default port if not set

        # Choose between CustomChat and CustomChat2 based on template setting
        if template == 2:
            return CustomChat2(
                model=model_value, # Use the actual path/name from enum value
                temperature=temp,
                api_key="EMPTY",
                base_url=f"http://localhost:{port}/v1")
        else: # Default to template 1
            return CustomChat(
                model=model_value, # Use the actual path/name from enum value
                temperature=temp,
                api_key="EMPTY",
                base_url=f"http://localhost:{port}/v1")
    else: # Assume OpenRouter model
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in the environment variables.")

        return OpenRouterChat(
            model=model_value, # Use the actual model name from enum value
            temperature=temp,
            api_key=openrouter_api_key)


def async_retry(max_retries: int = 3, timeout: int = 120):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_count = 0
            while retry_count < max_retries:
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                except asyncio.TimeoutError:
                    retry_count += 1
                    print(f"Timeout occurred. Retrying ({retry_count}/{max_retries})...")
                    if retry_count == max_retries:
                        print("Max retries reached after timeout.")
                        raise
                    await asyncio.sleep(1) # Wait before retrying
                except Exception as e:
                    retry_count += 1
                    print(f"Error occurred: {e}. Retrying ({retry_count}/{max_retries})...")
                    if retry_count == max_retries:
                        print("Max retries reached after error.")
                        raise
                    await asyncio.sleep(1) # Wait before retrying
            # This part should ideally not be reached if max_retries > 0
            raise Exception(f"Failed after {max_retries} retries")
        return wrapper
    return decorator

@async_retry(max_retries=3, timeout=120)
async def get_model_response(model, prompt, max_tokens=None) -> str:
    """Get response from model with retry logic"""
    try:
        response = await model.ainvoke(prompt, max_tokens=max_tokens)
        return response.content
    except Exception as e:
        print(f"Error in get_model_response (will be retried): {e}")
        # Add small delay before retry to prevent overwhelming API
        await asyncio.sleep(0.1)
        raise # Re-raise the exception for the retry decorator to catch
