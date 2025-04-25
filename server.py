import os
import json
import logging
import time
import shutil # For file copying
from datetime import datetime, timedelta # For timestamp comparison
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
APP_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(APP_DIR, 'data')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups') # Backup directory
APPS_STATIC_DIR = os.path.join(APP_DIR, 'apps')
TRACE_STORE_FILE = os.path.join(DATA_DIR, 'traces_store.json')
BACKUP_INTERVAL = timedelta(hours=1) # Backup interval (1 hour)

# --- Flask App Setup ---
app = Flask(__name__, static_folder=None) # Disable default static folder
app.config['SECRET_KEY'] = 'your_secret_key_here!' # Change this in production!
socketio = SocketIO(app, cors_allowed_origins="*") # Allow all origins for now

# --- Data Loading ---
# base_task_data = {} # Replaced by unified_dataset_data
unified_dataset_data = None # Will hold the loaded dataset.json content
trace_data = {}

def load_unified_dataset_data():
    """Loads the unified dataset.json data."""
    global unified_dataset_data
    filepath = os.path.join(DATA_DIR, "dataset.json") # Load dataset.json directly
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            unified_dataset_data = json.load(f)
            logging.info(f"Successfully loaded unified dataset from {filepath}")
    except FileNotFoundError:
        logging.error(f"Unified dataset file not found: {filepath}")
        unified_dataset_data = None # Ensure it's None if loading fails
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in unified dataset file: {filepath}")
        unified_dataset_data = None
    except Exception as e:
        logging.error(f"Error loading unified dataset file {filepath}: {e}")
        unified_dataset_data = None

def load_trace_data():
    """Loads trace data from the JSON store."""
    global trace_data
    try:
        if os.path.exists(TRACE_STORE_FILE):
            with open(TRACE_STORE_FILE, 'r', encoding='utf-8') as f:
                trace_data = json.load(f)
                logging.info(f"Loaded trace data from {TRACE_STORE_FILE}")
        else:
            trace_data = {} # Initialize if file doesn't exist
            logging.info(f"Trace store file not found ({TRACE_STORE_FILE}), initializing empty store.")
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in trace store file: {TRACE_STORE_FILE}. Initializing empty store.")
        trace_data = {}
    except Exception as e:
        logging.error(f"Error loading trace store file {TRACE_STORE_FILE}: {e}")
        trace_data = {} # Fallback to empty

def save_trace_data():
    """Saves the current trace data to the JSON store."""
    try:
        with open(TRACE_STORE_FILE, 'w', encoding='utf-8') as f:
            json.dump(trace_data, f, indent=2) # Use indent for readability
            logging.debug(f"Saved trace data to {TRACE_STORE_FILE}")
    except Exception as e:
        logging.error(f"Error saving trace store file {TRACE_STORE_FILE}: {e}")
    finally:
        # Attempt backup regardless of main save success, but log potential issues
        try:
            backup_trace_data_hourly()
        except Exception as backup_e:
            logging.error(f"Error during hourly backup process: {backup_e}")


def backup_trace_data_hourly():
    """Creates a timestamped backup of the trace store if the last backup is older than BACKUP_INTERVAL."""
    try:
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Find the latest backup file
        latest_backup_time = None
        backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith('traces_store_') and f.endswith('.json')]
        if backup_files:
            timestamps = []
            for fname in backup_files:
                try:
                    # Extract timestamp string (YYYYMMDD_HHMMSS)
                    ts_str = fname.replace('traces_store_', '').replace('.json', '')
                    timestamps.append(datetime.strptime(ts_str, '%Y%m%d_%H%M%S'))
                except ValueError:
                    logging.warning(f"Could not parse timestamp from backup filename: {fname}")
            if timestamps:
                latest_backup_time = max(timestamps)

        # Check if backup is needed
        now = datetime.now()
        should_backup = False
        if latest_backup_time is None:
            should_backup = True # First backup
            logging.info("No previous backups found. Creating initial backup.")
        elif now - latest_backup_time >= BACKUP_INTERVAL:
            should_backup = True
            logging.info(f"Last backup ({latest_backup_time}) is older than {BACKUP_INTERVAL}. Creating new backup.")
        else:
            logging.debug(f"Last backup ({latest_backup_time}) is recent. Skipping backup.")

        # Perform backup if needed
        if should_backup:
            if not os.path.exists(TRACE_STORE_FILE):
                logging.warning(f"Trace store file {TRACE_STORE_FILE} does not exist. Cannot create backup.")
                return

            timestamp_str = now.strftime('%Y%m%d_%H%M%S')
            backup_filename = f"traces_store_{timestamp_str}.json"
            backup_filepath = os.path.join(BACKUP_DIR, backup_filename)
            shutil.copy2(TRACE_STORE_FILE, backup_filepath) # copy2 preserves metadata
            logging.info(f"Successfully created backup: {backup_filepath}")

    except Exception as e:
        logging.error(f"Failed to perform hourly backup: {e}")

def save_unified_dataset_data():
    """Saves the current unified dataset data back to dataset.json."""
    global unified_dataset_data
    filepath = os.path.join(DATA_DIR, "dataset.json")
    # TODO: Implement file locking for concurrent writes in production
    try:
        # Optional: Create a backup before overwriting
        # backup_filepath = filepath + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # shutil.copy2(filepath, backup_filepath)
        # logging.info(f"Created backup before saving: {backup_filepath}")

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(unified_dataset_data, f, indent=2) # Use indent for readability
            logging.info(f"Successfully saved updated dataset to {filepath}")
        return True
    except Exception as e:
        logging.error(f"Error saving unified dataset file {filepath}: {e}")
        return False

def compare_task_data(task_data1, task_data2):
    """Deep compares the 'train' and 'test' arrays of two task data objects."""
    try:
        # Simple but effective way for nested lists/dicts: compare JSON strings
        # Ensure consistent sorting if order doesn't matter (though it usually does for ARC)
        return json.dumps(task_data1.get('train', []), sort_keys=True) == json.dumps(task_data2.get('train', []), sort_keys=True) and \
               json.dumps(task_data1.get('test', []), sort_keys=True) == json.dumps(task_data2.get('test', []), sort_keys=True)
    except Exception as e:
        logging.error(f"Error comparing task data: {e}")
        return False


# Load initial data on startup
load_unified_dataset_data() # Load the unified dataset
# base_task_data['original'] = load_base_task_data('original') # Removed
# base_task_data['augmented'] = load_base_task_data('augmented') # Removed
load_trace_data()

# --- HTTP Routes ---
@app.route('/')
def index():
    """Serves the testing interface directly."""
    return send_from_directory(APPS_STATIC_DIR, 'testing_interface.html')

@app.route('/apps/<path:filename>')
def serve_apps_files(filename):
    """Serves static files from the apps directory (js, css, html)."""
    return send_from_directory(APPS_STATIC_DIR, filename)

@app.route('/data/dataset.json') # Specific route for dataset.json
def serve_unified_data():
    """Serves the unified dataset.json data."""
    if unified_dataset_data is not None:
        return jsonify(unified_dataset_data)
    else:
        # Log the error server-side as well
        logging.error("Attempted to serve unified dataset, but it was not loaded successfully.")
        return jsonify({"error": "Unified dataset 'dataset.json' not found or failed to load on the server."}), 404

# --- WebSocket Event Handlers ---
@socketio.on('connect')
def handle_connect():
    logging.info(f"Client connected: {request.sid}")
    emit('connection_ack', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logging.info(f"Client disconnected: {request.sid}")

@socketio.on('request_traces')
def handle_request_traces(data):
    """Client requests traces for a specific task."""
    task_id = data.get('task_id')
    sid = request.sid
    logging.info(f"Client {sid} requested traces for task_id: {task_id}")
    if task_id:
        task_traces = trace_data.get(task_id, [])
        emit('initial_traces', {'task_id': task_id, 'traces': task_traces}, room=sid)
        logging.debug(f"Sent {len(task_traces)} traces for task {task_id} to client {sid}")
    else:
        logging.warning(f"Client {sid} sent 'request_traces' without task_id.")

@socketio.on('add_trace')
def handle_add_trace(data):
    """Client adds a new trace."""
    task_id = data.get('task_id')
    username = data.get('username', 'Anonymous') # Default username
    text = data.get('text')
    sid = request.sid

    logging.info(f"Client {sid} adding trace for task {task_id} by {username}")

    if not task_id or not text:
        logging.warning(f"Client {sid} sent incomplete 'add_trace' data.")
        emit('trace_error', {'message': 'Missing task_id or text for adding trace.'}, room=sid)
        return

    # Create new trace object
    # TODO: Generate a truly unique trace ID (e.g., UUID)
    trace_id = f"{task_id}_{username}_{socketio.server.eio.generate_id()[:8]}" # Simple unique enough ID for now
    new_trace = {
        'trace_id': trace_id,
        'task_id': task_id,
        'username': username,
        'text': text,
        'score': 0,
        'timestamp': time.time(), # Use standard time module for timestamp
        'voters': {} # Initialize empty voters dict
    }

    # Add to in-memory store
    if task_id not in trace_data:
        trace_data[task_id] = []
    trace_data[task_id].append(new_trace)

    # Save to file (consider debouncing or batching writes later for performance)
    save_trace_data()

    # Broadcast the new trace to all connected clients
    # TODO: Ideally, only broadcast to clients interested in this task_id
    emit('new_trace', new_trace, broadcast=True)
    logging.info(f"Broadcasted new trace {trace_id} for task {task_id}")

@socketio.on('vote_trace')
def handle_vote_trace(data):
    """Client votes on a trace."""
    trace_id = data.get('trace_id')
    username = data.get('username', 'Anonymous')
    vote = data.get('vote') # Should be +1 or -1
    sid = request.sid

    logging.info(f"Client {sid} ({username}) voting {vote} on trace {trace_id}")

    if not trace_id or not username or vote not in [1, -1]:
        logging.warning(f"Client {sid} sent invalid 'vote_trace' data.")
        emit('trace_error', {'message': 'Invalid vote data.'}, room=sid)
        return

    # Find the trace
    target_trace = None
    task_id_of_trace = None
    for task_id, traces in trace_data.items():
        for trace in traces:
            if trace.get('trace_id') == trace_id:
                target_trace = trace
                task_id_of_trace = task_id
                break
        if target_trace:
            break

    if not target_trace:
        logging.warning(f"Client {sid} tried to vote on non-existent trace {trace_id}")
        emit('trace_error', {'message': f'Trace ID {trace_id} not found.'}, room=sid)
        return

    # Check if user already voted this way
    current_vote = target_trace.get('voters', {}).get(username, 0)

    if current_vote == vote:
        logging.debug(f"User {username} already voted {vote} on trace {trace_id}. No change.")
        # Optionally inform the user they already voted
        # emit('vote_ack', {'trace_id': trace_id, 'score': target_trace['score'], 'message': 'Already voted.'}, room=sid)
        return

    # Update score and voter record
    # If user voted oppositely before, the change is doubled (e.g., -1 to +1 is +2 change)
    score_change = vote - current_vote
    target_trace['score'] = target_trace.get('score', 0) + score_change
    if 'voters' not in target_trace: target_trace['voters'] = {}
    target_trace['voters'][username] = vote

    # Save changes
    save_trace_data()

    # Broadcast the updated trace score/info
    # TODO: Only broadcast to clients interested in this task_id
    updated_trace_info = {
        'trace_id': trace_id,
        'task_id': task_id_of_trace,
        'score': target_trace['score']
        # Optionally include updated voters dict if frontend needs it
    }
    emit('trace_updated', updated_trace_info, broadcast=True)
    logging.info(f"Broadcasted updated score for trace {trace_id} (New score: {target_trace['score']})")

@socketio.on('remove_trace')
def handle_remove_trace(data):
    """Client requests to remove a trace."""
    trace_id = data.get('trace_id')
    task_id = data.get('task_id')
    username = data.get('username', 'Anonymous')
    sid = request.sid

    logging.info(f"Client {sid} ({username}) attempting to remove trace {trace_id} for task {task_id}")

    if not trace_id or not task_id or not username:
        logging.warning(f"Client {sid} sent incomplete 'remove_trace' data.")
        emit('trace_error', {'message': 'Missing required data (trace ID, task ID, or username).'}, room=sid)
        return

    # Find the trace
    if task_id not in trace_data:
        logging.warning(f"Task ID {task_id} not found in trace data.")
        emit('trace_error', {'message': f'Task ID {task_id} not found.'}, room=sid)
        return

    # Find the trace in the task's traces
    trace_index = None
    for i, trace in enumerate(trace_data[task_id]):
        if trace.get('trace_id') == trace_id:
            trace_index = i
            break

    if trace_index is None:
        logging.warning(f"Trace ID {trace_id} not found in task {task_id}.")
        emit('trace_error', {'message': f'Trace ID {trace_id} not found in task {task_id}.'}, room=sid)
        return

    # Remove the trace
    removed_trace = trace_data[task_id].pop(trace_index)
    logging.info(f"Removed trace {trace_id} from task {task_id}.")

    # Save changes
    save_trace_data()

    # Broadcast the removal to all connected clients
    emit('trace_removed', {
        'trace_id': trace_id,
        'task_id': task_id,
        'message': f'Trace removed by {username}.'
    }, broadcast=True)
    
    # Re-enable the remove button
    emit('trace_removal_result', {
        'success': True,
        'message': f'Trace successfully removed.'
    }, room=sid)
    
    logging.info(f"Broadcasted trace removal for trace {trace_id} of task {task_id}")

@socketio.on('remove_variation')
def handle_remove_variation(data):
    """Client requests to remove a task variation."""
    task_id = data.get('task_id')
    version_index = data.get('version_index')
    username = data.get('username')
    sid = request.sid

    logging.info(f"Client {sid} ({username}) attempting to remove variation for task {task_id}, version index {version_index}")

    # --- Validation ---
    if not all([task_id, username]) or version_index is None:
        logging.warning(f"Client {sid} sent incomplete 'remove_variation' data.")
        emit('variation_sign_result', {'success': False, 'message': 'Missing required data (task ID, version index, or username).'}, room=sid)
        return

    if unified_dataset_data is None:
        logging.error("Cannot remove variation: Unified dataset is not loaded.")
        emit('variation_sign_result', {'success': False, 'message': 'Server error: Dataset not loaded.'}, room=sid)
        return

    # Cannot remove version 0 (base version)
    if version_index == 0:
        logging.warning(f"Client {sid} attempted to remove base version (index 0) of task {task_id}.")
        emit('variation_sign_result', {'success': False, 'message': 'Cannot remove base version (version 0).'}, room=sid)
        return

    # --- Processing ---
    task_versions = []
    task_indices = []
    
    # Find all versions of the task and their indices in the dataset
    for i, entry in enumerate(unified_dataset_data):
        if entry.get('id') == task_id:
            task_versions.append(entry)
            task_indices.append(i)
    
    if not task_versions:
        logging.warning(f"Task {task_id} not found in dataset.")
        emit('variation_sign_result', {'success': False, 'message': f'Task ID {task_id} not found in dataset.'}, room=sid)
        return
    
    # Sort versions by version number
    task_versions_with_indices = sorted(zip(task_versions, task_indices), key=lambda x: x[0].get('version', 0))
    
    # Check if version_index is valid
    if version_index < 0 or version_index >= len(task_versions_with_indices):
        logging.warning(f"Invalid version index {version_index} for task {task_id}.")
        emit('variation_sign_result', {'success': False, 'message': f'Invalid version index {version_index} for task {task_id}.'}, room=sid)
        return
    
    # Get the version to remove and its index in the dataset
    version_to_remove, index_in_dataset = task_versions_with_indices[version_index]
    version_number = version_to_remove.get('version', 0)
    
    # Remove the version
    removed_version = unified_dataset_data.pop(index_in_dataset)
    logging.info(f"Removed version {version_number} of task {task_id}.")
    
    # Realign version numbers for higher versions
    versions_updated = 0
    for entry in unified_dataset_data:
        if entry.get('id') == task_id and entry.get('version', 0) > version_number:
            entry['version'] = entry['version'] - 1
            versions_updated += 1
    
    logging.info(f"Realigned {versions_updated} higher version numbers for task {task_id}.")
    
    # Save the updated dataset
    if save_unified_dataset_data():
        emit('variation_sign_result', {
            'success': True, 
            'message': f'Successfully removed version {version_number} of task {task_id} and realigned higher versions.', 
            'task_id': task_id
        }, room=sid)
        logging.info(f"Dataset saved after removing version {version_number} of task {task_id}.")
    else:
        # If saving failed, add the removed version back to maintain consistency
        unified_dataset_data.insert(index_in_dataset, removed_version)
        # Restore version numbers
        for entry in unified_dataset_data:
            if entry.get('id') == task_id and entry.get('version', 0) >= version_number:
                entry['version'] = entry['version'] + 1
        
        emit('variation_sign_result', {
            'success': False, 
            'message': 'Server error: Failed to save dataset after removing variation.', 
            'task_id': task_id
        }, room=sid)
        logging.error(f"Failed to save dataset after removing version {version_number} of task {task_id}.")

@socketio.on('sign_variation')
def handle_sign_variation(data):
    """Client signs a transformed task variation."""
    original_task_id = data.get('original_task_id')
    variation_data = data.get('variation_data') # Expected: {'train': [...], 'test': [...]}
    username = data.get('username')
    sid = request.sid

    logging.info(f"Client {sid} ({username}) attempting to sign variation for task {original_task_id}")

    # --- Validation ---
    if not all([original_task_id, variation_data, username]):
        logging.warning(f"Client {sid} sent incomplete 'sign_variation' data.")
        emit('variation_sign_result', {'success': False, 'message': 'Missing required data (task ID, variation data, or username).'}, room=sid)
        return

    if not isinstance(variation_data, dict) or 'train' not in variation_data or 'test' not in variation_data:
        logging.warning(f"Client {sid} sent invalid 'variation_data' structure.")
        emit('variation_sign_result', {'success': False, 'message': 'Invalid variation data structure.'}, room=sid)
        return

    if unified_dataset_data is None:
        logging.error("Cannot sign variation: Unified dataset is not loaded.")
        emit('variation_sign_result', {'success': False, 'message': 'Server error: Dataset not loaded.'}, room=sid)
        return

    # --- Processing ---
    found_duplicate = False
    updated_existing = False
    highest_version = -1
    target_entry = None # Will hold the entry if duplicate found

    # Iterate through a copy to avoid issues if we modify the list during iteration (though append should be safe)
    for i, entry in enumerate(list(unified_dataset_data)):
        if entry.get('id') == original_task_id:
            current_version = entry.get('version', 0)
            highest_version = max(highest_version, current_version)

            # Check if this existing version is identical to the submitted variation
            if compare_task_data(entry, variation_data):
                found_duplicate = True
                target_entry = entry # Reference the original entry in the list
                logging.info(f"Found identical variation (Version {current_version}) for task {original_task_id}.")
                # Check if user already signed this version
                if username not in target_entry.get('signed_by', []):
                    if 'signed_by' not in target_entry:
                        target_entry['signed_by'] = []
                    target_entry['signed_by'].append(username)
                    updated_existing = True
                    logging.info(f"Added signature from {username} to existing Version {current_version}.")
                else:
                    logging.info(f"User {username} already signed Version {current_version}. No changes needed.")
                break # Stop searching once duplicate is found and processed

    # --- Handle Outcome ---
    save_needed = False
    response_data = {'success': True}

    if found_duplicate:
        response_data['message'] = f"Signature added to existing Version {target_entry.get('version', 0)}."
        response_data['task_id'] = original_task_id
        response_data['new_version'] = target_entry.get('version', 0) # Report the existing version
        if updated_existing:
            save_needed = True # Only save if signature was actually added
    else:
        # Create new entry
        new_version_number = highest_version + 1
        new_entry = {
            "id": original_task_id,
            "version": new_version_number,
            "train": variation_data['train'],
            "test": variation_data['test'],
            "signed_by": [username] # Start with the submitting user
            # Add timestamp? Optional.
            # "creation_timestamp": time.time()
        }
        unified_dataset_data.append(new_entry)
        save_needed = True
        response_data['message'] = f"New variation saved as Version {new_version_number}."
        response_data['task_id'] = original_task_id
        response_data['new_version'] = new_version_number
        logging.info(f"Created new Version {new_version_number} for task {original_task_id} signed by {username}.")

    # --- Save if necessary ---
    if save_needed:
        if not save_unified_dataset_data():
            # Saving failed, report error
            logging.error(f"Failed to save dataset after signing variation for task {original_task_id}.")
            emit('variation_sign_result', {'success': False, 'message': 'Server error: Failed to save updated dataset.'}, room=sid)
            # Attempt to revert in-memory change? Maybe too complex for now.
            # For simplicity, the in-memory data might be inconsistent with the file if saving fails.
            return # Stop before sending success message

    # --- Emit result back to client ---
    emit('variation_sign_result', response_data, room=sid)


# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Flask-SocketIO server...")
    print(f"Serving index from: {APP_DIR}")
    print(f"Serving app files from: {APPS_STATIC_DIR}")
    print(f"Using trace store: {TRACE_STORE_FILE}")
    # Use host='0.0.0.0' to make it accessible on the network
    # Use debug=True for development (auto-reloads), but disable in production
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True)
