import os
import asyncio
import signal
import aiohttp
from dotenv import load_dotenv
from functools import wraps
from contextlib import contextmanager
from typing import Optional, Dict, List, Callable, Tuple, TypeVar, Any
from utils.benchmark_config import *
T = TypeVar('T')
load_dotenv()
class TimeoutException(Exception): pass

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
        
        # Process messages to properly handle system prompts
        messages = []
        system_content = ""
        # Handle different prompt types
        if hasattr(prompt, 'content'):  # Single LangChain message object
            messages = [{"role": "user", "content": prompt.content}]
        elif isinstance(prompt, list):  # List of messages
            # Extract system message if present
            for msg in prompt:
                if hasattr(msg, 'type') and msg.type == 'system':
                    system_content = msg.content
                elif isinstance(msg, dict) and msg.get("role", "").lower() == "system":
                    system_content = msg.get("content", "")
            
            # Get the last user message
            user_content = ""
            for msg in reversed(prompt):
                if hasattr(msg, 'type') and msg.type == 'human':
                    user_content = msg.content
                    break
                elif isinstance(msg, dict) and msg.get("role", "").lower() == "human":
                    user_content = msg.get("content", "")
                    break
            
            # Combine system and user content if both exist
            if system_content and user_content:
                combined_content = f"System instructions:\n{system_content}\n\nUser message:\n{user_content}"
                messages = [{"role": "user", "content": combined_content}]
            elif user_content:
                messages = [{"role": "user", "content": user_content}]
            elif prompt:  # Fallback to last message if no user message found
                last_msg = prompt[-1]
                if hasattr(last_msg, 'content'):
                    messages = [{"role": "user", "content": last_msg.content}]
                elif isinstance(last_msg, dict):
                    messages = [{"role": "user", "content": last_msg.get("content", "")}]
        else:  # String or other
            messages = [{"role": "user", "content": str(prompt)}]
            
        payload = {
            "model": self.model,
            "messages": messages,
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
                    return type('Response', (), {
                        'content': result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    })()
            except Exception as e:
                print(f"Exception in OpenRouterChat.ainvoke: {str(e)}")
                raise



class CustomChat:
    """Chat model that makes direct API requests to local endpoints"""
    
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
        """Format messages using the Phi chat template format"""
        formatted_prompt = ""
        
        for message in messages:
            # Handle both dict-like messages and LangChain message objects
            if hasattr(message, 'type') and hasattr(message, 'content'):
                # LangChain message object
                role = message.type if hasattr(message, 'type') else "user"
                content = message.content
            elif isinstance(message, dict):
                # Dictionary message format
                role = message.get("role", "").lower()
                content = message.get("content", "")
            else:
                # Fallback for other formats
                role = "user"
                content = str(message)
            if role == "system":
                formatted_prompt += f"<|im_start|>system\\n{content}<|im_end|>\\n"
            elif role == "user":
                formatted_prompt += f"<|im_start|>user\\n{content}<|im_end|>\\n"
            elif role == "human":
                formatted_prompt += f"<|im_start|>user\\n{content}<|im_end|>\\n"
            elif role == "assistant":
                formatted_prompt += f"<|im_start|>assistant\\n{content}<|im_end|>"
            else:
                # Handle other roles or fallback
                formatted_prompt += f"<|im_start|>{role}\\n{content}<|im_end|>"
                
        # Add the assistant prefix for the model to continue from
        if not formatted_prompt.endswith("<|im_start|>assistan\\n"):
            formatted_prompt += "<|im_start|>assistant\\n"
            
        return formatted_prompt

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
        """Async call to completion endpoint with direct API request"""
        max_tokens = kwargs.get("max_tokens", None)
        
        try:
            # Format the prompt using our chat template
            formatted_prompt = self._format_prompt(prompt)
            
            # Create completion parameters
            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "temperature": self.temperature
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
        """Format messages using the Phi chat template format"""
        formatted_prompt = ""
        
        for message in messages:
            # Handle both dict-like messages and LangChain message objects
            if hasattr(message, 'type') and hasattr(message, 'content'):
                # LangChain message object
                role = message.type if hasattr(message, 'type') else "user"
                content = message.content
            elif isinstance(message, dict):
                # Dictionary message format
                role = message.get("role", "").lower()
                content = message.get("content", "")
            else:
                # Fallback for other formats
                role = "user"
                content = str(message)
            
            if role == "system":
                formatted_prompt += f"<|im_start|>system<|im_sep|>{content}<|im_end|>"
            elif role == "user":
                formatted_prompt += f"<|im_start|>user<|im_sep|>{content}<|im_end|>"
            elif role == "assistant":
                formatted_prompt += f"<|im_start|>assistant<|im_sep|>{content}<|im_end|>"
            else:
                # Handle other roles or fallback
                formatted_prompt += f"<|im_start|>{role}<|im_sep|>{content}<|im_end|>"
                
        # Add the assistant prefix for the model to continue from
        if not formatted_prompt.endswith("<|im_start|>assistant<|im_sep|>"):
            formatted_prompt += "<|im_start|>assistant<|im_sep|>"
            
        return formatted_prompt
    
    
    def _create_modified_prompt(self, original_messages, first_response, modified_thinking):
        """Create a new prompt with the modified thinking section"""
        # Extract the system message and user question from original messages
        system_content = ""
        user_content = ""
        
        for message in original_messages:
            if hasattr(message, 'type') and message.type == 'system':
                system_content = message.content
            elif hasattr(message, 'type') and message.type == 'user':
                user_content = message.content
            elif isinstance(message, dict):
                role = message.get("role", "").lower()
                if role == "system":
                    system_content = message.get("content", "")
                elif role == "user":
                    user_content = message.get("content", "")
        
        # Create the modified prompt with the "wait a second" thinking
        modified_prompt = (
            f"<|im_start|>system<|im_sep|>{system_content}<|im_end|>"
            f"<|im_start|>user<|im_sep|>{user_content}<|im_end|>"
            f"<|im_start|>assistant<|im_sep|>"
            f"<thinking>{modified_thinking}</thinking>"
        )
        
        return modified_prompt

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> Any:
        """
        Get first response, modify thinking with '...no wait a second',
        then get second response and return that
        """
        max_tokens = kwargs.get("max_tokens", None)
        
        try:
            # Step 1: Get the first response
            formatted_prompt = self._format_prompt(prompt)
            
            # Create completion parameters for first request
            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "temperature": self.temperature
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            # Make first API request
            first_response = ""
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
                    first_response = result.get("choices", [{}])[0].get("text", "")
            
            # Step 2: Extract thinking section
            thinking_content = self._extract_thinking_section(first_response)
            
            # If no thinking section found, return the first response
            if not thinking_content:
                return type('Response', (), {'content': first_response})()
            
            # Step 3: Modify thinking with "...no wait a second"
            modified_thinking = self._modify_thinking_with_wait(thinking_content)
            
            # Step 4: Create modified prompt with the wait pattern
            modified_prompt = self._create_modified_prompt(prompt, first_response, modified_thinking)
            
            # Step 5: Get second response with modified prompt
            second_payload = {
                "model": self.model,
                "prompt": modified_prompt,
                "temperature": self.temperature
            }
            
            if max_tokens:
                second_payload["max_tokens"] = max_tokens
            
            # Make second API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/completions",
                    json=second_payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Error from API: {error_text}")
                    
                    result = await response.json()
                    second_response = result.get("choices", [{}])[0].get("text", "")
            
            # Return the second response
            return type('Response', (), {'content': second_response})()
            
        except Exception as e:
            print(f"Exception in CustomChat2.ainvoke: {str(e)}")
            raise

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def get_model(config: BenchmarkConfig, role: str = "main"):
    """
    Initialize the ChatOpenAI model based on configuration.
    For LOCAL models, it connects to a local endpoint.
    For other models, it uses the OpenRouter API.
    
    Args:
        config: The benchmark configuration
        role: The role of the model (e.g. "main", "auxiliary", etc.)
    """
    model = ModelOption[getattr(config, role)]
    
    name = model.value
    
    if role=="main":
        temp=config.main_temp
        template=config.main_template
    elif role=="auxiliary":
        temp = config.auxiliary_temp
        template=config.auxiliary_template
    else:
        temp=config.auxiliary2_temp
        template=config.auxiliary2_template

    # Check if the model name starts with "LOCAL_" to handle any LOCAL_number pattern
    if str(model).startswith("ModelOption.LOCAL_"):
        port = {
            "main": config.main_port,
            "auxiliary": config.auxiliary_port,
            "auxiliary2": config.auxiliary2_port
        }.get(role, config.main_port)
        
        # Choose between CustomChat and CustomChat2 based on template setting
        if template == 2:
            return CustomChat2(
                model=name,
                temperature=temp,
                api_key="EMPTY",
                base_url=f"http://localhost:{port}/v1")
        else:
            return CustomChat(
                model=name,
                temperature=temp,
                api_key="EMPTY",
                base_url=f"http://localhost:{port}/v1")
    else:
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in the environment variables.")
        
        return OpenRouterChat(
            model=name,
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
                    if retry_count == max_retries:
                        raise
                    await asyncio.sleep(1)
                except Exception as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        raise
                    await asyncio.sleep(1)
            raise Exception(f"Failed after {max_retries} retries")
        return wrapper
    return decorator

@async_retry(max_retries=3, timeout=120)
async def get_model_response(model, prompt, max_tokens=None) -> str:
    """Get response from model with retry logic"""
    try:
        if max_tokens==None:
            response = await model.ainvoke(prompt)
        else:
            response = await model.ainvoke(prompt, max_tokens=max_tokens)
        return response.content
    except Exception as e:
        # Add small delay before retry to prevent overwhelming API
        await asyncio.sleep(0.1)
        raise
