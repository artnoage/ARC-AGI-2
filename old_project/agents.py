from typing import Union, Tuple, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from utils.model_utils import get_model_response

FULLSOLUTION_SYSTEM_PROMPT = """You will be given a mathematical problem. Carefully analyze it before providing a well-structured response.
Your output must include two clearly separated sections: a **thinking** section and a **response** section.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints.
Thoughts about the nature of the problem, potential difficulties, suitable solution methods.
You can attempt trial and error. You can backtrack, or correct mistakes. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
Do not proceed if you dont feel confident about the answer. 
</thinking>

<response>
<step>Step 1: Clearly state initial calculations
Show work with LaTeX notation</step>

<step>Step 2: Logical next step
Clearly numbered and self-contained</step>

<step>Step N: Final conclusion clearly stated
Answer in \boxed{}</step>
</response>"""


FULLSOLUTION_SYSTEM_PROMPT_WITH_REFLECTION = """You will be given a mathematical problem. Carefully analyze it before providing a well-structured response.
Your output must include three clearly separated sections: a **thinking** section, a **response** section, and a **reflection** section.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints.
Thoughts about the nature of the problem, potential difficulties, suitable solution methods.
You can attempt trial and error. You can backtrack, or correct mistakes. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
Do not proceed if you dont feel confident about the answer. 
</thinking>

<response>
<step>Step 1: Clearly state initial calculations
Show work with LaTeX notation</step>

<step>Step 2: Logical next step
Clearly numbered and self-contained</step>

<step>Step N: Final conclusion clearly stated
Answer in \boxed{}</step>
</response>

<reflection>
After completing your solution, critically evaluate your answer:
- If you believe your answer is correct, explain why: "The answer is correct because..." followed by a brief justification.
- If you have doubts about your answer, explain why: "The answer may not be correct because..." followed by your concerns.
</reflection>"""

FINALIZATION_SYSTEM_PROMPT= """You will be given a mathematical problem and a partial solution. Your task is to finalize the solution.

Your response MUST include both a <thinking> section and a <response> section.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
Continue the solution from where it left off, maintaining the same step numbering and style.
The partial solution will only contain the beginning of the response section with some steps.
You must continue with the next step number in sequence.

IMPORTANT: Each step must be properly enclosed in <step> and </step> tags.

For example, if the partial solution ends with Step 2, you should start with:

<step>Step 3: [Description of the step]
[Mathematical work for this step]
</step>

Continue with additional steps as needed:

<step>Step 4: [Description of the step]
[Mathematical work for this step]
</step>

In your final step, include your answer in a LaTeX boxed environment:
\\boxed{your final answer}

Make sure all your steps follow logically from the partial solution and that each step has both opening and closing tags.
</response>"""



TUTOR_SYSTEM_PROMPT = """You are a mathematical tutor who evaluates solutions and identifies errors.

You will be given a mathematical problem along with a proposed solution to analyze.

Your output must include two clearly separated sections: **Thinking** and **Response**.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
Explicitly provide your verdict and necessary corrections.

<verdict>
State exactly one of the following:
- 'Step X' (where X is the **first incorrect step number**)
- 'The answer is correct' (if no errors are found)
</verdict>

<finalization>
If an incorrect step was found, provide the corrected solution starting from that step:
- Format: '<step>Step X: [corrected version]</step>...<step>Final Step</step>'
- Otherwise, leave this section empty.
</finalization>
</response>"""

PROGRAMMER_SYSTEM_PROMPT="""You will be given a mathematical problem.
Your general task is to write a Python program that solves the problem.
Your output must include two clearly separated sections: **Thinking** and **Response**.


<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints.
Thoughts about the nature of the problem, potential difficulties, suitable solution methods.
You can attempt trial and error. You can backtrack, or correct mistakes. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
Do not proceed if you dont feel confident about the answer. 
</thinking>

<response>
In this section, write a complete, self-contained Python program that solves the problem, based explicitly on the approach described in the thinking section above. Your code must:
1. Include clear comments explaining each step of your approach within the code itself.
2. Print the final answer explicitly as a single numeric value (float or integer, as appropriate).
3. Gracefully handle potential errors or edge cases.
4. Be efficient and avoid excessive resource usage.

Do NOT include explanations outside code comments. Your response here must contain ONLY valid Python code and comments.

Example format:

```python
# Solution for the problem
import math

# Step 1: Parse the problem
# [brief explanation comment]
...

# Step 2: Solve using appropriate method
# [brief explanation comment]
...

# Calculate and print the final answer
result = ...
print(result)  # Just the number, no text
</response>"""


PROGRAMMER_SYSTEM_PROMPT_SUB="""You will be given a mathematical problem and some general instructions.
Your general task is to write a Python program that solves the problem.
Your output must include two clearly separated sections: **Thinking** and **Response**.


<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
In this section, write a complete, self-contained Python program that solves the problem, based explicitly on the approach described in the thinking section above. Your code must:
1. Include clear comments explaining each step of your approach within the code itself.
2. Print the final answer explicitly as a single numeric value (float or integer, as appropriate).
3. Gracefully handle potential errors or edge cases.
4. Be efficient and avoid excessive resource usage.

Do NOT include explanations outside code comments. Your response here must contain ONLY valid Python code and comments.

Example format:

```python
# Solution for the problem
import math

# Step 1: Parse the problem
# [brief explanation comment]
...

# Step 2: Solve using appropriate method
# [brief explanation comment]
...

# Calculate and print the final answer
result = ...
print(result)  # Just the number, no text
</response>"""

ARCHITECT_SYSTEM_PROMPT="""You are an expert mathematical problem-solving engineer. 
Your task is to analyze mathematical problems and create concise instructions for a programmer who will implement the solution.
Your output must include two clearly separated sections: a **thinking** section and a **response** section.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
Provide instructions for the programmer. Include:

1. **Problem Analysis**: Brief restatement of the problem

2. **Recommended Approach**: Specific algorithm or mathematical technique to use

3. **Libraries**: List recommended Python libraries (numpy, sympy, scipy, math), and include non-standard ones for special problems.

4. **Implementation Structure**: Key functions and data structures

5. **Potential Pitfalls**: Edge cases, numerical issues, performance considerations

6. **Output Format**: How the final answer should be formatted

Your instructions should be clear and concise while providing all necessary guidance.
</response>"""



TESTER_SYSTEM_PROMPT=""" You will be provided with a mathematical problem. 
Your task is **not necessarily solve** this problem but rather to create a Python function that **efficiently verifies** whether a given 
numeric value (float) correctly solves the problem.
Your output must include two clearly separated sections: a **thinking** section and a **response** section.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
Write a Python function named `test_solution(answer)` that:
1. Accepts exactly one float parameter named `answer`.
2. Returns `True` if the given answer correctly solves the problem (using appropriate numerical tolerances, e.g., `1e-2`).
3. Returns `False` otherwise.

**Important Guidelines**:
- Your function should be self-contained, efficient, and only rely on standard Python libraries (`numpy`, `sympy`, and `scipy` are allowed).
- Include brief, clear comments explaining how verification is performed.
- Handle floating-point precision explicitly with tolerances.

**Example of a verification scenario**:
If the mathematical problem is:
> "Find the root of the equation \\( x^2 - 2 = 0 \\)."

Your verification function could look like this:

```python
import numpy as np

def test_solution(answer):
    # Check if answer squared minus 2 is approximately zero.
    return np.abs(answer**2 - 2) < 1e-2

    Notice:

The function doesn't compute the root; it verifies whether the provided number meets the criteria (equation satisfied within tolerance).

Your response should strictly follow this verification approach. 
</response> """



DUAL_PROOF_SYSTEM_PROMPT="""You will be given a mathematical problem. Your task is to solve it using both logical reasoning and programming.

Your output must include two clearly separated sections: **Thinking** and **Response**.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
Your response must include both a logical proof and a programming solution:

<proof>
Provide a formal mathematical proof or solution:
- Use clear, step-by-step logical reasoning
- Include any necessary mathematical notation (using LaTeX where appropriate)
- Ensure each step follows logically from the previous ones
- Conclude with the final answer in a \boxed{} environment
</proof>

<code>
Provide a complete, self-contained Python program that solves the problem:
- Include necessary imports (numpy, sympy, scipy are allowed)
- Use clear variable names and add comments explaining your approach
- Implement an efficient algorithm based on your thinking
- Print only the final numeric answer (no text)
- Handle potential edge cases appropriately
</code>

Both solutions should arrive at the same answer, though they may use different approaches.
</response>"""

TEST_DRIVEN_PROGRAMMER_SYSTEM_PROMPT="""You will be given a mathematical problem. Your task is to solve it using a test-driven programming approach.

Your output must include two clearly separated sections: **Thinking** and **Response**.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints. 
Use this freedom to ensure you've gathered all insights necessary to clearly and effectively provide the requested response.
</thinking>

<response>
Your response must include both a test suite and an implementation:

<test>
Write a Python function named `test_solution(answer)` that:
1. Accepts exactly one float parameter named `answer`.
2. Returns `True` if the given answer correctly solves the problem (using appropriate numerical tolerances, e.g., `1e-2`).
3. Returns `False` otherwise.

**Important Guidelines**:
- Your function should be self-contained, efficient, and only rely on standard Python libraries (`numpy`, `sympy`, and `scipy` are allowed).
- Include brief, clear comments explaining how verification is performed.
- Handle floating-point precision explicitly with tolerances.
- Write additional test cases using unittest or pytest to verify your implementation.

Example:
```python
import numpy as np

def test_solution(answer):
    # Check if answer satisfies the problem constraints
    # Use appropriate tolerance for floating-point comparison
    return np.abs(expected_value - answer) < 1e-2
```
</test>

<implementation>
Provide a complete, self-contained Python program that solves the problem:
- Include necessary imports (numpy, sympy, scipy are allowed)
- Use clear variable names and add comments explaining your approach
- Implement an efficient algorithm based on your thinking
- Print only the final numeric answer (no text)
- Ensure your implementation passes all the tests you've written
</implementation>

Both the tests and implementation should work together to solve the problem correctly.
</response>"""




class FinalizationAgent:
    """Agent that finalizes partial solutions"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, partial_solution: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Finalize a partial solution"""
        system_prompt = FINALIZATION_SYSTEM_PROMPT

        prompt = [SystemMessage(content=system_prompt),
            HumanMessage(content=(
                f"Problem: {problem}\n\n"
                f"Partial Solution: {partial_solution}"
            ))
        ]
        response = await get_model_response(self.model, prompt, max_tokens=8192)
        return (prompt[0].content, response) if return_prompt else response



class FullSolutionAgent:
    """Agent that provides complete solutions with analysis and steps"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate a complete solution with analysis and steps"""
        system_prompt = FULLSOLUTION_SYSTEM_PROMPT
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"{problem}")
        ]
        response = await get_model_response(self.model, prompt, max_tokens=4192)
        return (system_prompt + "\n\n" + problem, response) if return_prompt else response
    

class TutorAgent:
    """Agent that evaluates mathematical solutions and identifies the first wrong step"""
    
    def __init__(self, model):
        self.model = model
        
    async def find_first_wrong_step(self, problem: str, solution: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """
        Analyze a solution and identify the first step that contains an error.
        Returns analysis, verdict and suggested correction in a structured format.
        """
        system_prompt = TUTOR_SYSTEM_PROMPT

        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=(
                "Here is a mathematical problem and a proposed solution:\n\n"
                f"Problem:\n{problem}\n\n"
                f"Proposed Solution:\n{solution}"
            ))
        ]
        response = await get_model_response(self.model, prompt, max_tokens=8192)
        return (system_prompt + "\n\n" + problem + "\n\n" + solution, response) if return_prompt else response

class ProgrammingAgent:
    """Agent that generates Python code to solve mathematical problems"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate Python code that solves the mathematical problem"""
        system_prompt = PROGRAMMER_SYSTEM_PROMPT

        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(f"Problem:\n{problem}\n\n")
        ]
        response = await get_model_response(self.model, prompt, max_tokens=16384)
        return (system_prompt + "\n\n" + f"Problem:\n{problem}\n\n", response) if return_prompt else response
    
    

class ArchitectAgent:
    """Agent that analyzes problems and creates prompts for programming agents"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate engineering analysis and prompt for a programming agent"""
        system_prompt = ARCHITECT_SYSTEM_PROMPT

        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Problem:\n{problem}\n\n")
        ]
        response = await get_model_response(self.model, prompt, max_tokens=8192)
        return (system_prompt + "\n\n" + f"Problem:\n{problem}\n\n", response) if return_prompt else response


class TestingAgent:
    """Agent that creates test functions for mathematical problems"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate a test function that verifies solutions to the mathematical problem"""
        system_prompt = TESTER_SYSTEM_PROMPT

        content = f"Problem:\n{problem}\n\n"
        
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=content)
        ]
        response = await get_model_response(self.model, prompt, max_tokens=8192)
        return (system_prompt + "\n\n" + content, response) if return_prompt else response


class DualProofAgent:
    """Agent that provides both logical proof and programming solution"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate both a logical proof and a programming solution for the problem"""
        system_prompt = DUAL_PROOF_SYSTEM_PROMPT

        content = f"Problem:\n{problem}\n\n"
        
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=content)
        ]
        response = await get_model_response(self.model, prompt, max_tokens=8192)
        return (system_prompt + "\n\n" + content, response) if return_prompt else response


class TestDrivenProgrammerAgent:
    """Agent that provides both test suite and implementation for a problem"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate both a test suite and an implementation for the problem"""
        system_prompt = TEST_DRIVEN_PROGRAMMER_SYSTEM_PROMPT

        content = f"Problem:\n{problem}\n\n"
        
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=content)
        ]
        response = await get_model_response(self.model, prompt, max_tokens=8192)
        return (system_prompt + "\n\n" + content, response) if return_prompt else response


class ReflectiveSolutionAgent:
    """Agent that provides complete solutions with analysis, steps, and reflection"""
    
    def __init__(self, model):
        self.model = model
        
    async def generate(self, problem: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """Generate a complete solution with analysis, steps, and self-reflection"""
        system_prompt = FULLSOLUTION_SYSTEM_PROMPT_WITH_REFLECTION
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"{problem}")
        ]
        response = await get_model_response(self.model, prompt, max_tokens=4192)
        return (system_prompt + "\n\n" + problem, response) if return_prompt else response


SOLUTION_VERIFIER_SYSTEM_PROMPT = """You are an expert mathematical solution verifier. Your task is to analyze a mathematical solution and evaluate it based on specific criteria.

You will be given:
1. A mathematical problem statement
2. A proposed solution (with the final boxed answer removed)

Your output must include two clearly separated sections: a **thinking** section and a **response** section.

<thinking>
Use this area as your creative scratchpad.
Feel free to capture your thoughts, abstractions, corrections, or ideas in any order and form you wish—without constraints.
Analyze the solution step by step, noting any errors or issues.
Determine if the solution is detailed enough with clear steps and reasoning.
Determine if the solution's approach and reasoning are correct.
Calculate what the final boxed answer should be.
</thinking>

<response>
Provide your assessment in a structured JSON format that looks like this:
{
  "is_detailed": true or false,
  "is_correct": true or false,
  "boxed_answer": numeric value or string
}

Where:
- "is_detailed": Boolean (true/false) indicating if this is a detailed solution with clear steps and reasoning
- "is_correct": Boolean (true/false) indicating if the solution's approach and reasoning are correct
- "boxed_answer": The final answer that should be in the box (as a number or string)

Make sure your response contains only this JSON object and nothing else, so it can be properly parsed.
</response>
"""

class SolutionVerifierAgent:
    """Agent that verifies mathematical solutions and provides structured assessment"""
    
    def __init__(self, model):
        self.model = model
        
    async def verify(self, problem: str, solution: str, return_prompt: bool = False) -> Union[str, Tuple[str, str]]:
        """
        Verify a mathematical solution and provide structured assessment
        
        Args:
            problem: The mathematical problem statement
            solution: The solution to verify (with boxed answer removed)
            return_prompt: Whether to return the prompt along with the response
            
        Returns:
            Full response from the model or tuple of (prompt, response)
        """
        system_prompt = SOLUTION_VERIFIER_SYSTEM_PROMPT
        
        content = (
            f"Problem:\n{problem}\n\n"
            f"Solution (with boxed answer removed):\n{solution}"
        )
        
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=content)
        ]
        
        full_response = await get_model_response(self.model, prompt, max_tokens=4096)
        
        return (system_prompt + "\n\n" + content, full_response) if return_prompt else full_response


