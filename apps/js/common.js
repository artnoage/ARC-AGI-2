
class Grid {
    constructor(height, width, values) {
        this.height = height;
        this.width = width;
        this.grid = new Array(height);
        for (var i = 0; i < height; i++){
            this.grid[i] = new Array(width);
            for (var j = 0; j < width; j++){
                if (values != undefined && values[i] != undefined && values[i][j] != undefined){
                    this.grid[i][j] = values[i][j];
                } else {
                    this.grid[i][j] = 0;
                }
            }
        }
    }
}

function floodfillFromLocation(grid, i, j, symbol) {
    i = parseInt(i);
    j = parseInt(j);
    symbol = parseInt(symbol);

    target = grid[i][j];
    
    if (target == symbol) {
        return;
    }

    function flow(i, j, symbol, target) {
        if (i >= 0 && i < grid.length && j >= 0 && j < grid[i].length) {
            if (grid[i][j] == target) {
                grid[i][j] = symbol;
                flow(i - 1, j, symbol, target);
                flow(i + 1, j, symbol, target);
                flow(i, j - 1, symbol, target);
                flow(i, j + 1, symbol, target);
            }
        }
    }
    flow(i, j, symbol, target);
}

function parseSizeTuple(size) {
    size = size.split('x');
    if (size.length != 2) {
        alert('Grid size should have the format "3x3", "5x7", etc.');
        return;
    }
    if ((size[0] < 1) || (size[1] < 1)) {
        alert('Grid size should be at least 1. Cannot have a grid with no cells.');
        return;
    }
    if ((size[0] > 30) || (size[1] > 30)) {
        alert('Grid size should be at most 30 per side. Pick a smaller size.');
        return;
    }
    return size;
}

function convertSerializedGridToGridObject(values) {
    height = values.length;
    width = values[0].length;
    return new Grid(height, width, values)
}

function fitCellsToContainer(jqGrid, height, width, containerHeight, containerWidth) {
    // Calculate the maximum possible cell size based on container height and width constraints
    let sizeH = Math.floor(containerHeight / height);
    let sizeW = Math.floor(containerWidth / width);

    // Use the smaller of the two sizes to ensure the grid fits proportionally
    let size = Math.min(sizeH, sizeW);

    // Ensure minimum size of 1px and limit by MAX_CELL_SIZE
    size = Math.max(1, size);
    size = Math.min(MAX_CELL_SIZE, size);

    // Apply the calculated square cell size
    jqGrid.find('.cell').css('height', size + 'px');
    jqGrid.find('.cell').css('width', size + 'px');

    // // Adjust the container size to tightly wrap the grid - REMOVED - Let CSS handle container size.
    // jqGrid.css('height', (size * height) + 'px');
    // jqGrid.css('width', (size * width) + 'px');
}

function fillJqGridWithData(jqGrid, dataGrid) {
    jqGrid.empty();
    height = dataGrid.height;
    width = dataGrid.width;
    for (var i = 0; i < height; i++){
        var row = $(document.createElement('div'));
        row.addClass('row');
        for (var j = 0; j < width; j++){
            var cell = $(document.createElement('div'));
            cell.addClass('cell');
            cell.attr('x', i);
            cell.attr('y', j);
            setCellSymbol(cell, dataGrid.grid[i][j]);
            row.append(cell);
        }
        jqGrid.append(row);
    }
}

function copyJqGridToDataGrid(jqGrid, dataGrid) {
    row_count = jqGrid.find('.row').length
    if (dataGrid.height != row_count) {
        return
    }
    col_count = jqGrid.find('.cell').length / row_count
    if (dataGrid.width != col_count) {
        return
    }
    jqGrid.find('.row').each(function(i, row) {
        $(row).find('.cell').each(function(j, cell) {
            dataGrid.grid[i][j] = parseInt($(cell).attr('symbol'));
        });
    });
}

function setCellSymbol(cell, symbol) {
    cell.attr('symbol', symbol);
    classesToRemove = ''
    for (i = 0; i < 10; i++) {
        classesToRemove += 'symbol_' + i + ' ';
    }
    cell.removeClass(classesToRemove);
    cell.addClass('symbol_' + symbol);
    // Show numbers if "Show symbol numbers" is checked
    if ($('#show_symbol_numbers').is(':checked')) {
        cell.text(symbol);
    } else {
        cell.text('');
    }
}

function changeSymbolVisibility() {
    $('.cell').each(function(i, cell) {
        if ($('#show_symbol_numbers').is(':checked')) {
            $(cell).text($(cell).attr('symbol'));
        } else {
            $(cell).text('');
        }
    });
}

// Function to transpose a 2D array (grid)
function transposeGrid(grid) {
    if (!grid || grid.length === 0 || !grid[0] || grid[0].length === 0) {
        return []; // Return empty for empty or invalid input
    }
    const height = grid.length;
    // Ensure all rows have the same width, use the first row's width
    const width = grid[0].length;
    const newGrid = Array(width).fill(null).map(() => Array(height).fill(0)); // Initialize new grid with correct dimensions

    for (let i = 0; i < height; i++) {
        // Ensure row exists and has expected width before accessing
        if (grid[i] && grid[i].length === width) {
            for (let j = 0; j < width; j++) {
                if (grid[i][j] !== undefined) { // Check if source cell value exists
                     newGrid[j][i] = grid[i][j];
                }
                // else: keep the initialized 0 in newGrid
            }
        } else {
             // Handle potentially jagged arrays if necessary, though ARC expects rectangular
             // For now, we assume rectangular based on ARC format.
             // If a row is missing or has wrong length, its corresponding column in the transpose might be incomplete/incorrect.
             console.warn("Transpose encountered potentially non-rectangular grid or missing row at index:", i);
        }
    }
    return newGrid;
}

// Function to reflect a 2D array (grid) vertically (left-right flip)
function reflectGridVertical(grid) {
    if (!grid || grid.length === 0) {
        return [];
    }
    const newGrid = [];
    for (let i = 0; i < grid.length; i++) {
        if (Array.isArray(grid[i])) { // Check if row is an array
            newGrid.push([...grid[i]].reverse()); // Create a copy before reversing
        } else {
            newGrid.push([]); // Add empty array if original row wasn't an array
            console.warn("Vertical reflection encountered non-array row at index:", i);
        }
    }
    return newGrid;
}

// Function to reflect a 2D array (grid) horizontally (top-bottom flip)
function reflectGridHorizontal(grid) {
    if (!grid || grid.length === 0) {
        return [];
    }
    // Create a shallow copy of the outer array before reversing
    // Filter out any non-array elements just in case, though ARC expects arrays of arrays
    return [...grid].filter(row => Array.isArray(row)).reverse();
}


function errorMsg(msg) {
    $('#error_display').stop(true, true);
    $('#info_display').stop(true, true);

    $('#error_display').hide();
    $('#info_display').hide();
    $('#error_display').html(msg);
    $('#error_display').show();
    $('#error_display').fadeOut(5000);
}

function infoMsg(msg) {
    $('#error_display').stop(true, true);
    $('#info_display').stop(true, true);

    $('#info_display').hide();
    $('#error_display').hide();
    $('#info_display').html(msg);
    $('#info_display').show();
    $('#info_display').fadeOut(5000);
}

// Cookie Functions
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
    for(var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) == ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}
