// Global variables
var USERNAME = "Anonymous";
var CURRENT_TASK_ID = null;
var LOADED_TASK_LIST = [];
var UNIQUE_TASK_IDS = [];
var TASK_VERSIONS_MAP = {};
var socket = null;
var API_KEY = null;

// Initialize the interface
$(document).ready(function() {
    // Initialize WebSocket connection
    connectWebSocket();

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

    // Send message button
    $('#send_message_btn').click(function() {
        sendUserMessage();
    });

    // Send message on Enter (but allow Shift+Enter for new lines)
    $('#chat_input').keydown(function(event) {
        if (event.keyCode === 13 && !event.shiftKey) {
            event.preventDefault();
            sendUserMessage();
        }
    });

    // Task navigation buttons
    $('#random_task_btn').click(function() {
        randomTask();
    });

    $('#prev_task_btn').click(function() {
        previousTask();
    });

    $('#next_task_btn').click(function() {
        nextTask();
    });

    $('#goto_task_btn').click(function() {
        gotoTaskById();
    });

    // Enter key for task ID input
    $('#task_id_input').keydown(function(event) {
        if (event.keyCode === 13) {
            gotoTaskById();
        }
    });
});

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
    if (!TASK_VERSIONS_MAP[taskId] || versionIndex < 0 || versionIndex >= TASK_VERSIONS_MAP[taskId].length) {
        addSystemMessage(`Error: Task ID '${taskId}' version index ${versionIndex} not found.`);
        return;
    }

    const taskObject = TASK_VERSIONS_MAP[taskId][versionIndex];
    CURRENT_TASK_ID = taskId;

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

        // Add system message about the loaded task
        addSystemMessage(`Loaded task ID: ${taskId}`);

    } catch (e) {
        console.error(`Error processing task ${taskId}:`, e);
        addSystemMessage(`Error loading task ${taskId}: ${e.message}`);
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
            $('#task_index_display').text(`Task ${uniqueIndex + 1}/${UNIQUE_TASK_IDS.length}`);
            $('#prev_task_btn').prop('disabled', uniqueIndex === 0);
            $('#next_task_btn').prop('disabled', uniqueIndex === UNIQUE_TASK_IDS.length - 1);
        }
    } else {
        $('#task_index_display').text(`No tasks loaded`);
        $('#prev_task_btn').prop('disabled', true);
        $('#next_task_btn').prop('disabled', true);
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
    const taskIdToFind = $('#task_id_input').val().trim();
    if (!taskIdToFind) {
        addSystemMessage("Please enter a Task ID.");
        return;
    }

    if (TASK_VERSIONS_MAP.hasOwnProperty(taskIdToFind)) {
        loadTask(taskIdToFind, 0);
        $('#task_id_input').val('');
    } else {
        addSystemMessage(`Task ID '${taskIdToFind}' not found.`);
    }
}

// Chat functions
function sendUserMessage() {
    const messageText = $('#chat_input').val().trim();
    if (!messageText) return;

    // Add user message to chat
    addUserMessage(messageText);
    
    // Clear input
    $('#chat_input').val('');

    // Check if API key is set
    if (!API_KEY) {
        addSystemMessage("Please enter your OpenRouter API key in the settings below to enable AI responses.");
        return;
    }

    // Prepare context about the current task
    let taskContext = "";
    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const task = TASK_VERSIONS_MAP[CURRENT_TASK_ID][0]; // Use first version
        taskContext = `Current task ID: ${CURRENT_TASK_ID}\n`;
        
        if (task.train && task.train.length > 0) {
            taskContext += `The task has ${task.train.length} training examples and ${task.test ? task.test.length : 0} test examples.\n`;
            
            // Add description of the training examples
            taskContext += "Training examples show input grids and their corresponding output grids. ";
            taskContext += "The user is trying to understand the pattern or transformation rule that maps inputs to outputs.\n";
        }
    } else {
        taskContext = "No specific task is currently selected.\n";
    }

    // Show typing indicator
    addTypingIndicator();

    // Get the selected model info
    const modelInfo = OpenRouterAPI.getSelectedModel();
    console.log(`Using model: ${modelInfo.name} (${modelInfo.id})`);
    
    // If we have an API key, try to use the OpenRouter API
    if (API_KEY) {
        // Use a timeout to simulate the API call for now
        // In production, this would be replaced with the actual API call
        setTimeout(() => {
            try {
                removeTypingIndicator();
                
                // For testing, simulate a response based on the user's message
                let aiResponse = "";
                
                if (messageText.toLowerCase().includes("hello") || messageText.toLowerCase().includes("hi")) {
                    aiResponse = "Hello! I'm here to help you understand ARC tasks. What would you like to discuss?";
                } 
                else if (messageText.toLowerCase().includes("what is arc")) {
                    aiResponse = "The Abstraction and Reasoning Corpus (ARC) is a dataset designed to measure general AI reasoning capabilities. It consists of tasks where you need to infer a pattern from a few examples and apply it to new inputs.";
                }
                else if (CURRENT_TASK_ID && (messageText.toLowerCase().includes("this task") || messageText.toLowerCase().includes("current task"))) {
                    aiResponse = `This task (ID: ${CURRENT_TASK_ID}) requires you to analyze the pattern in the training examples shown on the left. Look for transformations between input and output grids, such as rotations, color changes, or pattern recognition.`;
                }
                else {
                    aiResponse = `I would use the ${modelInfo.name} model to analyze this. In a real implementation, I would connect to OpenRouter to provide helpful insights about ARC tasks and reasoning strategies.`;
                }
                
                addAiMessage(aiResponse);
            } catch (error) {
                // Handle errors
                removeTypingIndicator();
                console.error("Error getting AI response:", error);
                addSystemMessage(`Error: ${error.message || "Failed to get response from AI model"}`);
            }
        }, 1500);
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
}

function addAiMessage(text) {
    const messageHtml = `
        <div class="ai_message">
            <div class="message_sender">AI Assistant</div>
            <div class="message_content">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        </div>
    `;
    $('#chat_messages').append(messageHtml);
    scrollChatToBottom();
}

function addSystemMessage(text) {
    const messageHtml = `
        <div class="system_message">
            <div class="message_content">${escapeHtml(text)}</div>
        </div>
    `;
    $('#chat_messages').append(messageHtml);
    scrollChatToBottom();
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
