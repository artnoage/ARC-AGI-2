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
        id: 'google/gemini-2.5-pro-preview-03-25',
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
 * @returns {Promise} Promise that resolves with the AI response
 */
async function sendMessageToOpenRouter(apiKey, userMessage, taskContext) {
    if (!apiKey) {
        throw new Error("API key is required");
    }

    const model = OPENROUTER_MODELS[SELECTED_MODEL];
    if (!model) {
        throw new Error("Invalid model selected");
    }

    const messages = [
        {
            role: "system",
            content: "You are an AI assistant helping with Abstraction and Reasoning Corpus (ARC) tasks. " +
                     "Your goal is to help the user understand patterns, transformations, and reasoning strategies " +
                     "for solving ARC tasks. Be clear, helpful, and provide step-by-step explanations when appropriate. " +
                     "Here is the context for the current task: " + taskContext
        },
        {
            role: "user",
            content: userMessage
        }
    ];

    try {
        console.log(`Sending message to OpenRouter using model: ${model.id}`);
        
        const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiKey}`
            },
            body: JSON.stringify({
                model: model.id,
                messages: messages,
                temperature: 0.7,
                stream: false
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("OpenRouter API error:", errorText);
            throw new Error(`OpenRouter API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log("OpenRouter response:", data);
        
        if (data.choices && data.choices.length > 0 && data.choices[0].message) {
            return data.choices[0].message.content;
        } else {
            throw new Error("Invalid response format from OpenRouter API");
        }
    } catch (error) {
        console.error("Error sending message to OpenRouter:", error);
        throw error;
    }
}

// Export functions for use in other scripts
window.OpenRouterAPI = {
    models: OPENROUTER_MODELS,
    setSelectedModel: setSelectedModel,
    getSelectedModel: getSelectedModel,
    sendMessage: sendMessageToOpenRouter
};
