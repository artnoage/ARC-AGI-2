// Internal state.
var CURRENT_INPUT_GRID = new Grid(3, 3); // Grid object for the current test input (displayed)
var CURRENT_OUTPUT_GRID = new Grid(3, 3); // Grid object for the user's output editor
var ORIGINAL_TASK_DATA = null; // Holds the raw task object {train: [...], test: [...], id: ...} as loaded
var DISPLAYED_TASK_DATA = null; // Holds the potentially transformed task object
var DISPLAYED_TRAIN_PAIRS = []; // Train pairs for the *currently displayed* (transformed) task
var DISPLAYED_TEST_PAIRS = []; // Test pairs for the *currently displayed* (transformed) task
var CURRENT_TEST_PAIR_INDEX = 0; // Index for DISPLAYED_TEST_PAIRS
var COPY_PASTE_DATA = new Array();
var LOADED_TASK_LIST = []; // Holds the raw list of all entries from dataset.json
var TASK_VERSIONS_MAP = {}; // Maps task_id -> array of task objects sorted by version {id: [task_v0, task_v1], ...}
var UNIQUE_TASK_IDS = []; // Ordered list of unique task IDs found in the dataset
var CURRENT_TASK_ID = null; // The ID of the task currently being viewed
var CURRENT_VERSION_INDEX = -1; // The index within TASK_VERSIONS_MAP[CURRENT_TASK_ID] for the viewed version
var CURRENT_DATASET_NAME = null; // Will likely just be 'dataset' now
// var TASK_ID_MAP = {}; // Replaced by TASK_VERSIONS_MAP and UNIQUE_TASK_IDS
// var CURRENT_TASK_INDEX = -1; // Replaced by CURRENT_TASK_ID and CURRENT_VERSION_INDEX
var CURRENT_TRACE_INDEX = 0; // Index of the currently viewed trace for the active task ID
var USERNAME = "Anonymous"; // Default username, will be updated from input
var socket = null; // WebSocket connection object
var pendingTaskId = null; // For restoring state on refresh
var pendingVersionIndex = null; // For restoring state on refresh
var pendingDatasetName = null; // For restoring state on refresh

// Cosmetic.
var EDITION_GRID_HEIGHT = 500;
var EDITION_GRID_WIDTH = 500;
var MAX_CELL_SIZE = 100;


function resetTask(isDatasetLoad = false) { // Changed parameter name for clarity
    // Reset grids and current test pair index
    CURRENT_INPUT_GRID = new Grid(3, 3);
    // TEST_PAIRS = new Array(); // Replaced by DISPLAYED_TEST_PAIRS
    CURRENT_TEST_PAIR_INDEX = 0;
    $('#task_preview').html(''); // Clear old demonstration pairs
    resetOutputGrid(); // Reset the output grid editor

    // Reset task data state
    ORIGINAL_TASK_DATA = null;
    DISPLAYED_TASK_DATA = null;
    DISPLAYED_TRAIN_PAIRS = [];
    DISPLAYED_TEST_PAIRS = [];

    // Uncheck transformation checkboxes
    $('#transformation_controls_area input[type=checkbox]').prop('checked', false);


    // Reset version-specific UI
    $('#version_navigation').hide();
    $('#version_display').text('Ver -/-');
    $('#prev_version_btn').prop('disabled', true);
    $('#next_version_btn').prop('disabled', true);

    // Only fully reset dataset state if loading a new dataset
    if (isDatasetLoad) {
        LOADED_TASK_LIST = [];
        TASK_VERSIONS_MAP = {};
        UNIQUE_TASK_IDS = [];
        CURRENT_TASK_ID = null;
        CURRENT_VERSION_INDEX = -1;
        CURRENT_DATASET_NAME = null; // Clear dataset name
        $('#list_navigation').hide(); // Task navigation
        $('#task_index_display').text('');
        $('#loaded_dataset_display').text('');
        $('#goto_id_controls').hide();
        $('#comment_section').hide(); // Hide comments until a task is loaded
        CURRENT_TRACE_INDEX = 0; // Reset trace index
    }

    $('#error_display').hide();
    $('#info_display').hide();
    // Also reset trace display area on task reset (even if not full dataset load)
    $('#comment_display_area').text('No reasoning traces added yet.');
    $('#comment_score_display').text('0');
    $('#comment_nav_display').text('Trace -/-');
    $('#prev_comment_btn').prop('disabled', true);
    $('#next_comment_btn').prop('disabled', true);
    // Keep comment section hidden unless a task is successfully loaded later
    if (!isDatasetLoad) {
        $('#comment_section').hide();
    }
    $('#upvote_btn').prop('disabled', true);
    $('#downvote_btn').prop('disabled', true);
}

function refreshEditionGrid(jqGrid, dataGrid) {
    fillJqGridWithData(jqGrid, dataGrid);
    setUpEditionGridListeners(jqGrid);
    fitCellsToContainer(jqGrid, dataGrid.height, dataGrid.width, EDITION_GRID_HEIGHT, EDITION_GRID_HEIGHT);
    initializeSelectable();
}

function syncFromEditionGridToDataGrid() {
    copyJqGridToDataGrid($('#output_grid .edition_grid'), CURRENT_OUTPUT_GRID);
}

function syncFromDataGridToEditionGrid() {
    refreshEditionGrid($('#output_grid .edition_grid'), CURRENT_OUTPUT_GRID);
}

function getSelectedSymbol() {
    selected = $('#symbol_picker .selected-symbol-preview')[0];
    return $(selected).attr('symbol');
}

function setUpEditionGridListeners(jqGrid) {
    jqGrid.find('.cell').click(function(event) {
        cell = $(event.target);
        symbol = getSelectedSymbol();

        mode = $('input[name=tool_switching]:checked').val();
        if (mode == 'floodfill') {
            // If floodfill: fill all connected cells.
            syncFromEditionGridToDataGrid();
            grid = CURRENT_OUTPUT_GRID.grid;
            floodfillFromLocation(grid, cell.attr('x'), cell.attr('y'), symbol);
            syncFromDataGridToEditionGrid();
        }
        else if (mode == 'edit') {
            // Else: fill just this cell.
            setCellSymbol(cell, symbol);
        }
        // Update distance after any edit/floodfill action
        updateDistanceDisplay();
    });
}

function resizeOutputGrid() {
    size = $('#output_grid_size').val();
    size = parseSizeTuple(size);
    height = size[0];
    width = size[1];

    jqGrid = $('#output_grid .edition_grid');
    syncFromEditionGridToDataGrid();
    dataGrid = JSON.parse(JSON.stringify(CURRENT_OUTPUT_GRID.grid));
    CURRENT_OUTPUT_GRID = new Grid(height, width, dataGrid);
    refreshEditionGrid(jqGrid, CURRENT_OUTPUT_GRID);
    updateDistanceDisplay(); // Update distance after resize
}

function resetOutputGrid() {
    syncFromEditionGridToDataGrid();
    CURRENT_OUTPUT_GRID = new Grid(3, 3);
    syncFromDataGridToEditionGrid();
    resizeOutputGrid(); // This already calls refreshEditionGrid and updateDistanceDisplay
    // updateDistanceDisplay(); // No need to call again, resizeOutputGrid handles it
}

function copyFromInput() {
    syncFromEditionGridToDataGrid();
    CURRENT_OUTPUT_GRID = convertSerializedGridToGridObject(CURRENT_INPUT_GRID.grid);
    syncFromDataGridToEditionGrid();
    $('#output_grid_size').val(CURRENT_OUTPUT_GRID.height + 'x' + CURRENT_OUTPUT_GRID.width);
    updateDistanceDisplay(); // Update distance after copy
}

function fillPairPreview(pairId, inputGrid, outputGrid) {
    var pairSlot = $('#pair_preview_' + pairId);
    if (!pairSlot.length) {
        // Create HTML for pair.
        pairSlot = $('<div id="pair_preview_' + pairId + '" class="pair_preview" index="' + pairId + '"></div>');
        pairSlot.appendTo('#task_preview');
    }
    var jqInputGrid = pairSlot.find('.input_preview');
    if (!jqInputGrid.length) {
        jqInputGrid = $('<div class="input_preview"></div>');
        jqInputGrid.appendTo(pairSlot);
    }
    var jqOutputGrid = pairSlot.find('.output_preview');
    if (!jqOutputGrid.length) {
        jqOutputGrid = $('<div class="output_preview"></div>');
        jqOutputGrid.appendTo(pairSlot);
    }

    // Fill the grids first
    fillJqGridWithData(jqInputGrid, inputGrid);
    fillJqGridWithData(jqOutputGrid, outputGrid);

    // Define fixed, smaller constraints for the preview grids.
    const previewConstraint = 150; // Use 150x150 box constraint

    // Fit cells using the fixed constraints.
    // fitCellsToContainer calculates the best proportional size within these bounds.
    fitCellsToContainer(jqInputGrid, inputGrid.height, inputGrid.width, previewConstraint, previewConstraint);
    fitCellsToContainer(jqOutputGrid, outputGrid.height, outputGrid.width, previewConstraint, previewConstraint);
}

// Loads a single task object into the UI (assumes username is validated and welcome screen is hidden)
function loadSingleTask(taskObject, taskName) {
    // Reset UI elements specific to a single task load
    resetTask(CURRENT_TASK_INDEX !== -1); // Pass true if navigating a list
    // Modal is removed, no need to hide it.

    try {
        train = taskObject['train'];
        test = taskObject['test'];
        if (!train || !test) {
            throw new Error("Task object missing 'train' or 'test' fields.");
        }
    } catch (e) {
        errorMsg(`Error processing task ${taskName}: ${e.message}`);
        // If loading the first task from a list fails, clear the list state
        if (CURRENT_TASK_INDEX === 0) {
            LOADED_TASK_LIST = [];
            CURRENT_TASK_INDEX = -1;
            $('#list_navigation').hide();
        }
        return; // Stop loading this task
    }


    // Load training pairs
    for (var i = 0; i < train.length; i++) {
        pair = train[i];
        values = pair['input'];
        input_grid = convertSerializedGridToGridObject(values)
        values = pair['output'];
        output_grid = convertSerializedGridToGridObject(values)
        fillPairPreview(i, input_grid, output_grid);
    }
    for (var i=0; i < test.length; i++) {
        pair = test[i];
        TEST_PAIRS.push(pair);
    }
    // Handle cases where there might be no test pairs
    if (TEST_PAIRS.length > 0 && TEST_PAIRS[0]['input']) {
        values = TEST_PAIRS[0]['input'];
        CURRENT_INPUT_GRID = convertSerializedGridToGridObject(values);
        fillTestInput(CURRENT_INPUT_GRID);
        CURRENT_TEST_PAIR_INDEX = 0;
        $('#current_test_input_id_display').html('1');
    } else {
        // No test pairs or invalid first test pair
        $('#evaluation_input').html(''); // Clear input grid display
        CURRENT_INPUT_GRID = new Grid(3, 3); // Reset grid
        CURRENT_TEST_PAIR_INDEX = -1; // Indicate no valid test index
         $('#current_test_input_id_display').html('0');
    }
    $('#total_test_input_count_display').html(test.length);


    // Update task name display using the task's ID if available
    display_task_name(taskObject.id || taskName); // Prefer task ID for display name

    // Update list navigation UI
    updateListNavigationUI();

    // Request traces from server for this task
    const taskId = taskObject.id;
    if (socket && socket.connected && taskId) {
        console.log(`Requesting traces for task ID: ${taskId}`);
        socket.emit('request_traces', { task_id: taskId });
    } else if (!taskId) {
        console.warn("Cannot request traces: Task ID is missing.");
        // Proceed without server-side traces for this task
        displayTraces(); // Display local/empty traces
    } else {
        console.error("Cannot request traces: WebSocket not connected.");
        errorMsg("Not connected to real-time server. Cannot load traces.");
        // Proceed without server-side traces for this task
        displayTraces(); // Display local/empty traces
    }

    // Note: displayTraces() will now be primarily triggered by the 'initial_traces' event handler
    // The comment section is shown after successful load, trace display handled by displayTraces/socket events
    $('#comment_section').show(); // Ensure comment section is visible for the loaded task
    $('#comment_display_area').text('Loading traces...'); // Placeholder until socket response
    $('#comment_score_display').text('-'); // Placeholder
    $('#comment_nav_display').text('Trace -/-');
    $('#prev_comment_btn').prop('disabled', true);
    $('#next_comment_btn').prop('disabled', true);
    $('#upvote_btn').prop('disabled', true);
    $('#downvote_btn').prop('disabled', true);

    // Update distance display for the newly loaded task/test pair
    // updateDistanceDisplay(); // Moved to applyAndDisplayTransformations
}


// --- Transformation Logic ---

// Applies selected transformations to the ORIGINAL_TASK_DATA and updates the UI
function applyAndDisplayTransformations() {
    if (!ORIGINAL_TASK_DATA) {
        console.log("applyAndDisplayTransformations called but no ORIGINAL_TASK_DATA exists.");
        return; // No original data to transform
    }

    console.log("Applying transformations...");

    // Create a deep copy to avoid modifying the original
    let transformedData = JSON.parse(JSON.stringify(ORIGINAL_TASK_DATA));

    // Get checkbox states
    const doTranspose = $('#transform_transpose').is(':checked');
    const doReflectV = $('#transform_reflect_v').is(':checked');
    const doReflectH = $('#transform_reflect_h').is(':checked');
    const doSwapTrain0Test0 = $('#transform_swap_train0_test0').is(':checked');
    const doSwapTrain1Test0 = $('#transform_swap_train1_test0').is(':checked');

    // Helper to apply grid transformations sequentially
    function transformGrid(grid) {
        let currentGrid = grid;
        if (doTranspose) {
            currentGrid = transposeGrid(currentGrid);
        }
        if (doReflectV) {
            currentGrid = reflectGridVertical(currentGrid);
        }
        if (doReflectH) {
            currentGrid = reflectGridHorizontal(currentGrid);
        }
        return currentGrid;
    }

    // Apply grid transformations to all inputs and outputs
    transformedData.train.forEach(pair => {
        if (pair.input) pair.input = transformGrid(pair.input);
        if (pair.output) pair.output = transformGrid(pair.output);
    });
    transformedData.test.forEach(pair => {
        if (pair.input) pair.input = transformGrid(pair.input);
        if (pair.output) pair.output = transformGrid(pair.output);
    });

    // Apply swap transformations (careful with indices and potential double-swaps)
    let test0_exists = transformedData.test.length > 0;
    let train0_exists = transformedData.train.length > 0;
    let train1_exists = transformedData.train.length > 1;

    if (doSwapTrain0Test0 && train0_exists && test0_exists) {
        console.log("Swapping train[0] and test[0]");
        [transformedData.train[0], transformedData.test[0]] = [transformedData.test[0], transformedData.train[0]];
        // After this swap, train[1] might now be at index 0 if test[0] was originally train[1] due to the *next* swap.
        // Re-evaluate existence for the second swap based on the *current* state.
        train1_exists = transformedData.train.length > 1; // Recheck train1 existence
    }

    if (doSwapTrain1Test0 && train1_exists && test0_exists) {
        console.log("Swapping train[1] and test[0]");
         // Ensure test[0] wasn't originally train[0] from the previous swap if both are checked
        if (doSwapTrain0Test0 && transformedData.test[0] === ORIGINAL_TASK_DATA.train[0]) {
             // If both swaps active, test[0] is now original train[0].
             // We want to swap original train[1] with original train[0].
             // Original train[1] is still at transformedData.train[1].
             // Original train[0] is now at transformedData.test[0].
             [transformedData.train[1], transformedData.test[0]] = [transformedData.test[0], transformedData.train[1]];
        } else {
            // Only swap train[1] <-> test[0] is active, or test[0] wasn't affected by first swap.
            [transformedData.train[1], transformedData.test[0]] = [transformedData.test[0], transformedData.train[1]];
        }
    }


    // Update displayed data state
    DISPLAYED_TASK_DATA = transformedData;
    DISPLAYED_TRAIN_PAIRS = DISPLAYED_TASK_DATA.train || [];
    DISPLAYED_TEST_PAIRS = DISPLAYED_TASK_DATA.test || [];

    // --- Update UI based on DISPLAYED data ---

    // Update training pair previews
    $('#task_preview').html(''); // Clear previous previews
    for (let i = 0; i < DISPLAYED_TRAIN_PAIRS.length; i++) {
        const pair = DISPLAYED_TRAIN_PAIRS[i];
        // Ensure pair has input/output before trying to convert
        if (pair && pair.input && pair.output) {
            const input_grid = convertSerializedGridToGridObject(pair.input);
            const output_grid = convertSerializedGridToGridObject(pair.output);
            fillPairPreview(i, input_grid, output_grid);
        } else {
             console.warn(`Skipping display of train pair ${i} due to missing input/output after transformation.`);
        }
    }

    // Update test input display (resetting index to 0)
    CURRENT_TEST_PAIR_INDEX = 0; // Reset to first test pair after transform
    if (DISPLAYED_TEST_PAIRS.length > 0 && DISPLAYED_TEST_PAIRS[0] && DISPLAYED_TEST_PAIRS[0]['input']) {
        CURRENT_INPUT_GRID = convertSerializedGridToGridObject(DISPLAYED_TEST_PAIRS[0]['input']);
        fillTestInput(CURRENT_INPUT_GRID);
        $('#current_test_input_id_display').html('1');
    } else {
        // No test pairs or invalid first test pair after transform
        $('#evaluation_input').html(''); // Clear input grid display
        CURRENT_INPUT_GRID = new Grid(3, 3); // Reset grid
        CURRENT_TEST_PAIR_INDEX = -1; // Indicate no valid test index
        $('#current_test_input_id_display').html('0');
    }
    $('#total_test_input_count_display').html(DISPLAYED_TEST_PAIRS.length);

    // Reset the output grid for the user
    resetOutputGrid(); // Crucial to clear previous attempt

    // Update distance display for the new state
    updateDistanceDisplay();

    console.log("Transformations applied and UI updated.");
}


// New function to load a specific task version by ID and version index
function loadSingleTaskByIdAndVersion(taskId, versionIndex) {
    if (!TASK_VERSIONS_MAP[taskId] || versionIndex < 0 || versionIndex >= TASK_VERSIONS_MAP[taskId].length) {
        errorMsg(`Error: Task ID '${taskId}' version index ${versionIndex} not found.`);
        return;
    }

    const taskObject = TASK_VERSIONS_MAP[taskId][versionIndex];
    const taskVersion = taskObject.version !== undefined ? taskObject.version : 'N/A'; // Get version number

    // Reset UI elements specific to a single task load (but not full dataset reset)
    resetTask(false); // Pass false for isDatasetLoad

    CURRENT_TASK_ID = taskId;
    CURRENT_VERSION_INDEX = versionIndex;

    try {
        // Store the original data (deep copy)
        ORIGINAL_TASK_DATA = JSON.parse(JSON.stringify(taskObject));

        // Apply transformations (if any checked) and update the display
        applyAndDisplayTransformations(); // This now handles loading train/test pairs into UI

        // Update task name, task navigation, and version navigation displays
        updateNavigationDisplays();

        // Request traces from server for this task ID (consistent across versions)
        if (socket && socket.connected && taskId) {
            console.log(`Requesting traces for task ID: ${taskId}`);
            socket.emit('request_traces', { task_id: taskId });
            $('#comment_display_area').text('Loading traces...'); // Placeholder
        } else if (!taskId) {
            console.warn("Cannot request traces: Task ID is missing.");
            displayTraces(); // Display local/empty traces
        } else {
            console.error("Cannot request traces: WebSocket not connected.");
            errorMsg("Not connected to real-time server. Cannot load traces.");
            displayTraces(); // Display local/empty traces
        }

        $('#comment_section').show(); // Show comment section for the loaded task
        // updateDistanceDisplay(); // Called within applyAndDisplayTransformations

        // --- Persist state on successful load ---
        try {
            sessionStorage.setItem('currentTaskId', CURRENT_TASK_ID);
            sessionStorage.setItem('currentVersionIndex', CURRENT_VERSION_INDEX.toString()); // Store as string
            sessionStorage.setItem('currentDatasetName', CURRENT_DATASET_NAME); // Store dataset name too
            console.log(`Stored state: Task=${CURRENT_TASK_ID}, VersionIndex=${CURRENT_VERSION_INDEX}, Dataset=${CURRENT_DATASET_NAME}`);
        } catch (storageError) {
            console.error("Failed to save state to sessionStorage:", storageError);
            // Non-critical error, maybe inform user? For now, just log.
        }
        // --- End Persist state ---

    } catch (e) {
        errorMsg(`Error processing task ${taskId} version ${taskVersion}: ${e.message}`);
        // Optionally reset further UI elements if loading fails critically
        ORIGINAL_TASK_DATA = null; // Clear original data on error too
        DISPLAYED_TASK_DATA = null;
        CURRENT_TASK_ID = null;
        CURRENT_VERSION_INDEX = -1;
        $('#comment_section').hide();
        updateNavigationDisplays(); // Update displays to reflect failed load
    }
}


// Updated function to handle task name, task index, and version display
function updateNavigationDisplays() {
    // Task Name and Version Display
    let displayName = CURRENT_TASK_ID || "No Task Loaded";
    let versionText = "";
    let taskIndexText = "";

    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID] && CURRENT_VERSION_INDEX !== -1) {
        const currentVersionObject = TASK_VERSIONS_MAP[CURRENT_TASK_ID][CURRENT_VERSION_INDEX];
        const versionNum = currentVersionObject.version !== undefined ? currentVersionObject.version : '?';
        versionText = ` (Version ${versionNum})`;
    }

    // Task Index Display (based on unique IDs)
    if (CURRENT_TASK_ID && UNIQUE_TASK_IDS.length > 0) {
        const uniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        if (uniqueIndex !== -1) {
            taskIndexText = ` (Task ${uniqueIndex + 1}/${UNIQUE_TASK_IDS.length})`;
        }
    }
    $('#task_name').html(`Task name:&nbsp;&nbsp;&nbsp;&nbsp;${displayName}${versionText}${taskIndexText}`);

    // Task List Navigation UI
    if (UNIQUE_TASK_IDS.length > 0 && CURRENT_TASK_ID) {
        const uniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        $('#list_navigation').show();
        $('#goto_id_controls').show();
        $('#goto_task_number_controls').show(); // Show task number controls too
        $('#task_index_display').text(`Task ${uniqueIndex + 1}/${UNIQUE_TASK_IDS.length}`);
        $('#prev_task_btn').prop('disabled', uniqueIndex === 0);
        $('#next_task_btn').prop('disabled', uniqueIndex === UNIQUE_TASK_IDS.length - 1);
    } else {
        $('#list_navigation').hide();
        $('#goto_id_controls').hide();
        $('#goto_task_number_controls').hide(); // Hide task number controls too
    }

    // Version Navigation UI
    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const versions = TASK_VERSIONS_MAP[CURRENT_TASK_ID];
        const totalVersions = versions.length;
        // Always show the version navigation if a task with versions is loaded
        $('#version_navigation').show();
        $('#version_display').text(`Ver ${CURRENT_VERSION_INDEX + 1}/${totalVersions}`);
        // Disable buttons appropriately based on index and total count
        $('#prev_version_btn').prop('disabled', CURRENT_VERSION_INDEX === 0);
        $('#next_version_btn').prop('disabled', CURRENT_VERSION_INDEX === totalVersions - 1);
    } else {
        // Hide if no task or versions map entry exists
        $('#version_navigation').hide();
    }
}


// --- Trace Functions --- // (No changes needed here for versioning, relies on task_id)
// ... displayTraces, previousTrace, nextTrace, upvoteTrace, downvoteTrace, voteOnTrace, addTrace ...

// --- Download Data ---

// --- Trace Functions --- // Renamed section

function displayTraces() { // Renamed function
    // Find the task object using the CURRENT_TASK_ID
    const currentTask = LOADED_TASK_LIST.find(task => task.id === CURRENT_TASK_ID);

    if (!currentTask) {
        $('#comment_section').hide(); // Hide if no task loaded or found
        // Clear previous trace display
        $('#comment_display_area').text('No task loaded.');
        $('#comment_score_display').text('0');
        $('#comment_nav_display').text('Trace 0/0');
        $('#prev_comment_btn').prop('disabled', true);
        $('#next_comment_btn').prop('disabled', true);
        $('#upvote_btn').prop('disabled', true);
        $('#downvote_btn').prop('disabled', true);
        return;
    }

    // Ensure 'comments' array exists (it should have been initialized in loadDataset or by socket)
    if (!currentTask.comments) {
        currentTask.comments = []; // Initialize if missing
    }

    // Sort traces by score descending (highest first)
    const sortedTraces = [...currentTask.comments].sort((a, b) => {
        if (b.score !== a.score) {
            return b.score - a.score;
        }
        // Optional: tie-break by timestamp (newest first)
        // return (b.timestamp || 0) - (a.timestamp || 0);
        return 0; // Default: maintain original order on tie
    });

    const totalTraces = sortedTraces.length;

    if (totalTraces === 0) {
        $('#comment_display_area').text('No reasoning traces added yet.');
        $('#comment_score_display').text('0');
        $('#comment_nav_display').text('Trace 0/0');
        $('#prev_comment_btn').prop('disabled', true);
        $('#next_comment_btn').prop('disabled', true);
        $('#upvote_btn').prop('disabled', true);
        $('#downvote_btn').prop('disabled', true);
    } else {
        // Ensure current trace index is valid
        if (CURRENT_TRACE_INDEX >= totalTraces) {
            CURRENT_TRACE_INDEX = totalTraces - 1;
        }
        if (CURRENT_TRACE_INDEX < 0) {
            CURRENT_TRACE_INDEX = 0;
        }

        const traceToShow = sortedTraces[CURRENT_TRACE_INDEX];
        // Display trace text, score, and potentially username
        let traceHtml = $('<div>').text(traceToShow.text || '').html(); // Basic text display, escape HTML
        if (traceToShow.username) {
             traceHtml += `<br><span style="font-size: 0.8em; color: #555;"> - ${$('<div>').text(traceToShow.username).html()}</span>`; // Display username safely
        }
        $('#comment_display_area').html(traceHtml); // Use .html() to render the break and span
        $('#comment_score_display').text(traceToShow.score || 0);
        $('#comment_nav_display').text(`Trace ${CURRENT_TRACE_INDEX + 1}/${totalTraces}`);

        // Enable/disable navigation buttons
        $('#prev_comment_btn').prop('disabled', CURRENT_TRACE_INDEX === 0);
        $('#next_comment_btn').prop('disabled', CURRENT_TRACE_INDEX === totalTraces - 1);
        // Enable voting buttons
        $('#upvote_btn').prop('disabled', false);
        $('#downvote_btn').prop('disabled', false);
    }

    $('#comment_section').show(); // Make sure section is visible
}

function previousTrace() { // Renamed function
    // Check if a task is loaded (implicitly checks CURRENT_TASK_ID)
    const currentTask = LOADED_TASK_LIST.find(task => task.id === CURRENT_TASK_ID);
    if (!currentTask) return;

    if (CURRENT_TRACE_INDEX > 0) {
        CURRENT_TRACE_INDEX--;
        displayTraces(); // Call renamed function
    }
}

function nextTrace() { // Renamed function
    // Check if a task is loaded
    const currentTask = LOADED_TASK_LIST.find(task => task.id === CURRENT_TASK_ID);
    if (!currentTask) return;

    const totalTraces = currentTask.comments ? currentTask.comments.length : 0;

    if (CURRENT_TRACE_INDEX < totalTraces - 1) {
        CURRENT_TRACE_INDEX++;
        displayTraces(); // Call renamed function
    }
}

function upvoteTrace() { // Renamed function
    voteOnTrace(1);
}

function downvoteTrace() { // Renamed function
    voteOnTrace(-1);
}

function voteOnTrace(voteChange) { // Renamed function
    // Find the task object using the CURRENT_TASK_ID
    const currentTask = LOADED_TASK_LIST.find(task => task.id === CURRENT_TASK_ID);
    if (!currentTask || !currentTask.comments || currentTask.comments.length === 0) {
        errorMsg("Cannot vote: No task or traces loaded.");
        return;
    }

    // Get the currently displayed trace based on the sorted order.
    // Ensure comments array exists before sorting
    const sortedTraces = [...(currentTask.comments || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
    if (CURRENT_TRACE_INDEX >= sortedTraces.length) return; // Index out of bounds

    const displayedTraceObject = sortedTraces[CURRENT_TRACE_INDEX];

    // Find this trace in the original task.comments array using its unique ID
    // This relies on the server sending back a unique 'trace_id'
    const originalTrace = currentTask.comments.find(c => c.trace_id === displayedTraceObject.trace_id);

    if (originalTrace) {
        // Emit vote event to server instead of changing locally
        if (socket && socket.connected) {
            console.log(`Emitting vote_trace: trace_id=${originalTrace.trace_id}, username=${USERNAME}, vote=${voteChange}`);
            socket.emit('vote_trace', {
                trace_id: originalTrace.trace_id,
                username: USERNAME,
                vote: voteChange
            });
            // Optionally disable buttons temporarily until update received
            $('#upvote_btn').prop('disabled', true);
            $('#downvote_btn').prop('disabled', true);
        } else {
            errorMsg("Cannot vote: Not connected to real-time server.");
        }
    } else {
        // This case might happen if the trace_id isn't set correctly yet
        console.error("Could not find the original trace to vote on. Displayed Object:", displayedTraceObject);
        errorMsg("Error applying vote: Trace not found locally (might be missing ID).");
    }
}


function addTrace() { // Renamed function
    // Username check is still relevant here before sending to server
    if (!USERNAME || USERNAME === "Anonymous") {
         errorMsg("Please enter a valid username before adding a trace.");
         $('#username_input').focus();
         return;
     }

    // Find the task object using the CURRENT_TASK_ID
    const currentTask = LOADED_TASK_LIST.find(task => task.id === CURRENT_TASK_ID);
    if (!currentTask) {
        errorMsg("No task loaded to add a reasoning trace to.");
        return;
    }
    const taskId = currentTask.id; // Get task ID from the found task object

    const traceText = $('#new_comment_text').val().trim();
    if (!traceText) {
        errorMsg("Reasoning trace cannot be empty.");
        return;
    }

    // Emit add_trace event to server
    if (socket && socket.connected) {
         console.log(`Emitting add_trace: task_id=${taskId}, username=${USERNAME}, text=${traceText}`);
         socket.emit('add_trace', {
             task_id: taskId,
             username: USERNAME,
             text: traceText
         });
         $('#new_comment_text').val(''); // Clear textarea immediately
         infoMsg("Submitting reasoning trace..."); // Give feedback
    } else {
         errorMsg("Cannot add trace: Not connected to real-time server.");
    }
    // Don't add locally or refresh display, wait for broadcast
}

function removeCurrentTrace() {
    // Username check
    if (!USERNAME || USERNAME === "Anonymous") {
        errorMsg("Please enter a valid username before removing a trace.");
        $('#username_input').focus();
        return;
    }

    // Find the task object using the CURRENT_TASK_ID
    const currentTask = LOADED_TASK_LIST.find(task => task.id === CURRENT_TASK_ID);
    if (!currentTask || !currentTask.comments || currentTask.comments.length === 0) {
        errorMsg("No traces available to remove.");
        return;
    }

    // Get the currently displayed trace based on the sorted order
    const sortedTraces = [...(currentTask.comments || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
    if (CURRENT_TRACE_INDEX >= sortedTraces.length) {
        errorMsg("No trace selected to remove.");
        return;
    }

    const displayedTraceObject = sortedTraces[CURRENT_TRACE_INDEX];
    
    // Password prompt
    const password = prompt("Enter password to remove this trace:", "");
    if (password !== "remove") {
        errorMsg("Incorrect password. Trace not removed.");
        return;
    }

    // Find this trace in the original task.comments array using its unique ID
    const originalTrace = currentTask.comments.find(c => c.trace_id === displayedTraceObject.trace_id);
    if (!originalTrace) {
        errorMsg("Error: Could not find the trace to remove.");
        return;
    }

    // Emit remove_trace event to server
    if (socket && socket.connected) {
        console.log(`Emitting remove_trace: trace_id=${originalTrace.trace_id}, username=${USERNAME}`);
        socket.emit('remove_trace', {
            trace_id: originalTrace.trace_id,
            task_id: currentTask.id,
            username: USERNAME
        });
        infoMsg("Removing trace..."); // Give feedback
        $('#remove_trace_btn').prop('disabled', true); // Prevent double-clicks
    } else {
        errorMsg("Cannot remove trace: Not connected to real-time server.");
    }
}

function downloadData() {
    if (!LOADED_TASK_LIST || LOADED_TASK_LIST.length === 0) {
        errorMsg("No dataset loaded to download.");
        return;
    }

    try {
        // Use a deep copy to avoid modifying the original data if needed later,
        const dataToDownload = JSON.parse(JSON.stringify(LOADED_TASK_LIST));

        // Convert the data (which includes traces) to a JSON string
        const jsonString = JSON.stringify(dataToDownload, null, 2); // Use indentation for readability

        // Create a Blob object
        const blob = new Blob([jsonString], { type: 'application/json' });

        // Create a temporary download link
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);

        // Set the filename for the download (using 'dataset' as it's now unified)
        const filename = `dataset_with_traces.json`;
        link.download = filename;

        // Programmatically click the link to trigger the download
        document.body.appendChild(link); // Required for Firefox
        link.click();

        // Clean up the temporary link
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href); // Free up memory

        infoMsg(`Dataset with traces ('${filename}') download initiated.`); // Update message

    } catch (e) {
        console.error("Error preparing data for download:", e);
        errorMsg("Failed to prepare data for download.");
    }
}


// --- End Trace Functions --- // Renamed section


// Removed loadTaskFromFile function

function loadDataset(datasetName) {
    // --- Username Check ---
    if (!USERNAME || USERNAME === "Anonymous") {
        $('#username_error').show(); // Show the error message near the username input
        $('#username_input').focus(); // Focus the input
        // Do not proceed with loading
        return;
    } else {
        $('#username_error').hide(); // Hide error if username is provided
        // Save username to cookie (e.g., for 30 days)
        setCookie('username', USERNAME, 30);
        console.log("Username saved to cookie:", USERNAME);
    }
    // --- End Username Check ---

    // Prevent reloading the same dataset unnecessarily
    if (CURRENT_DATASET_NAME === datasetName && LOADED_TASK_LIST.length > 0) {
        infoMsg(`Dataset '${datasetName}' is already loaded.`);
        return; // Already loaded, no need to proceed
    }

    console.log(`Attempting to load dataset: ${datasetName} with username: ${USERNAME}`); // Add log
    resetTask(); // Full reset before loading new dataset
    CURRENT_DATASET_NAME = datasetName; // Set dataset name early for potential error messages
    // Use the unified dataset name 'dataset'
    const filename = `dataset.json`;
    const serverRoute = `/data/${filename}`; // Path for Flask server route

    infoMsg(`Loading dataset '${filename}'...`);
    errorMsg('');
    $('#loaded_dataset_display').text(`Loading ${filename}...`);
    console.log(`Fetching data from ${serverRoute}...`);

    $.ajax({
        url: serverRoute,
        dataType: 'json',
        success: function(data) {
            console.log(`Successfully fetched data from ${filename}. Processing...`);
            if (!Array.isArray(data)) {
                console.error(`Data from ${serverRoute} is not an array.`);
                errorMsg(`Error: Dataset file '${filename}' does not contain a valid JSON list.`);
                resetTask(true); // Full reset
                $('#loaded_dataset_display').text(`Failed: Invalid format`);
                return;
            }
            if (data.length === 0) {
                console.warn(`Data from ${serverRoute} is an empty array.`);
                // Allow loading empty dataset, but show message
                infoMsg(`Warning: Dataset '${filename}' is empty.`);
                resetTask(true); // Full reset
                LOADED_TASK_LIST = [];
                TASK_VERSIONS_MAP = {};
                UNIQUE_TASK_IDS = [];
                CURRENT_DATASET_NAME = 'dataset'; // Still mark as loaded
                $('#loaded_dataset_display').text(`Loaded: ${filename} (Empty)`);
                // Hide welcome, show main (but nothing will load)
                $('#welcome_screen').hide();
                $('#demonstration_examples_view').show();
                $('#evaluation_view').show();
                updateNavigationDisplays(); // Update UI to show no tasks
                return;
            }

            console.log(`Dataset ${filename} has ${data.length} entries. Building version map...`);
            resetTask(true); // Full reset before populating
            LOADED_TASK_LIST = data; // Store raw data
            CURRENT_DATASET_NAME = 'dataset'; // Set dataset name

            // Build the TASK_VERSIONS_MAP and UNIQUE_TASK_IDS
            TASK_VERSIONS_MAP = {};
            UNIQUE_TASK_IDS = [];
            const idSet = new Set(); // To track unique IDs in order of appearance

            LOADED_TASK_LIST.forEach((task, index) => {
                // Ensure required fields exist
                if (!task || typeof task !== 'object') {
                    console.warn(`Skipping invalid entry at index ${index} in ${filename}.`);
                    return;
                }
                const taskId = task.id;
                const taskVersion = task.version !== undefined ? parseInt(task.version, 10) : 0; // Default to 0, ensure int

                if (!taskId) {
                    console.warn(`Task entry at index ${index} in ${filename} is missing an 'id' field. Skipping.`);
                    return;
                }
                 // Ensure version is a non-negative integer
                if (isNaN(taskVersion) || taskVersion < 0) {
                    console.warn(`Task entry '${taskId}' at index ${index} has invalid version '${task.version}'. Skipping.`);
                    return;
                }
                task.version = taskVersion; // Store the parsed version back

                // Initialize comments array (will be populated by WebSocket)
                task.comments = [];

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

            // --- Hide Welcome, Show Main Content ---
            $('#welcome_screen').hide();
            $('#demonstration_examples_view').show();
            $('#evaluation_view').show();
            console.log(`Hid welcome screen and showed main content for ${filename}.`);

            // --- Load Task (Check for Pending State First) ---
            let taskLoaded = false;
            if (pendingTaskId && pendingVersionIndex !== null && TASK_VERSIONS_MAP.hasOwnProperty(pendingTaskId) && pendingVersionIndex >= 0 && pendingVersionIndex < TASK_VERSIONS_MAP[pendingTaskId].length) {
                console.log(`Attempting to load pending state: Task=${pendingTaskId}, VersionIndex=${pendingVersionIndex}`);
                try {
                    loadSingleTaskByIdAndVersion(pendingTaskId, pendingVersionIndex);
                    infoMsg(`Restored session for task ID: ${pendingTaskId}`);
                    $('#loaded_dataset_display').text(`Loaded: ${filename}`);
                    taskLoaded = true;
                } catch (loadError) {
                    console.error("Error loading pending task state:", loadError);
                    errorMsg(`Failed to restore previous task (${pendingTaskId}). Loading first task instead.`);
                    // Clear bad pending state from session storage
                    sessionStorage.removeItem('currentTaskId');
                    sessionStorage.removeItem('currentVersionIndex');
                    sessionStorage.removeItem('currentDatasetName');
                }
            } else if (pendingTaskId) {
                console.warn(`Pending task ID ${pendingTaskId} or version ${pendingVersionIndex} not found in loaded dataset. Loading first task.`);
                errorMsg(`Previous task (${pendingTaskId}) not found. Loading first task instead.`);
                 // Clear bad pending state from session storage
                 sessionStorage.removeItem('currentTaskId');
                 sessionStorage.removeItem('currentVersionIndex');
                 sessionStorage.removeItem('currentDatasetName');
            }

            // Clear pending state variables regardless of success/failure
            pendingTaskId = null;
            pendingVersionIndex = null;
            pendingDatasetName = null; // This was already set to CURRENT_DATASET_NAME

            // If no task was loaded via pending state, load the default first task
            if (!taskLoaded) {
                if (UNIQUE_TASK_IDS.length > 0) {
                    const firstTaskId = UNIQUE_TASK_IDS[0];
                    console.log("Loading default first task:", firstTaskId);
                    loadSingleTaskByIdAndVersion(firstTaskId, 0); // Load version 0 (index 0 after sort)
                    infoMsg(`Successfully loaded ${UNIQUE_TASK_IDS.length} unique tasks from '${filename}'.`);
                    $('#loaded_dataset_display').text(`Loaded: ${filename}`);
                } else {
                    // Handle case where dataset had entries but none were valid tasks with IDs/versions
                    errorMsg(`Dataset '${filename}' loaded, but no valid tasks with IDs found.`);
                    $('#loaded_dataset_display').text(`Loaded: ${filename} (No valid tasks)`);
                    updateNavigationDisplays(); // Update UI to show no tasks
                }
            }
            // --- End Load Task ---

            // WebSocket connection should already be established
            // loadSingleTaskByIdAndVersion will emit 'request_traces'
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error(`Failed to load data ${serverRoute}. Status: ${textStatus}, Error: ${errorThrown}`, jqXHR);
            errorMsg(`Failed to load dataset '${filename}'. Check server logs. Status: ${textStatus}.`);
            resetTask(true); // Full reset
            $('#loaded_dataset_display').text(`Failed to load ${filename}`);
            // Stay on welcome screen on error
        }
    });
}


// Navigate through UNIQUE_TASK_IDS
function randomTask() {
    if (UNIQUE_TASK_IDS.length > 0) {
        let currentUniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        let randomUniqueIndex = Math.floor(Math.random() * UNIQUE_TASK_IDS.length);
        // Avoid picking the same task ID consecutively if possible
        if (UNIQUE_TASK_IDS.length > 1 && randomUniqueIndex === currentUniqueIndex) {
            randomUniqueIndex = (randomUniqueIndex + 1) % UNIQUE_TASK_IDS.length;
        }
        const newTaskId = UNIQUE_TASK_IDS[randomUniqueIndex];
        loadSingleTaskByIdAndVersion(newTaskId, 0); // Load first version of the new task ID
        infoMsg(`Loaded random task ID: ${newTaskId} (Task ${randomUniqueIndex + 1}/${UNIQUE_TASK_IDS.length})`);
    } else {
        errorMsg("Please load a dataset with valid tasks first.");
    }
}

// Navigate through UNIQUE_TASK_IDS
function previousTask() {
    if (CURRENT_TASK_ID && UNIQUE_TASK_IDS.length > 0) {
        const currentUniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        if (currentUniqueIndex > 0) {
            const newTaskId = UNIQUE_TASK_IDS[currentUniqueIndex - 1];
            loadSingleTaskByIdAndVersion(newTaskId, 0); // Load first version
        }
    }
}

// Navigate through UNIQUE_TASK_IDS
function nextTask() {
     if (CURRENT_TASK_ID && UNIQUE_TASK_IDS.length > 0) {
        const currentUniqueIndex = UNIQUE_TASK_IDS.indexOf(CURRENT_TASK_ID);
        if (currentUniqueIndex < UNIQUE_TASK_IDS.length - 1) {
            const newTaskId = UNIQUE_TASK_IDS[currentUniqueIndex + 1];
            loadSingleTaskByIdAndVersion(newTaskId, 0); // Load first version
        }
    }
}

// Navigate to a specific Task ID (loads first version)
function gotoTaskById() {
    const taskIdToFind = $('#task_id_input').val().trim();
    if (!taskIdToFind) {
        errorMsg("Please enter a Task ID.");
        return;
    }

    if (TASK_VERSIONS_MAP.hasOwnProperty(taskIdToFind)) {
        if (taskIdToFind !== CURRENT_TASK_ID) {
            loadSingleTaskByIdAndVersion(taskIdToFind, 0); // Load first version
            infoMsg(`Navigated to task ID: ${taskIdToFind}`);
            $('#task_id_input').val(''); // Clear input on success
        } else {
            infoMsg(`Already viewing task ID: ${taskIdToFind}. Use version buttons to navigate versions.`);
        }
    } else {
        errorMsg(`Task ID '${taskIdToFind}' not found in the current dataset.`);
    }
}

// Navigate to a specific Task by its 1-based index in the unique list
function gotoTaskByNumber() {
    const taskNumberInput = $('#task_number_input');
    const taskNumberStr = taskNumberInput.val().trim();
    if (!taskNumberStr) {
        errorMsg("Please enter a Task Number.");
        return;
    }

    const taskNumber = parseInt(taskNumberStr, 10);

    if (isNaN(taskNumber)) {
        errorMsg("Invalid Task Number entered.");
        return;
    }

    if (!UNIQUE_TASK_IDS || UNIQUE_TASK_IDS.length === 0) {
        errorMsg("No tasks loaded to navigate by number.");
        return;
    }

    const totalTasks = UNIQUE_TASK_IDS.length;
    if (taskNumber < 1 || taskNumber > totalTasks) {
        errorMsg(`Task Number must be between 1 and ${totalTasks}.`);
        return;
    }

    const taskIndex = taskNumber - 1; // Convert 1-based input to 0-based index
    const taskIdToGo = UNIQUE_TASK_IDS[taskIndex];

    if (taskIdToGo === CURRENT_TASK_ID) {
        infoMsg(`Already viewing Task #${taskNumber} (ID: ${taskIdToGo}).`);
    } else {
        loadSingleTaskByIdAndVersion(taskIdToGo, 0); // Load first version
        infoMsg(`Navigated to Task #${taskNumber} (ID: ${taskIdToGo})`);
        taskNumberInput.val(''); // Clear input on success
    }
}


// --- New Version Navigation Functions ---

function previousVersion() {
    if (CURRENT_TASK_ID && CURRENT_VERSION_INDEX > 0) {
        loadSingleTaskByIdAndVersion(CURRENT_TASK_ID, CURRENT_VERSION_INDEX - 1);
    }
}

function nextVersion() {
    if (CURRENT_TASK_ID && TASK_VERSIONS_MAP[CURRENT_TASK_ID]) {
        const totalVersions = TASK_VERSIONS_MAP[CURRENT_TASK_ID].length;
        if (CURRENT_VERSION_INDEX < totalVersions - 1) {
            loadSingleTaskByIdAndVersion(CURRENT_TASK_ID, CURRENT_VERSION_INDEX + 1);
        }
    }
}

// --- End Version Navigation ---


function nextTestInput() {
    if (DISPLAYED_TEST_PAIRS.length <= CURRENT_TEST_PAIR_INDEX + 1) {
        errorMsg('No next test input.') // Removed suggestion to pick another file
        return
    }
    CURRENT_TEST_PAIR_INDEX += 1;
    // Load input from the (potentially transformed) displayed test pairs
    if (DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX] && DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX]['input']) {
        values = DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX]['input'];
        CURRENT_INPUT_GRID = convertSerializedGridToGridObject(values)
        fillTestInput(CURRENT_INPUT_GRID);
        $('#current_test_input_id_display').html(CURRENT_TEST_PAIR_INDEX + 1);
        // Reset the output grid when moving to the next test input
        resetOutputGrid();
        updateDistanceDisplay(); // Update distance for the new test input
    } else {
        errorMsg(`Error loading next test input (index ${CURRENT_TEST_PAIR_INDEX}). Data might be corrupted.`);
        // Attempt to recover or stay put? For now, just log error.
        CURRENT_TEST_PAIR_INDEX -=1; // Revert index change
    }
}

function submitSolution() {
    // Ensure we have a valid test pair index and data
    if (CURRENT_TEST_PAIR_INDEX < 0 || CURRENT_TEST_PAIR_INDEX >= DISPLAYED_TEST_PAIRS.length || !DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX] || !DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX]['output']) {
        errorMsg('Cannot submit: No valid test solution data available.');
        return;
    }

    syncFromEditionGridToDataGrid();
    // Compare against the output from the (potentially transformed) displayed test pair
    reference_output = DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX]['output'];
    submitted_output = CURRENT_OUTPUT_GRID.grid;

    // Compare dimensions first
    if (!reference_output || !submitted_output || reference_output.length !== submitted_output.length || (reference_output.length > 0 && (!reference_output[0] || !submitted_output[0] || reference_output[0].length !== submitted_output[0].length))) {
         errorMsg('Wrong solution dimensions.');
         return;
    }
    for (var i = 0; i < reference_output.length; i++){
        ref_row = reference_output[i];
        for (var j = 0; j < ref_row.length; j++){
            if (ref_row[j] != submitted_output[i][j]) {
                errorMsg('Wrong solution.');
                return
            }
        }
    }
    infoMsg('Correct solution!');
}

function fillTestInput(inputGrid) {
    jqInputGrid = $('#evaluation_input');
    fillJqGridWithData(jqInputGrid, inputGrid);
    // Get the actual container dimensions after filling data
    const containerHeight = jqInputGrid.height();
    const containerWidth = jqInputGrid.width();
    fitCellsToContainer(jqInputGrid, inputGrid.height, inputGrid.width, containerHeight, containerWidth);
}

function copyToOutput() {
    syncFromEditionGridToDataGrid();
    CURRENT_OUTPUT_GRID = convertSerializedGridToGridObject(CURRENT_INPUT_GRID.grid);
    syncFromDataGridToEditionGrid();
    $('#output_grid_size').val(CURRENT_OUTPUT_GRID.height + 'x' + CURRENT_OUTPUT_GRID.width);
}

function initializeSelectable() {
    try {
        $('.selectable_grid').selectable('destroy');
    }
    catch (e) {
    }
    toolMode = $('input[name=tool_switching]:checked').val();
    if (toolMode == 'select') {
        infoMsg('Select some cells and click on a color to fill in, or press C to copy');
        $('.selectable_grid').selectable(
            {
                autoRefresh: false,
                filter: '> .row > .cell',
                start: function(event, ui) {
                    $('.ui-selected').each(function(i, e) {
                        $(e).removeClass('ui-selected');
                    });
                }
            }
        );
    }
}


// --- Hamming Distance Calculation and Display ---

function calculateHammingDistance(grid1, grid2) {
    // Check if grids are valid arrays
    if (!Array.isArray(grid1) || !Array.isArray(grid2)) return Infinity;

    const h1 = grid1.length;
    const w1 = h1 > 0 ? grid1[0].length : 0;
    const h2 = grid2.length;
    const w2 = h2 > 0 ? grid2[0].length : 0;

    // Check for dimension mismatch or empty grids
    if (h1 !== h2 || w1 !== w2 || h1 === 0 || w1 === 0) {
        return Infinity;
    }

    let diff = 0;
    const totalPixels = h1 * w1;

    for (let i = 0; i < h1; i++) {
        // Ensure rows are arrays
        if (!Array.isArray(grid1[i]) || !Array.isArray(grid2[i])) return Infinity;
        for (let j = 0; j < w1; j++) {
            if (grid1[i][j] !== grid2[i][j]) {
                diff++;
            }
        }
    }

    return diff / totalPixels;
}

function updateDistanceDisplay() {
    const distanceSpan = $('#distance_value_display');
    // Check if we have valid DISPLAYED test pairs and a valid index
    if (!DISPLAYED_TEST_PAIRS || CURRENT_TEST_PAIR_INDEX < 0 || CURRENT_TEST_PAIR_INDEX >= DISPLAYED_TEST_PAIRS.length || !DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX] || !DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX]['output']) {
        distanceSpan.text('N/A'); // Not Applicable if no solution available
        return;
    }

    // Get the correct output from the (potentially transformed) displayed data
    const correctOutputGrid = DISPLAYED_TEST_PAIRS[CURRENT_TEST_PAIR_INDEX]['output'];
    // Ensure CURRENT_OUTPUT_GRID reflects the latest state of the UI grid
    syncFromEditionGridToDataGrid();
    const userOutputGrid = CURRENT_OUTPUT_GRID.grid;

    const distance = calculateHammingDistance(userOutputGrid, correctOutputGrid);

    if (distance === Infinity) {
        distanceSpan.text('Infinity (Size Mismatch)');
    } else {
        // Format to 2 decimal places for readability
        distanceSpan.text(distance.toFixed(2));
    }
}


function toggleDistanceDisplay() {
    const isChecked = $('#show_distance_toggle').prop('checked');
    const controlsDiv = $('#distance_display_controls');
    if (isChecked) {
        controlsDiv.removeClass('distance-hidden');
        updateDistanceDisplay(); // Update display immediately when shown
    } else {
        controlsDiv.addClass('distance-hidden');
    }
}

// --- WebSocket Connection & Event Handlers ---

function connectWebSocket() {
    // Connect to the Socket.IO server (adjust URL if server runs elsewhere)
    console.log("Attempting to connect WebSocket...");
    if (socket && socket.connected) {
        console.log("WebSocket already connected.");
        return;
    }
    // Connect to the server hosting the page, default port 5000
    socket = io(`http://${window.location.hostname}:5000`);

    socket.on('connect', () => {
        console.log('WebSocket connected successfully. SID:', socket.id);
        infoMsg('Connected to real-time server.');
    });

    socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason);
        errorMsg('Disconnected from real-time server. Refresh may be needed.');
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        errorMsg('Failed to connect to real-time server.');
    });

    socket.on('connection_ack', (data) => {
        console.log('Server Acknowledged Connection:', data.message);
    });

    socket.on('initial_traces', (data) => {
        console.log('Received initial_traces for task', data.task_id, ':', data.traces);
        // Find the task by ID in the loaded list
        const targetTask = LOADED_TASK_LIST.find(task => task.id === data.task_id);

        if (targetTask) {
            // Replace local comments with server data
            targetTask.comments = Array.isArray(data.traces) ? data.traces : [];
            console.log(`Updated traces for task ${data.task_id} locally.`);
            // If this is the currently viewed task, reset index and refresh display
            if (CURRENT_TASK_ID === data.task_id) {
                CURRENT_TRACE_INDEX = 0; // Reset view to the first trace
                displayTraces(); // Update the display
            }
        } else {
            console.log("Received initial_traces for a task not found in LOADED_TASK_LIST, ignoring.");
        }
    });

    socket.on('new_trace', (newTrace) => {
        console.log('Received new_trace:', newTrace);
        // Find the task in memory to add the trace to
        const targetTask = LOADED_TASK_LIST.find(task => task.id === newTrace.task_id);
        if (targetTask) {
             if (!targetTask.comments) targetTask.comments = [];
             // Avoid adding duplicates based on trace_id
             if (!targetTask.comments.some(c => c.trace_id === newTrace.trace_id)) {
                 targetTask.comments.push(newTrace);
                 console.log(`Added new trace ${newTrace.trace_id} to task ${newTrace.task_id} locally.`);
                 // If it's for the currently viewed task, refresh display
                 if (CURRENT_TASK_ID === newTrace.task_id) {
                     // Optionally decide whether to jump to the new trace or stay put
                     // CURRENT_TRACE_INDEX = targetTask.comments.length - 1; // Jump to new trace
                     displayTraces(); // Refresh display (will re-sort)
                 }
             } else {
                 console.log(`Duplicate new_trace message received (or trace already exists) for ${newTrace.trace_id}, ignoring.`);
             }
        } else {
            console.warn(`Received new_trace for unknown task_id ${newTrace.task_id}`);
        }
    });

    socket.on('trace_updated', (updatedInfo) => {
        console.log('Received trace_updated:', updatedInfo);
        // Find the task and trace in memory and update score
        const targetTask = LOADED_TASK_LIST.find(task => task.id === updatedInfo.task_id);
        if (targetTask && targetTask.comments) {
            const targetTrace = targetTask.comments.find(c => c.trace_id === updatedInfo.trace_id);
            if (targetTrace) {
                targetTrace.score = updatedInfo.score;
                // Optionally update voters if needed: targetTrace.voters = updatedInfo.voters;
                console.log(`Updated score for trace ${updatedInfo.trace_id} to ${updatedInfo.score} locally.`);
                // If it's for the currently viewed task, refresh display
                if (CURRENT_TASK_ID === updatedInfo.task_id) {
                    displayTraces(); // Refresh display (will re-sort)
                }
            } else {
                 console.warn(`Received trace_updated for unknown trace_id ${updatedInfo.trace_id} in task ${updatedInfo.task_id}`);
            }
        } else {
             console.warn(`Received trace_updated for unknown task_id ${updatedInfo.task_id}`);
        }
        // Re-enable voting buttons
        $('#upvote_btn').prop('disabled', false);
        $('#downvote_btn').prop('disabled', false);
    });

    socket.on('trace_removed', (removedInfo) => {
        console.log('Received trace_removed:', removedInfo);
        // Find the task in memory
        const targetTask = LOADED_TASK_LIST.find(task => task.id === removedInfo.task_id);
        if (targetTask && targetTask.comments) {
            // Find and remove the trace from the task's comments array
            const traceIndex = targetTask.comments.findIndex(c => c.trace_id === removedInfo.trace_id);
            if (traceIndex !== -1) {
                // Remove the trace
                targetTask.comments.splice(traceIndex, 1);
                console.log(`Removed trace ${removedInfo.trace_id} from task ${removedInfo.task_id} locally.`);
                
                // If it's for the currently viewed task, refresh display
                if (CURRENT_TASK_ID === removedInfo.task_id) {
                    // Reset trace index if needed
                    if (CURRENT_TRACE_INDEX >= targetTask.comments.length) {
                        CURRENT_TRACE_INDEX = Math.max(0, targetTask.comments.length - 1);
                    }
                    displayTraces(); // Refresh display
                    infoMsg(removedInfo.message || "Trace removed.");
                }
            } else {
                console.warn(`Received trace_removed for unknown trace_id ${removedInfo.trace_id} in task ${removedInfo.task_id}`);
            }
        } else {
            console.warn(`Received trace_removed for unknown task_id ${removedInfo.task_id}`);
        }
    });

    socket.on('trace_removal_result', (result) => {
        console.log('Received trace_removal_result:', result);
        // Re-enable the remove button
        $('#remove_trace_btn').prop('disabled', false);
        
        if (result.success) {
            infoMsg(result.message || "Trace successfully removed.");
        } else {
            errorMsg(result.message || "Failed to remove trace.");
        }
    });

    socket.on('trace_error', (error) => {
        // Handle errors sent from the server related to traces/votes
        console.error('Server Trace Error:', error.message);
        errorMsg(`Server error: ${error.message}`);
        
        // Re-enable buttons that might have been disabled
        $('#upvote_btn').prop('disabled', false);
        $('#downvote_btn').prop('disabled', false);
        $('#remove_trace_btn').prop('disabled', false);
    });

    // Handler for server response after signing a variation
    socket.on('variation_sign_result', (result) => {
        console.log('Received variation_sign_result:', result);
        if (result.success) {
            // This handler is used for both sign_variation and remove_variation responses
            if (result.message.includes('removed')) {
                infoMsg(`${result.message} Reloading dataset...`);
            } else {
                infoMsg(`Variation signed successfully! (Task: ${result.task_id}, New Version: ${result.new_version}). Reloading dataset...`);
            }
            
            // Store current task ID to restore after reload
            const currentTaskId = CURRENT_TASK_ID;
            
            // Fetch fresh dataset from server
            $.ajax({
                url: `/data/dataset.json`,
                dataType: 'json',
                cache: false, // Prevent caching to ensure we get fresh data
                success: function(data) {
                    console.log(`Successfully fetched fresh dataset data. Processing...`);
                    
                    // Update in-memory dataset
                    LOADED_TASK_LIST = data;
                    
                    // Rebuild the version maps
                    TASK_VERSIONS_MAP = {};
                    UNIQUE_TASK_IDS = [];
                    const idSet = new Set();
                    
                    LOADED_TASK_LIST.forEach((task) => {
                        if (!task || typeof task !== 'object' || !task.id) return;
                        
                        const taskId = task.id;
                        const taskVersion = task.version !== undefined ? parseInt(task.version, 10) : 0;
                        
                        // Initialize comments array
                        task.comments = task.comments || [];
                        
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
                    
                    // Try to load the same task if it still exists
                    if (currentTaskId && TASK_VERSIONS_MAP[currentTaskId]) {
                        // Load the first version if the current version was removed
                        const versionIndex = 0;
                        loadSingleTaskByIdAndVersion(currentTaskId, versionIndex);
                        infoMsg(`Dataset reloaded and task ${currentTaskId} restored.`);
                    } else {
                        // If the task was completely removed, load the first task
                        if (UNIQUE_TASK_IDS.length > 0) {
                            const firstTaskId = UNIQUE_TASK_IDS[0];
                            loadSingleTaskByIdAndVersion(firstTaskId, 0);
                            infoMsg(`Dataset reloaded. Previous task no longer exists, loaded first task.`);
                        } else {
                            infoMsg(`Dataset reloaded, but no tasks found.`);
                        }
                    }
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    console.error(`Failed to reload dataset. Status: ${textStatus}, Error: ${errorThrown}`, jqXHR);
                    errorMsg(`Failed to reload dataset after operation. Please refresh the page manually.`);
                    
                    // Re-enable buttons on error
                    $('#sign_variation_btn').prop('disabled', false);
                    $('#remove_version_btn').prop('disabled', false);
                }
            });
        } else {
            errorMsg(`Operation failed: ${result.message}`);
            // Re-enable the buttons only on failure
            $('#sign_variation_btn').prop('disabled', false);
            $('#remove_version_btn').prop('disabled', false);
        }
    });
}


// --- End WebSocket ---

// --- Sign Variation Logic ---

function signVariation() {
    console.log("Sign Variation button clicked.");

    // 1. Check prerequisites
    if (!ORIGINAL_TASK_DATA || !DISPLAYED_TASK_DATA) {
        errorMsg("No task loaded to sign a variation for.");
        return;
    }
    if (!USERNAME || USERNAME === "Anonymous") {
        errorMsg("Please enter a valid username before signing.");
        $('#username_input').focus();
        return;
    }
    if (!socket || !socket.connected) {
        errorMsg("Cannot sign variation: Not connected to real-time server.");
        return;
    }

    // 2. Confirmation Dialog
    const confirmationMessage = "Are you sure this transformed variation preserves the core logic of the original task and is a valid new task version?";
    if (!confirm(confirmationMessage)) {
        infoMsg("Variation signing cancelled.");
        return;
    }

    // 3. Prepare Payload
    const payload = {
        original_task_id: ORIGINAL_TASK_DATA.id,
        variation_data: { // Send only train and test arrays
            train: DISPLAYED_TASK_DATA.train,
            test: DISPLAYED_TASK_DATA.test
        },
        username: USERNAME
    };

    // 4. Emit WebSocket Event
    console.log("Emitting sign_variation event with payload:", payload);
    socket.emit('sign_variation', payload);

    // 5. Provide Feedback & Disable Button Temporarily
    infoMsg("Submitting variation signature...");
    $('#sign_variation_btn').prop('disabled', true); // Prevent double-clicks
    // The button will be re-enabled by the 'variation_sign_result' handler
}

// --- End Sign Variation Logic ---

// --- Remove Variation Logic ---

function removeVersion() {
    console.log("Remove Variation button clicked.");

    // 1. Check prerequisites
    if (!CURRENT_TASK_ID || CURRENT_VERSION_INDEX === -1) {
        errorMsg("No task version loaded to remove.");
        return;
    }
    if (!USERNAME || USERNAME === "Anonymous") {
        errorMsg("Please enter a valid username before removing a version.");
        $('#username_input').focus();
        return;
    }
    if (!socket || !socket.connected) {
        errorMsg("Cannot remove variation: Not connected to real-time server.");
        return;
    }

    // 2. Check if this is version 0 (cannot remove base version)
    if (CURRENT_VERSION_INDEX === 0) {
        errorMsg("Cannot remove version 0 (base version).");
        return;
    }

    // 3. Password prompt
    const password = prompt("Enter password to remove this variation:", "");
    if (password !== "remove") {
        errorMsg("Incorrect password. Variation not removed.");
        return;
    }

    // 4. Prepare Payload
    const payload = {
        task_id: CURRENT_TASK_ID,
        version_index: CURRENT_VERSION_INDEX,
        username: USERNAME
    };

    // 5. Emit WebSocket Event
    console.log("Emitting remove_variation event with payload:", payload);
    socket.emit('remove_variation', payload);

    // 6. Provide Feedback & Disable Button Temporarily
    infoMsg("Removing variation...");
    $('#remove_version_btn').prop('disabled', true); // Prevent double-clicks
    // The button will be re-enabled when the dataset is reloaded
}

// --- End Remove Variation Logic ---

// --- Logout Function ---
function logoutUser() {
    console.log("Logging out user...");

    // 1. Clear session storage
    try {
        sessionStorage.removeItem('currentTaskId');
        sessionStorage.removeItem('currentVersionIndex');
        sessionStorage.removeItem('currentDatasetName');
        console.log("Session storage cleared.");
    } catch (storageError) {
        console.error("Failed to clear sessionStorage:", storageError);
    }

    // 2. Clear username cookie
    setCookie('username', '', -1); // Set expiry date in the past
    console.log("Username cookie cleared.");

    // 3. Reset application state (full reset)
    resetTask(true);

    // 4. Clear username variable and input field
    USERNAME = "Anonymous";
    $('#username_input').val('');
    console.log("Username variable and input field cleared.");

    // 5. Hide main content, show welcome screen
    $('#demonstration_examples_view').hide();
    $('#evaluation_view').hide();
    $('#comment_section').hide();
    $('#welcome_screen').show();
    console.log("UI reset to welcome screen.");

    // 6. Optional: Disconnect WebSocket? Decide if needed.
    // if (socket && socket.connected) {
    //     socket.disconnect();
    //     console.log("WebSocket disconnected on logout.");
    // }

    infoMsg("You have been logged out."); // Provide feedback
}
// --- End Logout Function ---


// Initial event binding.

$(document).ready(function () {

    // Initialize WebSocket connection early
    connectWebSocket();

    // --- Username Handling (including Cookie) ---
    // Check for existing username cookie
    const savedUsername = getCookie('username');
    if (savedUsername) {
        $('#username_input').val(savedUsername);
        USERNAME = savedUsername; // Update global variable
        console.log("Username loaded from cookie:", USERNAME);
        $('#username_error').hide(); // Hide error if loaded from cookie
    }

    // Update username variable when input changes, hide error on input
    $('#username_input').on('input change', function() { // Trigger on input and change
        let name = $(this).val().trim();
        USERNAME = name || "Anonymous"; // Use 'Anonymous' if empty or only whitespace
        if (name) {
            $('#username_error').hide(); // Hide error message when user starts typing
        }
        console.log("Username set to:", USERNAME);
    });


    // --- Attempt to Restore State from Session Storage ---
    let restoredState = false;
    try {
        const savedTaskId = sessionStorage.getItem('currentTaskId');
        const savedVersionIndexStr = sessionStorage.getItem('currentVersionIndex');
        const savedDatasetName = sessionStorage.getItem('currentDatasetName');

        if (savedTaskId && savedVersionIndexStr && savedDatasetName && USERNAME && USERNAME !== "Anonymous") {
            const savedVersionIndex = parseInt(savedVersionIndexStr, 10);
            if (!isNaN(savedVersionIndex)) {
                console.log(`Found saved state: Task=${savedTaskId}, VersionIndex=${savedVersionIndex}, Dataset=${savedDatasetName}`);
                // Store in pending variables for loadDataset to pick up
                pendingTaskId = savedTaskId;
                pendingVersionIndex = savedVersionIndex;
                pendingDatasetName = savedDatasetName;

                // Immediately attempt to load the dataset (which will then load the specific task)
                // This implicitly hides the welcome screen if successful
                loadDataset(pendingDatasetName);
                restoredState = true; // Mark that we attempted restoration
            } else {
                console.warn("Invalid version index found in sessionStorage.");
                sessionStorage.clear(); // Clear potentially corrupted state
            }
        } else {
             console.log("No valid saved state found or username missing, showing welcome screen.");
             // Clear any partial state just in case
             sessionStorage.removeItem('currentTaskId');
             sessionStorage.removeItem('currentVersionIndex');
             sessionStorage.removeItem('currentDatasetName');
        }
    } catch (storageError) {
        console.error("Failed to read state from sessionStorage:", storageError);
        // Proceed as if no state was found
    }
    // --- End Attempt to Restore State ---


    // --- Initial UI State (Conditional) ---
    if (!restoredState) {
        // If state wasn't restored (or failed), show the welcome screen
        $('#welcome_screen').show();
        $('#demonstration_examples_view').hide();
        $('#evaluation_view').hide();
        $('#comment_section').hide();
        console.log("Showing welcome screen.");
    } else {
        // If restoration was attempted, loadDataset will handle showing/hiding
        console.log("Attempted state restoration, UI visibility handled by loadDataset.");
    }
    // --- End Initial UI State ---


    // Set initial distance display visibility based on checkbox state
    toggleDistanceDisplay();

    $('#symbol_picker').find('.symbol_preview').click(function(event) {
        symbol_preview = $(event.target);
        $('#symbol_picker').find('.symbol_preview').each(function(i, preview) {
            $(preview).removeClass('selected-symbol-preview');
        })
        symbol_preview.addClass('selected-symbol-preview');

        toolMode = $('input[name=tool_switching]:checked').val();
        if (toolMode == 'select') {
            $('.edition_grid').find('.ui-selected').each(function(i, cell) {
                symbol = getSelectedSymbol();
                setCellSymbol($(cell), symbol);
            });
        }
    });

    $('.edition_grid').each(function(i, jqGrid) {
        setUpEditionGridListeners($(jqGrid));
    });

    // Removed event listeners for '.load_task'

    $('input[type=radio][name=tool_switching]').change(function() {
        initializeSelectable();
    });

    $('input[type=text][name=size]').on('keydown', function(event) {
        // Trigger resize on Enter key
        if (event.keyCode == 13) {
            resizeOutputGrid();
        }
    });

    // Add event listener for Enter key in the Go To ID input
    $('#task_id_input').on('keydown', function(event) {
        if (event.keyCode == 13) { // 13 is the Enter key
            gotoTaskById();
        }
    });

    // Add event listener for Enter key in the Go To Task Number input
    $('#task_number_input').on('keydown', function(event) {
        if (event.keyCode == 13) { // 13 is the Enter key
            gotoTaskByNumber();
        }
    });


    $('body').keydown(function(event) {
        // Ignore keydown events if focused in an input field (like Go To ID, task number, or username)
        if ($(event.target).is('input, textarea')) {
            return;
        }

        // Copy and paste functionality.
        if (event.which == 67) { // Key 'C'
            // Press C

            selected = $('.ui-selected');
            if (selected.length == 0) {
                return;
            }

            COPY_PASTE_DATA = [];
            for (var i = 0; i < selected.length; i ++) {
                x = parseInt($(selected[i]).attr('x'));
                y = parseInt($(selected[i]).attr('y'));
                symbol = parseInt($(selected[i]).attr('symbol'));
                COPY_PASTE_DATA.push([x, y, symbol]);
            }
            infoMsg('Cells copied! Select a target cell and press V to paste at location.');

        }
        if (event.which == 86) { // Key 'V'
            // Press V (Paste)
            if (COPY_PASTE_DATA.length == 0) {
                errorMsg('No data to paste. Press C on selected cells to copy.');
                return;
            }
            selected = $('.edition_grid').find('.ui-selected');
            if (selected.length == 0) {
                errorMsg('Select a target cell on the output grid.');
                return;
            }

            jqGrid = $(selected.parent().parent()[0]);

            if (selected.length == 1) {
                targetx = parseInt(selected.attr('x'));
                targety = parseInt(selected.attr('y'));

                xs = new Array();
                ys = new Array();
                symbols = new Array();

                for (var i = 0; i < COPY_PASTE_DATA.length; i ++) {
                    xs.push(COPY_PASTE_DATA[i][0]);
                    ys.push(COPY_PASTE_DATA[i][1]);
                    symbols.push(COPY_PASTE_DATA[i][2]);
                }

                minx = Math.min(...xs);
                miny = Math.min(...ys);
                for (var i = 0; i < xs.length; i ++) {
                    x = xs[i];
                    y = ys[i];
                    symbol = symbols[i];
                    newx = x - minx + targetx;
                    newy = y - miny + targety;
                    res = jqGrid.find('[x="' + newx + '"][y="' + newy + '"] ');
                    if (res.length == 1) {
                        cell = $(res[0]);
                        setCellSymbol(cell, symbol);
                    }
                }
                // Update distance after paste
                updateDistanceDisplay();
            } else {
                errorMsg('Can only paste at a specific location; only select *one* cell as paste destination.');
            }
        }
    });

    // Add event listeners for transformation checkboxes
    $('#transformation_controls_area input[type=checkbox]').change(function() {
        // When any transformation checkbox changes, re-apply all transformations
        applyAndDisplayTransformations();
    });
});
