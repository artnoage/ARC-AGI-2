import os
import json
import hashlib
import argparse

def find_first_json_file(directory):
    """Finds the first .json file in the specified directory."""
    abs_directory = os.path.abspath(directory)
    print(f"Scanning directory: {abs_directory}") # Print absolute path
    try:
        files_found = []
        for filename in os.listdir(abs_directory):
            if filename.endswith(".json"):
                files_found.append(filename)

        if not files_found:
            print("No .json files found.")
            return None

        # Sort to ensure consistent "first" file if needed, though order isn't guaranteed
        files_found.sort()
        first_filename = files_found[0]
        full_path = os.path.join(abs_directory, first_filename)
        print(f"Found first .json file: {first_filename} (Full path: {full_path})")
        return full_path

    except FileNotFoundError:
        print(f"Error: Directory not found: {abs_directory}")
        return None
    except Exception as e:
        print(f"Error scanning directory {abs_directory}: {e}")
        return None

def get_expected_id(filepath):
    """Extracts the 8-character ID from the filename."""
    return os.path.splitext(os.path.basename(filepath))[0]

def hash_data(data_bytes, algorithm='sha256'):
    """Hashes the data using the specified algorithm and returns the hex digest."""
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    else: # Default to sha256
        hasher = hashlib.sha256()
    hasher.update(data_bytes)
    return hasher.hexdigest()

def verify_id(filepath):
    """Loads a JSON file, hashes parts, and checks against the filename ID."""
    if not filepath:
        print("No JSON file path provided.")
        return

    abs_filepath = os.path.abspath(filepath) # Get absolute path for clarity
    print(f"\nAttempting to process file: {abs_filepath}")

    # Explicitly check if the file exists at the constructed path
    if not os.path.exists(abs_filepath):
        print(f"Error: File does not exist at the specified path: {abs_filepath}")
        return

    expected_id = get_expected_id(filepath) # Use original path for basename extraction
    print(f"Expected ID (from filename '{os.path.basename(filepath)}'): {expected_id}")

    try:
        # Use the absolute path to open
        with open(abs_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("File successfully opened and JSON loaded.")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {abs_filepath}")
        return
    except Exception as e:
        print(f"Error reading file {abs_filepath}: {e}")
        return

    # --- Data parts to test ---
    parts_to_hash = {}

    try:
        # 1. Entire JSON object (consistent serialization)
        # Use sort_keys and no separators for max consistency
        full_json_string = json.dumps(data, sort_keys=True, separators=(',', ':'))
        parts_to_hash['full_json'] = full_json_string.encode('utf-8')

        # 2. 'train' part
        if 'train' in data:
            train_string = json.dumps(data['train'], sort_keys=True, separators=(',', ':'))
            parts_to_hash['train_part'] = train_string.encode('utf-8')

        # 3. 'test' part
        if 'test' in data:
            test_string = json.dumps(data['test'], sort_keys=True, separators=(',', ':'))
            parts_to_hash['test_part'] = test_string.encode('utf-8')

        # Add more parts here if needed (e.g., individual examples)

    except Exception as e:
        print(f"Error processing JSON content: {e}")
        return


    # --- Hashing and Comparison ---
    algorithms = ['md5', 'sha1', 'sha256']
    match_found = False

    print("\n--- Hashing Results (Truncated to 8 chars) ---")
    for part_name, part_bytes in parts_to_hash.items():
        print(f"Hashing part: '{part_name}'")
        for algo in algorithms:
            full_hash = hash_data(part_bytes, algo)
            truncated_hash = full_hash[:8] # Take the first 8 hex characters
            print(f"  {algo.upper()}: {truncated_hash} (Full: {full_hash})")
            if truncated_hash == expected_id:
                print(f"  *** MATCH FOUND! Part '{part_name}' with {algo.upper()} matches the expected ID. ***")
                match_found = True

    if not match_found:
        print("\nNo matching hash found for the tested parts and algorithms.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify if ARC task ID (filename) matches truncated hash of its content.")
    parser.add_argument(
        "filepath",
        nargs='?', # Makes the argument optional
        help="Path to a specific JSON task file. If omitted, uses the first .json file found in data/evaluation."
    )
    parser.add_argument(
        "--dir",
        default="data/evaluation",
        help="Directory to search for the first JSON file if filepath is omitted (default: data/evaluation)."
    )

    args = parser.parse_args()

    target_file = args.filepath
    if not target_file:
        print(f"No specific file provided, searching in '{args.dir}'...")
        target_file = find_first_json_file(args.dir)
        if not target_file:
            print(f"Could not find any .json file in '{args.dir}'.")

    if target_file:
        verify_id(target_file)
