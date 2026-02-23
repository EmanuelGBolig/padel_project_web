import json
import sys

def clean_json(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
            data = f.read()

        # Try to parse it to see if it's valid
        # We might have an unclosed list if the process was killed
        if not data.strip().endswith(']'):
            print("File is truncated, trying to fix by finding the last valid object.")
            last_brace = data.rfind('}')
            if last_brace != -1:
                data = data[:last_brace+1] + '\n]'
            else:
                print("Could not find any objects.")
                return

        parsed_data = json.loads(data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, indent=2, ensure_ascii=False)
            
        print(f"Successfully cleaned JSON and saved to {output_file}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    clean_json('backup_render4.json', 'backup_render_clean.json')
