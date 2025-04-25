import json
import os
import argparse

def merge_json_files(input_folder, output_file):
    """
    Merges JSON files from an input folder into a single output file.

    Handles both individual JSON objects and lists of objects within files.
    Merges 'signed_by' lists for entries with identical id, version, and content.
    """
    processed_entries = {} # Dictionary to store unique entries: {(id, version): entry_dict}
    default_signer = "gkamradt" # Define the default signer

    if not os.path.isdir(input_folder):
        print(f"Error: Input folder '{input_folder}' not found or is not a directory.")
        return

    for filename in os.listdir(input_folder):
        if filename.endswith(".json"):
            filepath = os.path.join(input_folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    # file_id = os.path.splitext(filename)[0] # Get file ID - No longer needed directly here

                    items_to_process = []
                    if isinstance(content, list):
                        items_to_process.extend(content)
                    elif isinstance(content, dict):
                        items_to_process.append(content)
                    # Ignore content that is not a list or dict for merging logic

                    for item in items_to_process:
                        if not isinstance(item, dict):
                            print(f"Warning: Skipping non-dictionary item in file '{filename}'.")
                            continue

                        # Ensure 'id', 'version', and 'signed_by' fields
                        if 'id' not in item:
                            # Try to infer ID from filename if missing, otherwise skip
                            file_id_base = os.path.splitext(filename)[0]
                            item['id'] = file_id_base
                            # print(f"Warning: Item in '{filename}' missing 'id'. Using filename base '{file_id_base}'.")
                            # If even filename doesn't work as ID, we might need to skip or handle differently
                            if not item['id']:
                                print(f"Warning: Could not determine ID for an item in '{filename}'. Skipping.")
                                continue

                        item['version'] = int(item.get('version', 0)) # Default version 0, ensure int

                        # Handle 'signed_by': ensure it's a list, default if missing
                        current_signer = item.get('signed_by')
                        if current_signer is None:
                            item['signed_by'] = [default_signer]
                        elif isinstance(current_signer, str):
                            item['signed_by'] = [current_signer] # Convert string to list
                        elif not isinstance(current_signer, list):
                            print(f"Warning: Invalid 'signed_by' type ({type(current_signer)}) for item {item.get('id')} v{item.get('version')} in '{filename}'. Resetting to default.")
                            item['signed_by'] = [default_signer]
                        # Ensure all elements in the list are strings (simple check)
                        item['signed_by'] = [str(s) for s in item['signed_by'] if isinstance(s, (str, int, float))]


                        entry_key = (item['id'], item['version'])
                        new_signer = item['signed_by'][0] if item['signed_by'] else default_signer # Assume the first signer is the relevant one from this file

                        if entry_key in processed_entries:
                            # Potential duplicate found
                            existing_item = processed_entries[entry_key]

                            # Compare content excluding 'signed_by'
                            item_copy = item.copy()
                            existing_item_copy = existing_item.copy()
                            item_copy.pop('signed_by', None)
                            existing_item_copy.pop('signed_by', None)

                            if item_copy == existing_item_copy:
                                # Identical content, merge signers
                                if new_signer not in existing_item['signed_by']:
                                    existing_item['signed_by'].append(new_signer)
                                    processed_entries[entry_key] = existing_item # Update entry
                                    # print(f"Merged signer '{new_signer}' into existing entry {entry_key}")
                            else:
                                # Content mismatch for the same id/version
                                print(f"Warning: Content mismatch for duplicate entry ID '{item['id']}' version '{item['version']}' found in '{filename}'. Keeping the first encountered version.")
                        else:
                            # New entry
                            processed_entries[entry_key] = item
                            # print(f"Added new entry {entry_key}")

            except json.JSONDecodeError:
                print(f"Warning: Skipping file '{filename}' due to invalid JSON format.")
            except Exception as e:
                print(f"Warning: Error processing file '{filename}': {e}")

    # Convert the processed entries dictionary back to a list
    merged_data_final = list(processed_entries.values())
    # Optional: Sort the final list, e.g., by id then version
    merged_data_final.sort(key=lambda x: (x.get('id', ''), x.get('version', 0)))


    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
             os.makedirs(output_dir)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data_final, f, indent=4) # Use indent for readability
        print(f"Successfully merged JSON files from '{input_folder}' into '{output_file}' ({len(merged_data_final)} unique entries)")
    except Exception as e:
        print(f"Error writing to output file '{output_file}': {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge JSON files from a folder into a single output file.")
    parser.add_argument("input_folder", help="Path to the folder containing JSON files to merge.")
    parser.add_argument("output_file", help="Path to the output JSON file.")

    args = parser.parse_args()

    merge_json_files(args.input_folder, args.output_file)
