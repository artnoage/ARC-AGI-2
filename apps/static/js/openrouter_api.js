/**
 * OpenRouter API Integration for ARC AI Discussion Interface
 * Handles communication with OpenRouter API for AI model responses
 */

// Available models from OpenRouter
const OPENROUTER_MODELS = {
    'claude': {
        id: 'anthropic/claude-3.7-sonnet',
        name: 'Claude 3.7 Sonnet'
    },
    'gemini-pro': {
        id: 'google/gemini-2.5-pro-preview',
        name: 'Gemini 2.5 Pro'
    },
    'gemini-pro-exp': {
        id: 'google/gemini-2.5-pro-exp-03-25',
        name: 'Gemini 2.5 Pro-exp'
    },
    'gemini-flash': {
        id: 'google/gemini-2.5-flash-preview',
        name: 'Gemini 2.5 Flash'
    },
    'gpt': {
        id: 'openai/gpt-4o-mini',
        name: 'GPT-4o Mini'
    }
};

// Default model
let SELECTED_MODEL = 'claude';

/**
 * Set the selected model
 * @param {string} modelKey - Key of the model to select
 */
function setSelectedModel(modelKey) {
    if (OPENROUTER_MODELS[modelKey]) {
        SELECTED_MODEL = modelKey;
        console.log(`Model set to: ${OPENROUTER_MODELS[SELECTED_MODEL].name}`);
        return true;
    }
    console.error(`Invalid model key: ${modelKey}`);
    return false;
}

/**
 * Get the currently selected model information
 * @returns {Object} Selected model information
 */
function getSelectedModel() {
    return OPENROUTER_MODELS[SELECTED_MODEL];
}

/**
 * Send a message to the OpenRouter API
 * @param {string} apiKey - OpenRouter API key
 * @param {string} userMessage - User's message
 * @param {string} taskContext - Context about the current task
 * @param {number} temperature - Temperature parameter for controlling randomness (0.0-1.0)
 * @param {Array} conversationHistory - Previous messages in the conversation
 * @param {boolean} useStreaming - Whether to use streaming for responses
 * @param {AbortController} abortController - AbortController for the request (optional, for streaming)
 * @param {function} onStreamChunk - Callback function for streaming chunks (optional)
 * @returns {Promise} Promise that resolves with the AI response
 */
async function sendMessageToOpenRouter(apiKey, userMessage, taskContext, temperature = 0.7, conversationHistory = [], useStreaming = false, abortController = null, onStreamChunk = null) {
    if (!apiKey) {
        throw new Error("API key is required");
    }

    const model = OPENROUTER_MODELS[SELECTED_MODEL];
    if (!model) {
        throw new Error("Invalid model selected");
    }

    // Start with the system message
    const messages = [
        {
            role: "system",
            content: "You are an AI assistant helping with Abstraction and Reasoning Corpus (ARC) tasks... " +
                     "Your goal is to help the user understand patterns, transformations, and reasoning strategies " +
                     "for solving ARC tasks. Be clear, helpful, and provide step-by-step explanations when appropriate. " +
                     
                     taskContext +
                     
                     "\n---\n" +
                     "In case the user asks for code generation I provide some guidlines:"+
                     "\n"+
                     "**Guidliness for Code Generation:**\n\n" +
                     "1.  Analyze the examples to determine the transformation rule.\n" +
                     "2.  Explain the rule clearly.\n" +
                     "3.  Provide Python code implementing the rule in a function named `solve_task`.\n" +
                     "4.  **IMPORTANT:** The `solve_task(task_input)` function must be robust. It should correctly handle being called with EITHER:\n" +
                     "    *   The full ARC task dictionary (where the relevant grid is typically `task_input['test'][0]['input']`).\n" +
                     "    *   Just the input grid itself (a list of lists).\n" +
                     "    Include checks (e.g., using `isinstance`) to determine the input type and extract/use the grid accordingly. Handle potential errors gracefully if the input format is unexpected.\n" +
                     "---"+
                     "\n---\n" +
                     "In case the user gives you hints:"+
                     "\n"+
                     "Take the hints into account in your thinking process but do NOT make any mention of them in your reasoning or in the code."+
                     "---"
        }
    ];
    
    // Add conversation history if available
    if (conversationHistory && conversationHistory.length > 0) {
        messages.push(...conversationHistory);
    }
    
    // Add the current user message
    messages.push({
        role: "user",
        content: userMessage
    });

    // Request body
    const requestBody = {
        model: model.id,
        messages: messages,
        temperature: temperature,
        stream: useStreaming
    };

    // Request options with extended timeout (180 seconds)
    const requestOptions = {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`
        },
        body: JSON.stringify(requestBody)
    };

    try {
        console.log(`Sending message to OpenRouter using model: ${model.id}, streaming: ${useStreaming}`);
        
        // If streaming is enabled and a callback is provided
        if (useStreaming && typeof onStreamChunk === 'function' && abortController) {
            return await handleStreamingResponse(requestOptions, abortController, onStreamChunk);
        } else {
            // Non-streaming approach with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                console.log("Non-streaming request timeout (180 seconds)");
                controller.abort();
            }, 180000); // 180 second timeout (3 minutes)
            
            const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
                ...requestOptions,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorText = await response.text();
                console.error("OpenRouter API error:", errorText);
                throw new Error(`OpenRouter API error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            console.log("OpenRouter response received");
            
            if (data.choices && data.choices.length > 0 && data.choices[0].message) {
                return data.choices[0].message.content;
            } else {
                console.error("Invalid response format:", data);
                throw new Error("Invalid response format from OpenRouter API");
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error("Request timed out after 180 seconds");
            throw new Error("Request timed out after 180 seconds. The model is taking too long to respond.");
        }
        console.error("Error sending message to OpenRouter:", error);
        throw error;
    }
}

/**
 * Handle streaming response from OpenRouter API
 * @param {Object} requestOptions - Fetch request options
 * @param {AbortController} abortController - AbortController for the request
 * @param {Function} onChunk - Callback function for each chunk
 * @returns {Promise<string>} Complete response text
 */
async function handleStreamingResponse(requestOptions, abortController, onChunk) {
    console.log("Starting streaming request to OpenRouter API");
    
    // Set up timeout for the passed AbortController
    const timeoutId = setTimeout(() => {
        console.log("Streaming request timeout (180 seconds)");
        if (!abortController.signal.aborted) {
            abortController.abort();
            
            // Force a timeout message to the user
            try {
                onChunk("\n\n[TIMEOUT: The model response was cut off after 180 seconds]");
            } catch (e) {
                console.error("Failed to send timeout message to UI:", e);
            }
        }
    }, 180000); // 180 seconds timeout (3 minutes)
    
    // Declare reader outside try block so it's accessible in catch block
    let reader = null;
    
    try {
        console.log("Sending fetch request to OpenRouter API...");
        const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            ...requestOptions,
            signal: abortController.signal
        });
        
        console.log("Streaming response received, status:", response.status, response.statusText);
        console.log("Response headers:", Object.fromEntries([...response.headers.entries()]));
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error("OpenRouter API streaming error:", errorText);
            throw new Error(`OpenRouter API error: ${response.status} ${response.statusText}`);
        }
        
        if (!response.body) {
            throw new Error("ReadableStream not supported in this browser.");
        }
        
        reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let completeResponse = "";
        let chunkCount = 0;
        let pendingText = ""; // Buffer for incomplete JSON data across chunks
        
        console.log("Starting to read streaming response");
        
        while (true) {
            // console.log(`DEBUG: Top of while loop, chunkCount: ${chunkCount}, pendingText: "${pendingText.substring(0,100)}"`); // General debug
            // Check if the request has been aborted before attempting to read
            if (abortController.signal.aborted) {
                console.log("Stream reading loop detected abort signal before read.");
                // Ensure reader is cancelled if it exists and hasn't been already
                if (reader && !reader.closed) { // Check if reader exists and is not already closed/cancelled
                    try {
                        await reader.cancel("Request aborted by user signal");
                        console.log("Reader cancelled inside loop due to abort signal.");
                    } catch (cancelError) {
                        console.warn("Error cancelling reader inside loop:", cancelError);
                    }
                }
                break; 
            }

            try {
                const { done, value } = await reader.read();

                // If aborted during or after read, but before processing 'done'
                if (abortController.signal.aborted) {
                    console.log("Stream reading aborted by signal (after read, before done check).");
                     if (reader && !reader.closed) {
                        try {
                            await reader.cancel("Request aborted by user signal post-read");
                            console.log("Reader cancelled post-read due to abort signal.");
                        } catch (cancelError) {
                            console.warn("Error cancelling reader post-read:", cancelError);
                        }
                    }
                    break;
                }

                if (done) {
                    console.log("Stream reading complete (done is true), received", chunkCount, "chunks");
                    // Process any remaining text in the buffer
                    if (pendingText.trim()) {
                        console.log("Processing remaining text in buffer:", pendingText);
                        try {
                            const extractedContent = extractContentFromText(pendingText, chunkCount);
                            if (extractedContent) {
                                completeResponse += extractedContent;
                                onChunk(extractedContent);
                            }
                        } catch (e) {
                            console.warn("Error processing remaining buffer:", e);
                        }
                    }
                    break; 
                }
                
                console.log(`Raw chunk ${chunkCount + 1} length:`, value ? value.length : 0);
                
                if (!value || value.length === 0) {
                    console.log(`Empty chunk received (${chunkCount + 1}), skipping`);
                    continue;
                }

                const decodedChunk = decoder.decode(value, { stream: true });
                chunkCount++;
                
                if (chunkCount >= 280 && chunkCount <= 300) {
                    console.log(`DEBUG CHUNK ${chunkCount} (length ${decodedChunk.length}): START`);
                    console.log(decodedChunk);
                    console.log(`DEBUG CHUNK ${chunkCount}: END`);
                    console.log(`DEBUG CHUNK ${chunkCount}: current pendingText before processing: "${pendingText.substring(0,200)}"`);
                } else if (chunkCount % 50 === 0) { // Log every 50 chunks for general progress
                    console.log(`Processing chunk ${chunkCount}...`);
                }
                // Original detailed logging for all chunks (can be re-enabled if needed, but verbose)
                // console.log(`--- Decoded Chunk ${chunkCount} START ---`);
                // console.log(decodedChunk);
                // console.log(`--- Decoded Chunk ${chunkCount} END ---`);
                
                const textToProcess = pendingText + decodedChunk;
                pendingText = ""; 
                
                const { processedText, remainingText } = processStreamChunk(textToProcess, chunkCount, completeResponse, onChunk);
                completeResponse = processedText; // This is the accumulated actual content for the final return
                pendingText = remainingText;

                if (chunkCount >= 280 && chunkCount <= 300) {
                    console.log(`DEBUG CHUNK ${chunkCount}: completeResponse length: ${completeResponse.length}`);
                    console.log(`DEBUG CHUNK ${chunkCount}: new pendingText after processing: "${pendingText.substring(0,200)}"`);
                }
                
            } catch (chunkError) {
                if (abortController.signal.aborted) {
                    // This error is likely a result of the stream being aborted.
                    // It's often an error like "The operation was aborted" or "The stream has been cancelled."
                    console.log(`Chunk processing interrupted by abort signal (chunk ${chunkCount}):`, chunkError.message);
                    break; 
                } else {
                    // For other errors not related to abort, log them more seriously.
                    console.error(`Error processing chunk ${chunkCount} (inside try-catch):`, chunkError);
                    // Depending on the error, you might want to break or continue.
                    // For now, we'll let it try to continue with the next chunk if possible,
                    // but critical errors might require a 'break;'.
                }
            }
        }
        
        clearTimeout(timeoutId);
        console.log("Final complete response length:", completeResponse.length);
        
        // If we have no complete response but received chunks, try to extract content directly
        if (completeResponse.length === 0 && chunkCount > 0) {
            console.warn("No content extracted from chunks despite receiving data. Attempting direct extraction...");
            // This is a fallback mechanism that might help in some cases
            return "Response could not be properly processed. Please check the browser console for details.";
        }
        
        return completeResponse;
    } catch (error) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            console.error("Streaming request aborted (timeout or manual cancellation)");
            // Try to cancel the reader if it exists
            try {
                if (reader) {
                    await reader.cancel("Request aborted");
                    console.log("Reader cancelled due to abort");
                }
            } catch (cancelError) {
                console.error("Error cancelling reader:", cancelError);
            }
            throw new Error("Request timed out after 180 seconds. The model is taking too long to respond.");
        }
        
        console.error("Error reading stream:", error);
        throw error;
    }
}

// Helper function to process a stream chunk and extract content
function processStreamChunk(text, chunkCount, currentResponse, onChunk) {
    let processedResponse = currentResponse;
    let remainingText = "";
    
    try {
        // Split by newlines and process each line
        const lines = text.split('\n');
        
        // Process complete lines
        for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            
            console.log(`Processing line ${i+1}/${lines.length} from chunk ${chunkCount}:`, line);
            
            try {
                const extractedContent = processStreamLine(line, chunkCount);
                if (extractedContent) {
                    processedResponse += extractedContent;
                    onChunk(extractedContent);
                }
            } catch (lineError) {
                console.warn(`Error processing line in chunk ${chunkCount}:`, lineError);
            }
        }
        
        // Keep the last line as it might be incomplete
        remainingText = lines[lines.length - 1];
        if (remainingText) {
            console.log(`Keeping remaining text for next chunk: "${remainingText.substring(0, 50)}${remainingText.length > 50 ? '...' : ''}"`);
        }
        
    } catch (e) {
        console.error("Error in processStreamChunk:", e);
    }
    
    return { processedText: processedResponse, remainingText };
}

// Helper function to process a single line from the stream
function processStreamLine(line, chunkCount) {
    // Prioritize data lines
    if (line.startsWith('data: ')) {
        const jsonData = line.substring(6).trim();
        
        // Check for the done marker
        if (jsonData === '[DONE]') {
            console.log(`Received [DONE] marker in chunk ${chunkCount}`);
            return null;
        }
        
        // Skip empty data
        if (!jsonData) {
            // console.log(`Empty JSON data in line from chunk ${chunkCount}`); // Reduced logging
            return null;
        }
        
        try {
            return extractContentFromJSON(jsonData, chunkCount);
        } catch (e) {
            console.warn(`Error extracting content from JSON in chunk ${chunkCount}:`, e);
            return null;
        }
    }

    // Filter out SSE comments (lines starting with ':') or specific processing messages
    if (line.startsWith(':') || line.includes("OPENROUTER PROCESSING")) {
        // console.log(`Filtering out comment/processing message in chunk ${chunkCount}:`, line); // Reduced logging
        return null;
    }
    
    // Fallback for other non-empty, non-data, non-comment lines
    if (line.trim()) {
        // console.log(`Fallback: Non-data, non-comment line in chunk ${chunkCount}:`, line); // Reduced logging
        // Try to extract content directly if possible
        return extractContentFromText(line, chunkCount);
    }
    
    return null;
}

// Helper function to extract content from JSON data
function extractContentFromJSON(jsonData, chunkCount) {
    try {
        const parsed = JSON.parse(jsonData);
        console.log(`Parsed JSON from chunk ${chunkCount}:`, JSON.stringify(parsed, null, 2));
        
        // Check for content in various locations
        if (parsed.choices && parsed.choices[0]) {
            // Standard OpenAI format with delta
            if (parsed.choices[0].delta && parsed.choices[0].delta.content) {
                const content = parsed.choices[0].delta.content;
                console.log(`Content from delta (chunk ${chunkCount}):`, content);
                return content;
            }
            
            // Complete message format
            if (parsed.choices[0].message && parsed.choices[0].message.content) {
                const content = parsed.choices[0].message.content;
                console.log(`Content from message (chunk ${chunkCount}):`, content);
                return content;
            }
            
            // Text-only format (some APIs)
            if (parsed.choices[0].text) {
                const content = parsed.choices[0].text;
                console.log(`Content from text (chunk ${chunkCount}):`, content);
                return content;
            }
            
            // Check for content directly in the choice object (rare but possible)
            if (typeof parsed.choices[0].content === 'string') {
                const content = parsed.choices[0].content;
                console.log(`Content directly from choice (chunk ${chunkCount}):`, content);
                return content;
            }
            
            console.log(`No extractable content in choices (chunk ${chunkCount}):`, JSON.stringify(parsed.choices[0]));
        } else {
            // Check for content at the root level (non-standard)
            if (typeof parsed.content === 'string') {
                const content = parsed.content;
                console.log(`Content from root level (chunk ${chunkCount}):`, content);
                return content;
            }
            
            console.log(`No choices found in parsed JSON (chunk ${chunkCount}):`, JSON.stringify(parsed));
        }
    } catch (e) {
        console.warn(`Error parsing JSON data in chunk ${chunkCount}:`, e, "JSON Data:", jsonData);
        throw e;
    }
    
    return null;
}

// Helper function to try extracting content from plain text
function extractContentFromText(text, chunkCount) {
    // This is a fallback for non-standard formats
    // Try to find content in various formats
    
    // Try to extract JSON-like content
    const jsonMatch = text.match(/{.*}/);
    if (jsonMatch) {
        try {
            const jsonContent = jsonMatch[0];
            return extractContentFromJSON(jsonContent, chunkCount);
        } catch (e) {
            // Ignore JSON extraction errors in fallback
        }
    }
    
    // If the text looks like it might be direct content (not JSON/SSE formatting)
    // This is very speculative and might need adjustment
    if (!text.includes('data:') && !text.startsWith('{') && text.length > 0) {
        console.log(`Treating as direct content (chunk ${chunkCount}):`, text);
        return text;
    }
    
    return null;
}

// Export functions for use in other scripts
window.OpenRouterAPI = {
    models: OPENROUTER_MODELS,
    setSelectedModel: setSelectedModel,
    getSelectedModel: getSelectedModel,
    sendMessage: sendMessageToOpenRouter, // Already updated to accept abortController
    // Helper function to create a streaming message handler
    createStreamHandler: function(elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error(`Element with ID ${elementId} not found`);
            return null;
        }
        
        // Clear the element initially
        element.textContent = '';
        
        // Return the handler function
        return function(chunk) {
            element.textContent += chunk;
            // Auto-scroll to bottom
            element.scrollTop = element.scrollHeight;
        };
    }
};
