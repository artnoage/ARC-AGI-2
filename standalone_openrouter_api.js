/**
 * Standalone OpenRouter API Integration for Testing
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
 * @param {function} onStreamChunk - Callback function for streaming chunks (optional)
 * @returns {Promise} Promise that resolves with the AI response
 */
async function sendMessageToOpenRouter(apiKey, userMessage, taskContext = '', temperature = 0.7, conversationHistory = [], useStreaming = false, onStreamChunk = null) {
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
                     
                     (taskContext ? taskContext : "")
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

    // Request options
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
        if (useStreaming && typeof onStreamChunk === 'function') {
            return await handleStreamingResponse(requestOptions, onStreamChunk);
        } else {
            // Non-streaming approach with extended timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 180000); // 180 second timeout (3 minutes)
            
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
            console.error("Request timed out after 180 seconds (3 minutes)");
            throw new Error("Request timed out after 3 minutes. The model is taking too long to respond.");
        }
        console.error("Error sending message to OpenRouter:", error);
        throw error;
    }
}

/**
 * Handle streaming response from OpenRouter API
 * @param {Object} requestOptions - Fetch request options
 * @param {Function} onChunk - Callback function for each chunk
 * @returns {Promise<string>} Complete response text
 */
async function handleStreamingResponse(requestOptions, onChunk) {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", requestOptions);
    
    if (!response.ok) {
        const errorText = await response.text();
        console.error("OpenRouter API streaming error:", errorText);
        throw new Error(`OpenRouter API error: ${response.status} ${response.statusText}`);
    }
    
    if (!response.body) {
        throw new Error("ReadableStream not supported in this browser.");
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let completeResponse = "";
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n').filter(line => line.trim() !== '');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    if (data === '[DONE]') continue;
                    
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.choices && parsed.choices[0] && parsed.choices[0].delta && parsed.choices[0].delta.content) {
                            const content = parsed.choices[0].delta.content;
                            completeResponse += content;
                            onChunk(content);
                        }
                    } catch (e) {
                        console.warn("Error parsing stream chunk:", e);
                    }
                }
            }
        }
    } catch (error) {
        console.error("Error reading stream:", error);
        throw error;
    }
    
    return completeResponse;
}

// Export functions for use in other scripts
window.OpenRouterAPI = {
    models: OPENROUTER_MODELS,
    setSelectedModel: setSelectedModel,
    getSelectedModel: getSelectedModel,
    sendMessage: sendMessageToOpenRouter,
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
