// Global variables
var USERNAME = "Anonymous";
var CURRENT_TASK_ID = null;
var CURRENT_VERSION_INDEX = 0; // Track the current version index
var LOADED_TASK_LIST = [];
var UNIQUE_TASK_IDS = [];
var TASK_VERSIONS_MAP = {};
var ORIGINAL_TASK_DATA = null; // Original task data
var DISPLAYED_TASK_DATA = null; // Potentially transformed task data
var socket = null;
var API_KEY = null;
var CHAT_MEMORY = {}; // Memory storage for chat messages
var TEMPERATURE = 0.7; // Default temperature value for API calls
var USE_STREAMING = true; // Default to use streaming for responses
var ACTIVE_STREAM_READER = null; // Track active stream reader for cancellation
var ACTIVE_STREAM_CONTROLLER = null; // Track active AbortController for cancellation

// Initialize the interface
$(document).ready(function() {
    // Initialize WebSocket connection
    connectWebSocket();
    
    // Initialize chat memory
    initChatMemory();
    
    // Version navigation buttons
    $('#prev_version_btn').click(function() {
        previousVersion();
    });
    
    $('#next_version_btn').click(function() {
        nextVersion();
    });
    
    // Stop streaming button
    $('#stop_streaming_btn').click(function() {
        if (ACTIVE_STREAM_CONTROLLER) {
            console.log("Manually cancelling active streaming request");
            ACTIVE_STREAM_CONTROLLER.abort();
            ACTIVE_STREAM_CONTROLLER = null;
            
            // Add a system message to indicate the streaming was cancelled
            addSystemMessage("Streaming response cancelled by user.");
            
            // Re-enable the send button
            $('#send_message_btn').prop('disabled', false);
            
            // Hide the stop button
            $(this).hide();
        }
    });

    // --- Username Handling (including Cookie) ---
    const savedUsername = getCookie('username');
    if (savedUsername) {
        USERNAME = savedUsername;
        console.log("Username loaded from cookie:", USERNAME);
        $('#current_user').text(`User: ${USERNAME}`); // Update displayed username
    } else {
        // If no username cookie, redirect to main welcome page
        window.location.href = '/arc2/';
        return; // Stop further execution
    }
    // --- End Username Handling ---

    // Check for saved API key
    const savedApiKey = localStorage.getItem('openrouter_api_key');
    if (savedApiKey) {
        $('#openrouter_key').val(savedApiKey);
        API_KEY = savedApiKey;
        $('#api_status').text("API key loaded from storage");
        console.log("API key loaded from storage");
    }

    // Show discussion interface (it's no longer hidden by default in HTML)
    $('#discussion_interface').show();

    // Load dataset automatically
    loadDataset();

    // Add welcome message
    addSystemMessage("Welcome to the ARC AI Discussion Interface. Select a task to discuss or ask general questions about ARC tasks.");


    // Logout button
    $('#logout_btn').click(function() {
        logoutUser();
    });

    // Save API key button
    $('#save_key_btn').click(function() {
        const apiKey = $('#openrouter_key').val().trim();
        if (apiKey) {
            localStorage.setItem('openrouter_api_key', apiKey);
            API_KEY = apiKey;
            $('#api_status').text("API key saved successfully");
            console.log("API key saved to local storage");
        } else {
            $('#api_status').text("Please enter a valid API key");
        }
    });
    
    // Model selector change event
    $('#model_selector').change(function() {
        const selectedModel = $(this).val();
        if (OpenRouterAPI.setSelectedModel(selectedModel)) {
            localStorage.setItem('selected_model', selectedModel);
            console.log(`Model changed to: ${OpenRouterAPI.getSelectedModel().name}`);
        }
    });
    
    // Load saved model selection
    const savedModel = localStorage.getItem('selected_model');
    if (savedModel && OpenRouterAPI.models[savedModel]) {
        $('#model_selector').val(savedModel);
        OpenRouterAPI.setSelectedModel(savedModel);
    }
    
    // Temperature slider event
    $('#temperature_slider').on('input', function() {
        const value = parseFloat($(this).val());
        TEMPERATURE = value;
        $('#temperature_value').text(value.toFixed(1));
        localStorage.setItem('temperature_value', value);
    });
    
    // Load saved temperature
    const savedTemperature = localStorage.getItem('temperature_value');
    if (savedTemperature !== null) {
        const tempValue = parseFloat(savedTemperature);
        TEMPERATURE = tempValue;
        $('#temperature_slider').val(tempValue);
        $('#temperature_value').text(tempValue.toFixed(1));
    }
    
    // Streaming toggle event
    $('#streaming_toggle').change(function() {
        USE_STREAMING = $(this).is(':checked');
        $('#streaming_status').text(USE_STREAMING ? 'Enabled' : 'Disabled');
        localStorage.setItem('use_streaming', USE_STREAMING ? 'true' : 'false');
        console.log(`Streaming ${USE_STREAMING ? 'enabled' : 'disabled'}`);
    });
    
    // Load saved streaming preference
    const savedStreaming = localStorage.getItem('use_streaming');
    if (savedStreaming !== null) {
        USE_STREAMING = savedStreaming === 'true';
        $('#streaming_toggle').prop('checked', USE_STREAMING);
        $('#streaming_status').text(USE_STREAMING ? 'Enabled' : 'Disabled');
    }

    // Task Data Source Selector
    $('#task_data_source_select').change(function() {
        const selectedDataSource = $(this).val();
        localStorage.setItem('task_data_source_select', selectedDataSource);
        console.log(`Task data source changed to: ${selectedDataSource}`);
    });

    // Load saved task data source selection
    const savedDataSource = localStorage.getItem('task_data_source_select');
    if (savedDataSource) {
        $('#task_data_source_select').val(savedDataSource);
    }

    // Send message button
    $('#send_message_btn').click(function() {
        if (!$(this).prop('disabled')) {
            sendUserMessage();
        }
    });

    // Send message on Enter (but allow Shift+Enter for new lines)
    $('#chat_input').keydown(function(event) {
        if (event.keyCode === 13 && !event.shiftKey) {
            event.preventDefault();
            sendUserMessage();
        }
    });

    // Task navigation buttons in the navigation panel
    $('#navigation_panel #random_task_btn').click(function() {
        randomTask();
    });

    $('#navigation_panel #prev_task_btn').click(function() {
        previousTask();
    });

    $('#navigation_panel #next_task_btn').click(function() {
        nextTask();
    });

    $('#navigation_panel #goto_task_btn').click(function() {
        gotoTaskById();
    });

    // Enter key for task ID input in the navigation panel
    $('#navigation_panel #task_id_input').keydown(function(event) {
        if (event.keyCode === 13) {
            gotoTaskById();
        }
    });
    
    // Go to task by number button in the navigation panel
    $('#navigation_panel #goto_task_number_btn').click(function() {
        gotoTaskByNumber();
    });
    
    // Enter key for task number input in the navigation panel
    $('#navigation_panel #task_number_input').keydown(function(event) {
        if (event.keyCode === 13) {
            gotoTaskByNumber();
        }
    });
    
    // Clear history button
    $('#clear_history_btn').click(function() {
        if (CURRENT_TASK_ID) {
            if (confirm(`Are you sure you want to clear the conversation history for task ${CURRENT_TASK_ID}?`)) {
                clearTaskMemory(CURRENT_TASK_ID);
                // Refresh the chat display
                $('#chat_messages').empty();
                addSystemMessage(`Conversation history cleared for task ${CURRENT_TASK_ID}.`);
            }
        } else {
            addSystemMessage("No task selected. Please select a task first.");
        }
    });
    
    // Execute code button
    $('#execute_code_btn').click(function() {
        executeCode();
    });
    
    // Visualize input button
    $('#visualize_input_btn').click(function() {
        visualizeInputGrid();
    });
    
    // Visualize output button
    $('#visualize_output_btn').click(function() {
        visualizeOutputGrid();
    });
    
    // Submit trace button
    $('#submit_trace_btn').click(function() {
        submitReasoningTrace();
    });

    // Copy system prompt button
    $('#copy_system_prompt_btn').click(function() {
        copySystemPromptToClipboard();
    });
});

// Function to get the current dynamic task context string
function getCurrentDynamicTaskContext() {
    let contextStr = "";
    const selectedDataSource = $('#task_data_source_select').val();

    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const originalTaskData = TASK_VERSIONS_MAP[CURRENT_TASK_ID].find(v => v.version === 0) || TASK_VERSIONS_MAP[CURRENT_TASK_ID][0];
        const currentVariationData = TASK_VERSIONS_MAP[CURRENT_TASK_ID][CURRENT_VERSION_INDEX];

        contextStr = `Current task ID: ${CURRENT_TASK_ID}\n`;
        let trainExamplesForContext = [];
        let testExamplesForContext = [];

        if (selectedDataSource === "original") {
            contextStr += `Data source: Original task (Version ${originalTaskData.version || 0}).\n`;
            trainExamplesForContext = originalTaskData.train ? originalTaskData.train.slice() : [];
            if (originalTaskData.test) {
                testExamplesForContext = originalTaskData.test.map(t => ({ input: t.input }));
            }
        } else if (selectedDataSource === "variation") {
            contextStr += `Data source: Current variation (Version ${currentVariationData.version || 0}).\n`;
            trainExamplesForContext = currentVariationData.train ? currentVariationData.train.slice() : [];
            if (currentVariationData.test) {
                testExamplesForContext = currentVariationData.test.map(t => ({ input: t.input }));
            }
        } else { // selectedDataSource === "both"
            contextStr += `Data source: Combined (Original Task Version ${originalTaskData.version || 0} + Current Variation Version ${currentVariationData.version || 0}).\n`;
            trainExamplesForContext = originalTaskData.train ? originalTaskData.train.slice() : [];
            // Only add variation if it's different from original and has train examples
            if (currentVariationData.task_id !== originalTaskData.task_id || currentVariationData.version !== originalTaskData.version) {
                if (currentVariationData.train) {
                     currentVariationData.train.forEach(varTrainEx => {
                        trainExamplesForContext.push(varTrainEx);
                    });
                }
            }
            // Test examples from the current variation (or original if variation has none)
            if (currentVariationData.test && currentVariationData.test.length > 0) {
                testExamplesForContext = currentVariationData.test.map(t => ({ input: t.input }));
            } else if (originalTaskData.test) {
                 testExamplesForContext = originalTaskData.test.map(t => ({ input: t.input }));
            }
        }

        if (trainExamplesForContext.length > 0) {
            contextStr += `The task has ${trainExamplesForContext.length} training examples and ${testExamplesForContext.length} test examples.\n\n`;
            contextStr += "TRAINING EXAMPLES:\n";
            for (let i = 0; i < trainExamplesForContext.length; i++) {
                const example = trainExamplesForContext[i];
                contextStr += `Example ${i+1}:\n`;
                contextStr += "Input: " + JSON.stringify(example.input) + "\n";
                contextStr += "Output: " + JSON.stringify(example.output) + "\n\n";
            }
            if (testExamplesForContext.length > 0) {
                contextStr += "TEST INPUTS (only inputs are provided to the AI):\n";
                for (let i = 0; i < testExamplesForContext.length; i++) {
                    const testInput = testExamplesForContext[i].input; 
                    contextStr += `Test ${i+1} input grid: ` + JSON.stringify(testInput) + "\n\n";
                }
            }
        } else {
             contextStr += `The selected task/variation has no training examples.\n`;
             if (testExamplesForContext.length > 0) {
                contextStr += "TEST INPUTS (only inputs are provided to the AI):\n";
                for (let i = 0; i < testExamplesForContext.length; i++) {
                    const testInput = testExamplesForContext[i].input;
                    contextStr += `Test ${i+1} input grid: ` + JSON.stringify(testInput) + "\n\n";
                }
            }
        }
    } else {
        contextStr = "No specific task is currently selected.\n";
    }
    return contextStr;
}

// Function to copy the full system prompt to clipboard
function copySystemPromptToClipboard() {
    const basePromptPart1 = "You are an AI assistant helping with Abstraction and Reasoning Corpus (ARC) tasks... " +
                          "Your goal is to help the user understand patterns, transformations, and reasoning strategies " +
                          "for solving ARC tasks. Be clear, helpful, and provide step-by-step explanations when appropriate. ";
    
    const basePromptPart2 = "\n---\n" +
                          "In case the user asks for code generation I provide some guidlines:"+ // Note: "guidlines" typo from original
                          "\n"+
                          "**Guidliness for Code Generation:**\n\n" + // Note: "Guidliness" typo from original
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
                          "---";

    const dynamicTaskContext = getCurrentDynamicTaskContext();
    const fullSystemPrompt = basePromptPart1 + dynamicTaskContext + basePromptPart2;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullSystemPrompt).then(function() {
            addSystemMessage('System prompt copied to clipboard!');
            // Temporarily change button text for feedback
            const originalButtonText = $('#copy_system_prompt_btn').text();
            $('#copy_system_prompt_btn').text('Copied!');
            setTimeout(() => {
                $('#copy_system_prompt_btn').text(originalButtonText);
            }, 2000);
        }, function(err) {
            addSystemMessage('Failed to copy system prompt. See console for details.');
            console.error('Failed to copy system prompt: ', err);
        });
    } else {
        addSystemMessage('Clipboard API not available. This is likely due to an insecure connection (HTTP). Please serve the page over HTTPS or from localhost. The prompt has been logged to the console for manual copying.');
        console.warn('navigator.clipboard.writeText is not available. System Prompt for manual copy:');
        console.log(fullSystemPrompt);
    }
}

// WebSocket connection
function connectWebSocket() {
    console.log("Attempting to connect WebSocket...");
    if (socket && socket.connected) {
        console.log("WebSocket already connected.");
        return;
    }
    
    // Connect to Socket.IO - Use the default path '/socket.io/'
    // Assumes a reverse proxy (like Nginx) handles routing if accessed via a prefix like /arc2/
    const socketPath = '/socket.io/';
    console.log(`Using Socket.IO path: ${socketPath}`);
    socket = io({ path: socketPath, transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
        console.log('WebSocket connected successfully. SID:', socket.id);
    });

    socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason);
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
    });
}

// Load dataset
function loadDataset() {
    const filename = `dataset.json`;
    const serverRoute = `/arc2/static/${filename}`;

    addSystemMessage(`Loading dataset...`);
    console.log(`Fetching data from ${serverRoute}...`);

    $.ajax({
        url: serverRoute,
        dataType: 'json',
        success: function(data) {
            console.log(`Successfully fetched data from ${filename}. Processing...`);
            
            if (!Array.isArray(data)) {
                console.error(`Data from ${serverRoute} is not an array.`);
                addSystemMessage(`Error: Dataset file does not contain a valid JSON list.`);
                return;
            }
            
            if (data.length === 0) {
                console.warn(`Data from ${serverRoute} is an empty array.`);
                addSystemMessage(`Warning: Dataset is empty.`);
                return;
            }

            console.log(`Dataset has ${data.length} entries. Building version map...`);
            LOADED_TASK_LIST = data;

            // Build the TASK_VERSIONS_MAP and UNIQUE_TASK_IDS
            TASK_VERSIONS_MAP = {};
            UNIQUE_TASK_IDS = [];
            const idSet = new Set();

            LOADED_TASK_LIST.forEach((task, index) => {
                if (!task || typeof task !== 'object') {
                    console.warn(`Skipping invalid entry at index ${index}.`);
                    return;
                }
                
                const taskId = task.task_id;
                const taskVersion = task.version !== undefined ? parseInt(task.version, 10) : 0;

                if (!taskId) {
                    console.warn(`Task entry at index ${index} in ${filename} is missing a 'task_id' field. Skipping.`); // Updated message
                    return;
                }
                
                if (isNaN(taskVersion) || taskVersion < 0) {
                    console.warn(`Task entry '${taskId}' at index ${index} has invalid version '${task.version}'. Skipping.`);
                    return;
                }
                
                task.version = taskVersion;

                // Add to TASK_VERSIONS_MAP
                if (!TASK_VERSIONS_MAP[taskId]) {
                    TASK_VERSIONS_MAP[taskId] = [];
                }
                TASK_VERSIONS_MAP[taskId].push(task);

                // Add to UNIQUE_TASK_IDS if new
                if (!idSet.has(taskId)) {
                    idSet.add(taskId);
                    UNIQUE_TASK_IDS.push(taskId);
                }
            });

            // Sort versions within each task ID entry
            for (const taskId in TASK_VERSIONS_MAP) {
                TASK_VERSIONS_MAP[taskId].sort((a, b) => a.version - b.version);
            }

            console.log(`Version map built. Unique Task IDs: ${UNIQUE_TASK_IDS.length}.`);
            addSystemMessage(`Dataset loaded with ${UNIQUE_TASK_IDS.length} unique tasks.`);

            // Load the first task
            if (UNIQUE_TASK_IDS.length > 0) {
                const firstTaskId = UNIQUE_TASK_IDS[0];
                loadTask(firstTaskId, 0);
            }
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error(`Failed to load data ${serverRoute}. Status: ${textStatus}, Error: ${errorThrown}`, jqXHR);
            addSystemMessage(`Failed to load dataset. Check server logs.`);
        }
    });
}

// Load a specific task
function loadTask(taskId, versionIndex = 0) {
    // Cancel any active streaming requests
    if (ACTIVE_STREAM_CONTROLLER) {
        console.log("Cancelling active streaming request due to task change");
        ACTIVE_STREAM_CONTROLLER.abort();
        ACTIVE_STREAM_CONTROLLER = null;
        
        // Add a system message to indicate the streaming was cancelled due to task change
        addSystemMessage("Streaming response cancelled due to task change.");
        
        // Re-enable the send button
        $('#send_message_btn').prop('disabled', false);
        
        // Hide the stop button if it's visible
        $('#stop_streaming_btn').hide();
    }
    
    if (!TASK_VERSIONS_MAP[taskId] || versionIndex < 0 || versionIndex >= TASK_VERSIONS_MAP[taskId].length) {
        addSystemMessage(`Error: Task ID '${taskId}' version index ${versionIndex} not found.`);
        return;
    }
    
    // Add a system message if we're changing tasks during an active conversation
    if (CURRENT_TASK_ID && CURRENT_TASK_ID !== taskId) {
        addSystemMessage(`Navigated from task ${CURRENT_TASK_ID} to task ${taskId}`);
    }

    const taskObject = TASK_VERSIONS_MAP[taskId][versionIndex];
    CURRENT_TASK_ID = taskId;
    CURRENT_VERSION_INDEX = versionIndex;
    ORIGINAL_TASK_DATA = JSON.parse(JSON.stringify(taskObject)); // Store a deep copy
    DISPLAYED_TASK_DATA = ORIGINAL_TASK_DATA; // Initially, displayed data is the same as original

    try {
        // Clear previous task preview
        $('#task_preview').empty();

        // Load training pairs
        const trainPairs = taskObject.train || [];
        for (let i = 0; i < trainPairs.length; i++) {
            const pair = trainPairs[i];
            if (pair && pair.input && pair.output) {
                const inputGrid = convertSerializedGridToGridObject(pair.input);
                const outputGrid = convertSerializedGridToGridObject(pair.output);
                fillPairPreview(i, inputGrid, outputGrid);
            }
        }

        // Update task navigation
        updateTaskNavigation();
        
        // Update version navigation
        updateVersionNavigation();
        
        // Update task name in header
        const uniqueIndex = UNIQUE_TASK_IDS.indexOf(taskId);
        if (uniqueIndex !== -1) {
            const versionText = taskObject.version !== undefined ? ` (Version ${taskObject.version})` : '';
            $('#current_task_name').text(`Task #${uniqueIndex + 1} (ID: ${taskId})${versionText}`);
        } else {
            const versionText = taskObject.version !== undefined ? ` (Version ${taskObject.version})` : '';
            $('#current_task_name').text(`Task ID: ${taskId}${versionText}`);
        }
        
        // Load chat history for this task
        displayChatHistory();
        
        // Populate the input grid field with the first test input if available
        const testPairs = taskObject.test || [];
        if (testPairs.length > 0 && testPairs[0].input) {
            $('#grid_input').val(JSON.stringify(testPairs[0].input, null, 2));
        }

    } catch (e) {
        console.error(`Error processing task ${taskId}:`, e);
        addSystemMessage(`Error loading task ${taskId}: ${e.message}`);
    }
}

// Update version navigation UI
function updateVersionNavigation() {
    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const versions = TASK_VERSIONS_MAP[CURRENT_TASK_ID];
        const totalVersions = versions.length;
        
        // Always show version navigation, even for single versions
        $('#version_display').text(`Ver ${CURRENT_VERSION_INDEX + 1}/${totalVersions}`);
        
        // Enable/disable navigation buttons based on current index
        $('#prev_version_btn').prop('disabled', CURRENT_VERSION_INDEX === 0);
        $('#next_version_btn').prop('disabled', CURRENT_VERSION_INDEX === totalVersions - 1);
    } else {
        // If no task is loaded, show placeholder
        $('#version_display').text(`Ver -/-`);
        $('#prev_version_btn').prop('disabled', true);
        $('#next_version_btn').prop('disabled', true);
    }
}

// Version navigation functions
function previousVersion() {
    if (CURRENT_TASK_ID && CURRENT_VERSION_INDEX > 0) {
        loadTask(CURRENT_TASK_ID, CURRENT_VERSION_INDEX - 1);
        addSystemMessage(`Navigated to previous version of task ${CURRENT_TASK_ID}`);
    }
}

function nextVersion() {
    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const totalVersions = TASK_VERSIONS_MAP[CURRENT_TASK_ID].length;
        if (CURRENT_VERSION_INDEX < totalVersions - 1) {
            loadTask(CURRENT_TASK_ID, CURRENT_VERSION_INDEX + 1);
            addSystemMessage(`Navigated to next version of task ${CURRENT_TASK_ID}`);
        }
    }
}

// Fill a pair preview in the task area
function fillPairPreview(pairId, inputGrid, outputGrid) {
    var pairSlot = $('<div id="pair_preview_' + pairId + '" class="pair_preview"></div>');
    var jqInputGrid = $('<div class="input_preview"></div>');
    var jqOutputGrid = $('<div class="output_preview"></div>');
    
    pairSlot.append(jqInputGrid);
    pairSlot.append(jqOutputGrid);
    $('#task_preview').append(pairSlot);

    // Fill the grids
    fillJqGridWithData(jqInputGrid, inputGrid);
    fillJqGridWithData(jqOutputGrid, outputGrid);

    // Define fixed, smaller constraints for the preview grids
    const previewConstraint = 150;
    fitCellsToContainer(jqInputGrid, inputGrid.height, inputGrid.width, previewConstraint, previewConstraint);
    fitCellsToContainer(jqOutputGrid, outputGrid.height, outputGrid.width, previewConstraint, previewConstraint);
}

// Update task navigation UI
function updateTaskNavigation() {
    if (UNIQUE_TASK_IDS.length > 0 && CURRENT_TASK_ID) {
        const uniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        if (uniqueIndex !== -1) {
            // Update task index display
            $('#task_index_display span').text(`Task ${uniqueIndex + 1}/${UNIQUE_TASK_IDS.length}`);
            
            // Update navigation panel buttons
            const isFirst = uniqueIndex === 0;
            const isLast = uniqueIndex === UNIQUE_TASK_IDS.length - 1;
            
            // Navigation panel buttons
            $('#navigation_panel #prev_task_btn').prop('disabled', isFirst);
            $('#navigation_panel #next_task_btn').prop('disabled', isLast);
        }
    } else {
        // No tasks loaded
        $('#task_index_display span').text(`No tasks loaded`);
        
        // Disable navigation buttons
        $('#navigation_panel #prev_task_btn').prop('disabled', true);
        $('#navigation_panel #next_task_btn').prop('disabled', true);
    }
}

// Task navigation functions
function randomTask() {
    if (UNIQUE_TASK_IDS.length > 0) {
        let currentUniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        let randomUniqueIndex = Math.floor(Math.random() * UNIQUE_TASK_IDS.length);
        
        // Avoid picking the same task ID consecutively if possible
        if (UNIQUE_TASK_IDS.length > 1 && randomUniqueIndex === currentUniqueIndex) {
            randomUniqueIndex = (randomUniqueIndex + 1) % UNIQUE_TASK_IDS.length;
        }
        
        const newTaskId = UNIQUE_TASK_IDS[randomUniqueIndex];
        loadTask(newTaskId, 0);
    } else {
        addSystemMessage("No tasks available to select randomly.");
    }
}

function previousTask() {
    if (CURRENT_TASK_ID && UNIQUE_TASK_IDS.length > 0) {
        const currentUniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        if (currentUniqueIndex > 0) {
            const newTaskId = UNIQUE_TASK_IDS[currentUniqueIndex - 1];
            loadTask(newTaskId, 0);
        }
    }
}

function nextTask() {
    if (CURRENT_TASK_ID && UNIQUE_TASK_IDS.length > 0) {
        const currentUniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        if (currentUniqueIndex < UNIQUE_TASK_IDS.length - 1) {
            const newTaskId = UNIQUE_TASK_IDS[currentUniqueIndex + 1];
            loadTask(newTaskId, 0);
        }
    }
}

function gotoTaskById() {
    // Get task ID from the navigation panel input field
    const taskIdToFind = $('#navigation_panel #task_id_input').val().trim();
    if (!taskIdToFind) {
        addSystemMessage("Please enter a Task ID.");
        return;
    }

    if (TASK_VERSIONS_MAP.hasOwnProperty(taskIdToFind)) {
        loadTask(taskIdToFind, 0);
        // Clear input field
        $('#navigation_panel #task_id_input').val('');
    } else {
        addSystemMessage(`Task ID '${taskIdToFind}' not found.`);
    }
}

function gotoTaskByNumber() {
    // Get task number from the navigation panel input field
    const taskNumberStr = $('#navigation_panel #task_number_input').val().trim();
    if (!taskNumberStr) {
        addSystemMessage("Please enter a Task Number.");
        return;
    }

    const taskNumber = parseInt(taskNumberStr, 10);

    if (isNaN(taskNumber)) {
        addSystemMessage("Invalid Task Number entered.");
        return;
    }

    if (!UNIQUE_TASK_IDS || UNIQUE_TASK_IDS.length === 0) {
        addSystemMessage("No tasks loaded to navigate by number.");
        return;
    }

    const totalTasks = UNIQUE_TASK_IDS.length;
    if (taskNumber < 1 || taskNumber > totalTasks) {
        addSystemMessage(`Task Number must be between 1 and ${totalTasks}.`);
        return;
    }

    const taskIndex = taskNumber - 1; // Convert 1-based input to 0-based index
    const taskIdToGo = UNIQUE_TASK_IDS[taskIndex];

    if (taskIdToGo === CURRENT_TASK_ID) {
        addSystemMessage(`Already viewing Task #${taskNumber} (ID: ${taskIdToGo}).`);
    } else {
        loadTask(taskIdToGo, 0); // Load first version
        addSystemMessage(`Navigated to Task #${taskNumber} (ID: ${taskIdToGo})`);
        // Clear input field
        $('#navigation_panel #task_number_input').val('');
    }
}

// Chat functions
function sendUserMessage() {
    const messageText = $('#chat_input').val().trim();
    if (!messageText) return;
    
    // Disable the send button to prevent multiple submissions
    $('#send_message_btn').prop('disabled', true);

    // Add user message to chat
    addUserMessage(messageText);
    
    // Clear input
    $('#chat_input').val('');

    // Check if API key is set
    if (!API_KEY) {
        addSystemMessage("Please enter your OpenRouter API key in the settings below to enable AI responses.");
        return;
    }

    // Prepare context about the current task based on selected data source
    const selectedDataSource = $('#task_data_source_select').val();
    let taskContext = "";

    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const originalTaskData = TASK_VERSIONS_MAP[CURRENT_TASK_ID][0];
        const currentVariationData = TASK_VERSIONS_MAP[CURRENT_TASK_ID][CURRENT_VERSION_INDEX];

        taskContext = `Current task ID: ${CURRENT_TASK_ID}\n`;
        let trainExamplesForContext = [];
        let testExamplesForContext = []; // Will hold only inputs

        if (selectedDataSource === "original") {
            taskContext += `Data source: Original task (Version ${originalTaskData.version}).\n`;
            trainExamplesForContext = originalTaskData.train ? originalTaskData.train.slice() : [];
            if (originalTaskData.test) {
                testExamplesForContext = originalTaskData.test.map(t => ({ input: t.input }));
            }
        } else if (selectedDataSource === "variation") {
            taskContext += `Data source: Current variation (Version ${currentVariationData.version}).\n`;
            trainExamplesForContext = currentVariationData.train ? currentVariationData.train.slice() : [];
            if (currentVariationData.test) {
                testExamplesForContext = currentVariationData.test.map(t => ({ input: t.input }));
            }
        } else { // selectedDataSource === "both"
            taskContext += `Data source: Combined (Original Task Version ${originalTaskData.version} + Current Variation Version ${currentVariationData.version}).\n`;
            // Combine train examples
            trainExamplesForContext = originalTaskData.train ? originalTaskData.train.slice() : [];
            if (CURRENT_VERSION_INDEX > 0 && currentVariationData.train) { // Only add if current variation is not the original
                currentVariationData.train.forEach(varTrainEx => {
                    // Simple concatenation.
                    trainExamplesForContext.push(varTrainEx);
                });
            }
            // Test examples from the current variation
            if (currentVariationData.test) {
                testExamplesForContext = currentVariationData.test.map(t => ({ input: t.input }));
            }
        }

        if (trainExamplesForContext.length > 0) {
            taskContext += `The task has ${trainExamplesForContext.length} training examples and ${testExamplesForContext.length} test examples.\n\n`;
            
            taskContext += "TRAINING EXAMPLES:\n";
            for (let i = 0; i < trainExamplesForContext.length; i++) {
                const example = trainExamplesForContext[i];
                taskContext += `Example ${i+1}:\n`;
                taskContext += "Input: " + JSON.stringify(example.input) + "\n";
                taskContext += "Output: " + JSON.stringify(example.output) + "\n\n";
            }
            
            if (testExamplesForContext.length > 0) {
                taskContext += "TEST INPUTS:\n";
                for (let i = 0; i < testExamplesForContext.length; i++) {
                    const testInput = testExamplesForContext[i].input; 
                    taskContext += `Test ${i+1} input grid: ` + JSON.stringify(testInput) + "\n\n";
                }
            }
        } else {
             taskContext += `The selected task/variation has no training examples.\n`;
             if (testExamplesForContext.length > 0) {
                taskContext += "TEST INPUTS:\n";
                for (let i = 0; i < testExamplesForContext.length; i++) {
                    const testInput = testExamplesForContext[i].input;
                    taskContext += `Test ${i+1} input grid: ` + JSON.stringify(testInput) + "\n\n";
                }
            }
        }
    } else {
        taskContext = "No specific task is currently selected.\n";
    }

    // Show typing indicator
    addTypingIndicator();

    // Get the selected model info
    const modelInfo = OpenRouterAPI.getSelectedModel();
    console.log(`Using model: ${modelInfo.name} (${modelInfo.id})`);
    
    // If we have an API key, use the OpenRouter API
    if (API_KEY) {
        // Get conversation history for the current task
        let conversationHistory = [];
        if (CURRENT_TASK_ID) {
            const messages = getTaskMessages(CURRENT_TASK_ID);
            // Only include user and AI messages, not system messages
            conversationHistory = messages.filter(msg => msg.role === 'user' || msg.role === 'ai')
                .map(msg => ({
                    role: msg.role === 'ai' ? 'assistant' : 'user',
                    content: msg.content
                }));
            
            console.log(`Including ${conversationHistory.length} previous messages in conversation history`);
        }
        
        if (USE_STREAMING) {
            // Create a unique ID for the AI message
            const messageId = 'ai_msg_' + Date.now();
            
            // Add an empty AI message that will be filled by streaming
            const emptyMessageHtml = `
                <div class="ai_message" id="${messageId}">
                    <div class="message_sender">AI Assistant</div>
                    <div class="message_content"></div>
                </div>
            `;
            removeTypingIndicator();
            $('#chat_messages').append(emptyMessageHtml);
            scrollChatToBottom();
            
            // Create a streaming handler that will update the message content
            const streamHandler = function(chunk) {
                console.log(`--- streamHandler received chunk (discuss_interface.js) ---`);
                console.log("Raw chunk received by streamHandler:", chunk);
                console.log("Length:", chunk ? chunk.length : 'N/A');
                
                // Skip empty chunks or processing messages
                if (!chunk || !chunk.trim()) {
                    console.log("streamHandler: Skipping empty or null chunk.");
                    console.log(`--- streamHandler END ---`);
                    return;
                }
                
                // Filter out OpenRouter processing messages
                if (chunk.includes("OPENROUTER PROCESSING")) {
                    console.log("streamHandler: Filtering out OpenRouter processing message:", chunk);
                    console.log(`--- streamHandler END ---`);
                    return;
                }
                
                // Process the chunk to handle code blocks and newlines
                let processedChunk = escapeHtml(chunk);
                console.log("streamHandler: Chunk after escapeHtml:", processedChunk);
                
                // Get the current content
                const messageElement = $(`#${messageId} .message_content`);
                if (messageElement.length === 0) {
                    console.error("streamHandler: Message element not found for ID:", messageId);
                    console.log(`--- streamHandler END ---`);
                    return;
                }
                
                // Store the raw content in a data attribute for post-processing
                let currentRawContent = messageElement.attr('data-raw-content') || '';
                currentRawContent += chunk;
                messageElement.attr('data-raw-content', currentRawContent);
                
                // For streaming display, just append the escaped HTML with newlines converted to <br>
                // We'll do proper code block formatting after streaming is complete
                let displayContent = escapeHtml(chunk).replace(/\n/g, '<br>');
                messageElement.append(displayContent);
                
                scrollChatToBottom();
                console.log(`--- streamHandler END ---`);
            };
            
            // Use the OpenRouter API with streaming
            let fullResponse = '';
            
            // Create an AbortController for this request
            ACTIVE_STREAM_CONTROLLER = new AbortController();
            
            // Add a message to indicate which task this stream belongs to
            const currentTaskId = CURRENT_TASK_ID;
            
            // Show the stop button
            $('#stop_streaming_btn').show();
            
            console.log("Starting streaming request for task:", currentTaskId);
            
            try {
                OpenRouterAPI.sendMessage(API_KEY, messageText, taskContext, TEMPERATURE, conversationHistory, true,
                    ACTIVE_STREAM_CONTROLLER, // Pass the controller
                    function(chunk) {
                        // Only process the chunk if we're still on the same task
                        if (CURRENT_TASK_ID === currentTaskId) {
                            console.log("Received chunk for task:", currentTaskId, "Length:", chunk.length);
                            fullResponse += chunk;
                            streamHandler(chunk);
                        } else {
                            console.log("Ignoring chunk for previous task:", currentTaskId, "Current task:", CURRENT_TASK_ID);
                        }
                    })
                    .then(response => {
                        console.log("Streaming complete for task:", currentTaskId, "Response length:", response.length);
                        console.log("Accumulated fullResponse length:", fullResponse.length);
                        
                        // Check if we have a valid response
                        if (response.length === 0 && fullResponse.length > 0) {
                            console.log("Using accumulated fullResponse instead of empty response");
                            response = fullResponse;
                        } else if (response.length === 0) {
                            console.warn("Received empty response from streaming API");
                            
                            // Check if the message element has any content despite empty response
                            const messageElement = $(`#${messageId} .message_content`);
                            const currentContent = messageElement.html();
                            
                            if (currentContent && currentContent.trim().length > 0) {
                                console.log("Message element has content despite empty response, keeping it");
                                // Use the HTML content that was accumulated during streaming
                                response = messageElement.text(); // Get the text content without HTML
                            } else {
                                // No content at all, show error message
                                removeTypingIndicator();
                                addSystemMessage("The AI model returned an empty response. Please try again or try with a different model.");
                                
                                // Clear the empty AI message that was created for streaming
                                $(`#${messageId}`).remove();
                                
                        // Clear the active controller
                        if (ACTIVE_STREAM_CONTROLLER) {
                            ACTIVE_STREAM_CONTROLLER = null;
                        }
                        
                        // Re-enable the send button and hide the stop button
                        $('#send_message_btn').prop('disabled', false);
                        $('#stop_streaming_btn').hide();
                                return;
                            }
                        }
                        
                        // Process the raw content to properly format code blocks
                        const messageElement = $(`#${messageId} .message_content`);
                        const rawContent = messageElement.attr('data-raw-content') || '';
                        
                        if (rawContent) {
                            // Process the raw content to properly format code blocks
                            let processedText = escapeHtml(rawContent);
                            
                            // Check if there are code blocks (```python ... ```)
                            const codeBlockRegex = /```(?:python)?([\s\S]*?)```/g;
                            processedText = processedText.replace(codeBlockRegex, function(match, codeContent) {
                                console.log("Found code block, content:", codeContent.substring(0,50) + "...");
                                // Wrap code in a pre>code block to preserve indentation
                                return `<pre><code>${codeContent}</code></pre>`;
                            });
                            
                            // For text outside of code blocks, replace newlines with <br>
                            let finalHtml = '';
                            let segments = processedText.split(/(<pre>[\s\S]*?<\/pre>)/g);
                            
                            segments.forEach(segment => {
                                if (segment.startsWith('<pre>')) {
                                    finalHtml += segment; // Already formatted and escaped
                                } else {
                                    finalHtml += segment.replace(/\n/g, '<br>');
                                }
                            });
                            
                            // Update the message content with properly formatted HTML
                            messageElement.html(finalHtml);
                        }
                        
                        // Save the complete response to memory only if we're still on the same task
                        if (CURRENT_TASK_ID === currentTaskId) {
                            addMessageToMemory(CURRENT_TASK_ID, 'ai', response);
                        }
                        
                        // Clear the active controller
                        if (ACTIVE_STREAM_CONTROLLER) {
                            ACTIVE_STREAM_CONTROLLER = null;
                        }
                        
                        // Re-enable the send button and hide the stop button
                        $('#send_message_btn').prop('disabled', false);
                        $('#stop_streaming_btn').hide();
                    })
                    .catch(error => {
                        console.error("Streaming error for task:", currentTaskId, "Error:", error);
                        
                        // Check if this is a timeout error
                        const isTimeout = error.message && error.message.includes("timed out after 180 seconds");
                        
                        // Only show error if we're still on the same task
                        if (CURRENT_TASK_ID === currentTaskId) {
                            if (isTimeout) {
                                // For timeout errors, the message has already been added to the UI by the timeout handler
                                console.log("Timeout error handled for task:", currentTaskId);
                                
                                // Process the raw content to properly format code blocks
                                const messageElement = $(`#${messageId} .message_content`);
                                const rawContent = messageElement.attr('data-raw-content') || '';
                                
                                if (rawContent) {
                                    // Process the raw content to properly format code blocks
                                    let processedText = escapeHtml(rawContent);
                                    
                                    // Check if there are code blocks (```python ... ```)
                                    const codeBlockRegex = /```(?:python)?([\s\S]*?)```/g;
                                    processedText = processedText.replace(codeBlockRegex, function(match, codeContent) {
                                        console.log("Found code block in timeout response, content:", codeContent.substring(0,50) + "...");
                                        // Wrap code in a pre>code block to preserve indentation
                                        return `<pre><code>${codeContent}</code></pre>`;
                                    });
                                    
                                    // For text outside of code blocks, replace newlines with <br>
                                    let finalHtml = '';
                                    let segments = processedText.split(/(<pre>[\s\S]*?<\/pre>)/g);
                                    
                                    segments.forEach(segment => {
                                        if (segment.startsWith('<pre>')) {
                                            finalHtml += segment; // Already formatted and escaped
                                        } else {
                                            finalHtml += segment.replace(/\n/g, '<br>');
                                        }
                                    });
                                    
                                    // Add a note that this was cut off
                                    finalHtml += '<br><br><em>[Response was cut off due to 180-second timeout]</em>';
                                    
                                    // Update the message content with properly formatted HTML
                                    messageElement.html(finalHtml);
                                    
                                    // Save the partial response to memory
                                    const partialContent = rawContent + "\n\n[Response was cut off due to 180-second timeout]";
                                    addMessageToMemory(CURRENT_TASK_ID, 'ai', partialContent);
                                }
                            } else if (error.name !== 'AbortError') {
                                // For non-abort errors, show the error message
                                console.error("Error getting AI response:", error);
                                addSystemMessage(`Error: ${error.message || "Failed to get response from AI model"}`);
                            } else {
                                console.log("Streaming was aborted for task:", currentTaskId);
                            }
                        } else {
                            console.log("Ignoring error for previous task:", currentTaskId);
                        }
                        
                        // Clear the active controller
                        if (ACTIVE_STREAM_CONTROLLER) {
                            ACTIVE_STREAM_CONTROLLER = null;
                        }
                        
                        // Re-enable the send button
                        $('#send_message_btn').prop('disabled', false);
                    });
            } catch (error) {
                console.error("Exception during streaming setup:", error);
                addSystemMessage(`Error: ${error.message || "Failed to set up streaming"}`);
                
                // Clear the active controller
                if (ACTIVE_STREAM_CONTROLLER) {
                    ACTIVE_STREAM_CONTROLLER = null;
                }
            }
        } else {
            // Use the OpenRouter API without streaming
            OpenRouterAPI.sendMessage(API_KEY, messageText, taskContext, TEMPERATURE, conversationHistory)
                .then(response => {
                    removeTypingIndicator();
                    addAiMessage(response);
                    // Re-enable the send button
                    $('#send_message_btn').prop('disabled', false);
                })
                .catch(error => {
                    removeTypingIndicator();
                    console.error("Error getting AI response:", error);
                    addSystemMessage(`Error: ${error.message || "Failed to get response from AI model"}`);
                    // Re-enable the send button
                    $('#send_message_btn').prop('disabled', false);
                });
        }
    } else {
        // Remove typing indicator after a short delay
        setTimeout(() => {
            removeTypingIndicator();
            addSystemMessage("Please enter your OpenRouter API key in the settings below to enable AI responses.");
        }, 500);
    }
}

function addUserMessage(text) {
    const messageHtml = `
        <div class="user_message">
            <div class="message_sender">${USERNAME}</div>
            <div class="message_content">${escapeHtml(text)}</div>
        </div>
    `;
    $('#chat_messages').append(messageHtml);
    scrollChatToBottom();
    
    // Save to memory if we have a current task
    if (CURRENT_TASK_ID) {
        addMessageToMemory(CURRENT_TASK_ID, 'user', text);
    }
}

function addAiMessage(text) {
    // Process the text to properly format code blocks
    let processedText = escapeHtml(text);
    
    // Check if there are code blocks (```python ... ```)
    const codeBlockRegex = /```(?:python)?([\s\S]*?)```/g;
    processedText = processedText.replace(codeBlockRegex, function(match, codeContent) {
        // Wrap code in a pre>code block to preserve indentation
        return `<pre><code>${codeContent}</code></pre>`;
    });
    
    // For text outside of code blocks, replace newlines with <br>
    // But we need to avoid replacing newlines inside the <pre> tags we just created
    let finalHtml = '';
    let inPreTag = false;
    let segments = processedText.split(/(<pre>[\s\S]*?<\/pre>)/g);
    
    segments.forEach(segment => {
        if (segment.startsWith('<pre>')) {
            finalHtml += segment;
        } else {
            finalHtml += segment.replace(/\n/g, '<br>');
        }
    });
    
    const messageHtml = `
        <div class="ai_message">
            <div class="message_sender">AI Assistant</div>
            <div class="message_content">${finalHtml}</div>
        </div>
    `;
    $('#chat_messages').append(messageHtml);
    scrollChatToBottom();
    
    // Save to memory if we have a current task
    if (CURRENT_TASK_ID) {
        addMessageToMemory(CURRENT_TASK_ID, 'ai', text);
    }
}

function addSystemMessage(text) {
    const messageHtml = `
        <div class="system_message">
            <div class="message_content">${escapeHtml(text)}</div>
        </div>
    `;
    $('#chat_messages').append(messageHtml);
    scrollChatToBottom();
    
    // Save to memory if we have a current task and it's not a welcome message for a new task
    if (CURRENT_TASK_ID && !text.startsWith("Welcome to the discussion for this task")) {
        addMessageToMemory(CURRENT_TASK_ID, 'system', text);
    }
}

function addTypingIndicator() {
    const indicatorHtml = `
        <div id="typing_indicator" class="ai_message">
            <div class="message_sender">AI Assistant</div>
            <div class="message_content">Typing<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></div>
        </div>
    `;
    $('#chat_messages').append(indicatorHtml);
    scrollChatToBottom();
    
    // Animate dots
    let dotIndex = 0;
    window.typingInterval = setInterval(() => {
        const dots = $('#typing_indicator .dot');
        dots.css('opacity', 0.3);
        $(dots[dotIndex]).css('opacity', 1);
        dotIndex = (dotIndex + 1) % dots.length;
    }, 500);
}

function removeTypingIndicator() {
    clearInterval(window.typingInterval);
    $('#typing_indicator').remove();
}

function scrollChatToBottom() {
    const chatMessages = $('#chat_messages');
    chatMessages.scrollTop(chatMessages[0].scrollHeight);
}

// Chat Memory Management Functions

// Initialize chat memory structure
function initChatMemory() {
    // Try to load existing memory from localStorage
    const savedMemory = localStorage.getItem('arc_chat_memory');
    if (savedMemory) {
        try {
            CHAT_MEMORY = JSON.parse(savedMemory);
            console.log("Chat memory loaded from localStorage");
        } catch (e) {
            console.error("Error parsing saved chat memory:", e);
            CHAT_MEMORY = {};
        }
    } else {
        CHAT_MEMORY = {};
    }
    
    // Ensure the current user has a memory object
    if (!CHAT_MEMORY[USERNAME]) {
        CHAT_MEMORY[USERNAME] = {};
    }
}

// Save chat memory to localStorage
function saveChatMemory() {
    try {
        localStorage.setItem('arc_chat_memory', JSON.stringify(CHAT_MEMORY));
        console.log("Chat memory saved to localStorage");
    } catch (e) {
        console.error("Error saving chat memory:", e);
        // If localStorage is full, we might need to clear some old conversations
        if (e.name === 'QuotaExceededError') {
            pruneOldestConversations();
            try {
                localStorage.setItem('arc_chat_memory', JSON.stringify(CHAT_MEMORY));
                console.log("Chat memory saved after pruning old conversations");
            } catch (e2) {
                console.error("Still unable to save chat memory after pruning:", e2);
            }
        }
    }
}

// Add a message to memory
function addMessageToMemory(taskId, role, content) {
    if (!USERNAME || !taskId) return;
    
    // Ensure user and task structures exist
    if (!CHAT_MEMORY[USERNAME]) {
        CHAT_MEMORY[USERNAME] = {};
    }
    if (!CHAT_MEMORY[USERNAME][taskId]) {
        CHAT_MEMORY[USERNAME][taskId] = [];
    }
    
    // Add message with timestamp
    CHAT_MEMORY[USERNAME][taskId].push({
        role: role,
        content: content,
        timestamp: new Date().toISOString()
    });
    
    // Save to localStorage
    saveChatMemory();
}

// Get messages for a specific task
function getTaskMessages(taskId) {
    if (!USERNAME || !taskId || !CHAT_MEMORY[USERNAME] || !CHAT_MEMORY[USERNAME][taskId]) {
        return [];
    }
    return CHAT_MEMORY[USERNAME][taskId];
}

// Clear messages for a specific task
function clearTaskMemory(taskId) {
    if (!USERNAME || !taskId || !CHAT_MEMORY[USERNAME]) return;
    
    // Delete the task's messages
    if (CHAT_MEMORY[USERNAME][taskId]) {
        delete CHAT_MEMORY[USERNAME][taskId];
        saveChatMemory();
        console.log(`Cleared chat memory for task ${taskId}`);
        return true;
    }
    return false;
}

// Clear all messages for the current user
function clearAllUserMemory() {
    if (!USERNAME || !CHAT_MEMORY[USERNAME]) return;
    
    CHAT_MEMORY[USERNAME] = {};
    saveChatMemory();
    console.log(`Cleared all chat memory for user ${USERNAME}`);
    return true;
}

// Prune oldest conversations if storage is full
function pruneOldestConversations() {
    if (!USERNAME || !CHAT_MEMORY[USERNAME]) return;
    
    const userMemory = CHAT_MEMORY[USERNAME];
    const taskIds = Object.keys(userMemory);
    
    if (taskIds.length <= 1) return; // Keep at least one conversation
    
    // Find the oldest conversation based on the timestamp of the last message
    let oldestTaskId = null;
    let oldestTimestamp = Date.now();
    
    taskIds.forEach(taskId => {
        const messages = userMemory[taskId];
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            const timestamp = new Date(lastMessage.timestamp).getTime();
            if (timestamp < oldestTimestamp) {
                oldestTimestamp = timestamp;
                oldestTaskId = taskId;
            }
        } else {
            // If no messages, this is a candidate for removal
            oldestTaskId = taskId;
        }
    });
    
    // Remove the oldest conversation
    if (oldestTaskId) {
        delete userMemory[oldestTaskId];
        console.log(`Pruned oldest conversation for task ${oldestTaskId}`);
    }
}

// Display chat history for the current task
function displayChatHistory() {
    if (!CURRENT_TASK_ID) return;
    
    // Clear current chat display
    $('#chat_messages').empty();
    
    // Get messages for the current task
    const messages = getTaskMessages(CURRENT_TASK_ID);
    
    if (messages.length === 0) {
        // Add welcome message if no history
        addSystemMessage("Welcome to the discussion for this task. Ask questions or discuss patterns you notice.");
        return;
    }
    
    // Add each message to the display
    messages.forEach(message => {
        if (message.role === 'user') {
            const messageHtml = `
                <div class="user_message">
                    <div class="message_sender">${USERNAME}</div>
                    <div class="message_content">${escapeHtml(message.content)}</div>
                </div>
            `;
            $('#chat_messages').append(messageHtml);
        } else if (message.role === 'ai') {
            // Process the text to properly format code blocks
            let processedText = escapeHtml(message.content);
            
            // Check if there are code blocks (```python ... ```)
            const codeBlockRegex = /```(?:python)?([\s\S]*?)```/g;
            processedText = processedText.replace(codeBlockRegex, function(match, codeContent) {
                // Wrap code in a pre>code block to preserve indentation
                return `<pre><code>${codeContent}</code></pre>`;
            });
            
            // For text outside of code blocks, replace newlines with <br>
            let finalHtml = '';
            let segments = processedText.split(/(<pre>[\s\S]*?<\/pre>)/g);
            
            segments.forEach(segment => {
                if (segment.startsWith('<pre>')) {
                    finalHtml += segment;
                } else {
                    finalHtml += segment.replace(/\n/g, '<br>');
                }
            });
            
            const messageHtml = `
                <div class="ai_message">
                    <div class="message_sender">AI Assistant</div>
                    <div class="message_content">${finalHtml}</div>
                </div>
            `;
            $('#chat_messages').append(messageHtml);
        } else if (message.role === 'system') {
            const messageHtml = `
                <div class="system_message">
                    <div class="message_content">${escapeHtml(message.content)}</div>
                </div>
            `;
            $('#chat_messages').append(messageHtml);
        }
    });
    
    // Scroll to bottom
    scrollChatToBottom();
}

// Logout function
function logoutUser() {
    // Clear username cookie
    setCookie('username', '', -1);
    
    // Reset username
    USERNAME = "Anonymous";
    $('#username_input').val('');
    
    // Redirect to the welcome page (root URL)
    window.location.href = '/';
    console.log("Redirecting to welcome page (root URL):", '/');
}

// Helper functions
function escapeHtml(text) {
    return $('<div>').text(text).html();
}

function setCookie(name, value, days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) == ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

// Grid utility functions (using Grid from common.js)
function convertSerializedGridToGridObject(serializedGrid) {
    if (!serializedGrid || !Array.isArray(serializedGrid) || serializedGrid.length === 0) {
        return new Grid(3, 3); // Default empty grid
    }
    
    const height = serializedGrid.length;
    const width = serializedGrid[0].length || 0;
    
    return new Grid(height, width, serializedGrid);
}

function fillJqGridWithData(jqGrid, dataGrid) {
    jqGrid.empty();
    
    for (let i = 0; i < dataGrid.height; i++) {
        let rowDiv = $('<div class="row"></div>');
        
        for (let j = 0; j < dataGrid.width; j++) {
            let cellDiv = $('<div class="cell"></div>');
            let symbol = dataGrid.grid[i][j];
            
            cellDiv.addClass('symbol_' + symbol);
            cellDiv.attr('symbol', symbol);
            cellDiv.attr('x', j);
            cellDiv.attr('y', i);
            
            rowDiv.append(cellDiv);
        }
        
        jqGrid.append(rowDiv);
    }
}

function fitCellsToContainer(jqGrid, gridHeight, gridWidth, containerHeight, containerWidth) {
    const cellSize = Math.min(
        Math.floor(containerWidth / gridWidth),
        Math.floor(containerHeight / gridHeight)
    );
    
    jqGrid.find('.cell').css({
        width: cellSize + 'px',
        height: cellSize + 'px'
    });
}

// Code Execution Functions
function executeCode() {
    // Get code and input grid from UI
    const code = $('#code_input').val().trim();
    const inputGridText = $('#grid_input').val().trim();
    
    // Validate inputs
    if (!code) {
        $('#execution_status').text('Please enter Python code');
        return;
    }
    
    if (!inputGridText) {
        $('#execution_status').text('Please enter an input grid');
        return;
    }
    
    // Parse input grid
    let inputGrid;
    try {
        inputGrid = JSON.parse(inputGridText);
        if (!Array.isArray(inputGrid) || !inputGrid.every(row => Array.isArray(row))) {
            throw new Error('Input grid must be a 2D array');
        }
    } catch (e) {
        $('#execution_status').text('Invalid input grid format: ' + e.message);
        return;
    }
    
    // Update status
    $('#execution_status').text('Executing code...');
    $('#code_error_display').hide();
    $('#grid_output_display').empty();
    
    // Send to server
    $.ajax({
        url: '/arc2/execute_code',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            code: code,
            input_grid: inputGrid
        }),
        success: function(response) {
            if (response.success) {
                // Display output grid
                $('#execution_status').text('Execution successful');
                displayOutputGrid(response.output_grid);
            } else {
                // Display error
                $('#execution_status').text('Execution failed');
                $('#code_error_display').text(response.error).show();
            }
        },
        error: function(xhr, status, error) {
            $('#execution_status').text('Server error: ' + error);
            $('#code_error_display').text('Failed to communicate with the server').show();
        }
    });
}

// Input Grid Visualization Function
function visualizeInputGrid() {
    // Get input grid from UI
    const inputGridText = $('#grid_input').val().trim();
    
    // Validate input
    if (!inputGridText) {
        $('#execution_status').text('Please enter an input grid');
        return;
    }
    
    // Parse input grid
    let inputGrid;
    try {
        inputGrid = JSON.parse(inputGridText);
        if (!Array.isArray(inputGrid) || !inputGrid.every(row => Array.isArray(row))) {
            throw new Error('Input grid must be a 2D array');
        }
    } catch (e) {
        $('#execution_status').text('Invalid input grid format: ' + e.message);
        return;
    }
    
    // Create a Grid object from the input
    const gridObject = convertSerializedGridToGridObject(inputGrid);
    
    // Clear previous input visualization
    const gridDisplay = $('#grid_input_display');
    gridDisplay.empty();
    
    // Create visual grid container (using common grid styling)
    const gridContainer = $('<div class="grid_container"></div>'); // Use a generic class or style directly
    
    // Fill the grid with data
    fillJqGridWithData(gridContainer, gridObject);
    
    // Size the cells appropriately based on the container's available space
    // We use the width of the parent (#grid_input_right) and a reasonable height
    const containerWidth = gridDisplay.parent().width() || 200; // Get width of #grid_input_right
    const containerHeight = 200; // Set a reasonable max height for the visual grid
    fitCellsToContainer(gridContainer, gridObject.height, gridObject.width, containerHeight, containerWidth);
    
    // Add the visual grid directly to the display area
    gridDisplay.append(gridContainer);
    
    // Show the input display
    $('#grid_input_display').show();
}

function displayOutputGrid(grid) {
    if (!grid || !Array.isArray(grid)) {
        $('#grid_output').val('Invalid output grid');
        return;
    }
    
    // Create a Grid object from the output
    const outputGrid = convertSerializedGridToGridObject(grid);
    
    // Store the output grid in a global variable for later visualization
    window.currentOutputGrid = outputGrid;
    
    // Clear previous output
    $('#grid_output').val('');
    
    // Add matrix representation to the text area
    let matrixString = '';
    for (let i = 0; i < outputGrid.height; i++) {
        matrixString += '[';
        for (let j = 0; j < outputGrid.width; j++) {
            matrixString += outputGrid.grid[i][j];
            if (j < outputGrid.width - 1) {
                matrixString += ', ';
            }
        }
        matrixString += ']';
        if (i < outputGrid.height - 1) {
            matrixString += ',\n';
        }
    }
    $('#grid_output').val(matrixString);
    
    // Hide the visual output display (it will be shown when the user clicks the visualize button)
    $('#visual_output_display').hide();
}

// Function to visualize the output grid
function visualizeOutputGrid() {
    let outputGridObject = window.currentOutputGrid;

    // If window.currentOutputGrid is not set (e.g., manual input), parse from the textarea
    if (!outputGridObject) {
        const outputGridText = $('#grid_output').val().trim();
        if (!outputGridText) {
            $('#execution_status').text('No output grid to visualize');
            return;
        }
        try {
            const outputGrid = JSON.parse(outputGridText);
            if (!Array.isArray(outputGrid) || !outputGrid.every(row => Array.isArray(row))) {
                throw new Error('Output grid must be a 2D array');
            }
            outputGridObject = convertSerializedGridToGridObject(outputGrid);
        } catch (e) {
            $('#execution_status').text('Invalid output grid format: ' + e.message);
            return;
        }
    }
    
    // Clear previous visualization
    $('#visual_output_display').empty();
    
    // Create visual grid container
    const gridContainer = $('<div class="grid_container"></div>');
    
    // Fill the grid with data
    fillJqGridWithData(gridContainer, outputGridObject);
    
    // Size the cells appropriately
    const containerWidth = $('#visual_output_display').width() || 200;
    const containerHeight = 200; // Fixed height
    fitCellsToContainer(gridContainer, outputGridObject.height, outputGridObject.width, containerHeight, containerWidth);
    
    // Add visual grid to its container
    $('#visual_output_display').append(gridContainer);
    
    // Show the visual output display
    $('#visual_output_display').show();
}

// Submit Reasoning Trace Function
function submitReasoningTrace() {
    // Get trace content from UI
    const traceContent = $('#code_input').val().trim();
    
    // Get current task ID
    const taskId = CURRENT_TASK_ID;
    
    // Validate inputs
    if (!traceContent) {
        $('#execution_status').text('Please enter reasoning trace content');
        return;
    }
    
    if (!taskId) {
        $('#execution_status').text('No task selected to submit trace for');
        return;
    }
    
    // Update status
    $('#execution_status').text('Submitting reasoning trace...');
    $('#code_error_display').hide();
    
    // Check if socket is connected
    if (socket && socket.connected) {
        // Emit add_trace event to server (same as testing interface)
        console.log(`Emitting add_trace: task_id=${taskId}, username=${USERNAME}, text=${traceContent}`);
        socket.emit('add_trace', {
            task_id: taskId,
            username: USERNAME,
            text: traceContent
        });
        
        // Clear the code input area immediately for better UX
        $('#code_input').val('');
        
        // Show temporary success message (will be updated by socket events)
        $('#execution_status').text('Reasoning trace submitted successfully');
    } else {
        // Socket not connected
        $('#execution_status').text('Cannot submit trace: Not connected to real-time server');
        $('#code_error_display').text('WebSocket connection is not available. Please refresh the page.').show();
    }
}
