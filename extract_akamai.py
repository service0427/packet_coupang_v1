
import json
import re
import sys

def extract_akamai_script(har_path, output_path):
    print(f"Loading HAR: {har_path}")
    try:
        with open(har_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)
    except Exception as e:
        print(f"Error loading HAR: {e}")
        return

    print("Searching for Akamai script (bmak)...")
    
    entries = har_data['log']['entries']
    found = False
    
    for entry in entries:
        resp = entry['response']
        content = resp.get('content', {})
        text = content.get('text', '')
        
        if not text:
            continue
            
        # Search for bmak object initialization or typical Akamai patterns
        # Pattern 1: var bmak = ...
        # Pattern 2: _cf = ... (often associated)
        # Pattern 3: Reference to "sensor_data" logic
        
        if "var bmak" in text or "bmak={" in text or "bmak=" in text:
            print(f"Found 'bmak' in response from: {entry['request']['url']}")
            
            # Simple extraction heuristic:
            # If it's an HTML file, we need to extract the <script> tag.
            # If it's a JS file, the whole text is the script.
            
            if "html" in content.get('mimeType', ''):
                print("Source is HTML, extracting script tags...")
                # Find script tag containing bmak
                # Regex for <script> content
                scripts = re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL)
                for script in scripts:
                    if "bmak" in script:
                        print("Found Akamai logic in inline script.")
                        with open(output_path, 'w', encoding='utf-8') as f_out:
                            f_out.write(script)
                        print(f"Saved to {output_path}")
                        found = True
                        break
            else:
                print("Source is JS, saving full content...")
                with open(output_path, 'w', encoding='utf-8') as f_out:
                    f_out.write(text)
                print(f"Saved to {output_path}")
                found = True
                
        if found:
            break
            
    if not found:
        print("Akamai script not found in HAR.")

if __name__ == "__main__":
    extract_akamai_script('/home/tech/packet_coupang_v1/pc_chrome_20260108.har', 'akamai_script.js')
