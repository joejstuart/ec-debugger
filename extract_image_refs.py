#!/usr/bin/env python3
"""
Script to extract image references from the STEP-VALIDATE section of Conforma log files.

Usage:
    python extract_image_refs.py <log_file> [--json] [--first]
    python extract_image_refs.py managed-zxd9h-verify-conforma.log
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Optional


def extract_image_refs(log_file: Path) -> List[str]:
    """Extract image references from the STEP-VALIDATE section."""
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the STEP-VALIDATE marker
    validate_start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == 'STEP-VALIDATE':
            validate_start_idx = i + 1
            break
    
    if validate_start_idx is None:
        raise ValueError("STEP-VALIDATE section not found in log file")
    
    image_refs = []
    
    # Look for ImageRef or COMPONENTS in the STEP-VALIDATE section header
    # The section header ends when we hit "Results:" or the next STEP- marker
    i = validate_start_idx
    in_components = False
    component_list = []
    seen_refs = set()  # Track seen refs to avoid duplicates
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if we've reached the end of STEP-VALIDATE header (Results: starts the details)
        if stripped.startswith('Results:'):
            break
        
        # Check if we've reached the next STEP- marker
        if stripped.startswith('STEP-') and i > validate_start_idx:
            break
        
        # Check for single ImageRef in the header
        if stripped.startswith('ImageRef:'):
            image_ref = stripped.replace('ImageRef:', '').strip()
            if image_ref and image_ref not in seen_refs:
                image_refs.append(image_ref)
                seen_refs.add(image_ref)
        
        # Check for COMPONENTS list
        if stripped.startswith('COMPONENTS:'):
            in_components = True
            # The next lines should be the component list
            i += 1
            continue
        
        # If we're in components, look for image references
        if in_components:
            # Components might be listed with ImageRef: or as a structured list
            if stripped.startswith('ImageRef:'):
                image_ref = stripped.replace('ImageRef:', '').strip()
                if image_ref and image_ref not in seen_refs:
                    component_list.append(image_ref)
                    seen_refs.add(image_ref)
            # Check if we've hit an empty line or Results: which indicates end of components
            elif not stripped or stripped.startswith('Results:'):
                if component_list:
                    image_refs.extend(component_list)
                    component_list = []
                in_components = False
        
        i += 1
    
    # Add any remaining components
    if component_list:
        image_refs.extend(component_list)
    
    if not image_refs:
        raise ValueError("No image references found in STEP-VALIDATE section")
    
    return image_refs


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_image_refs.py <log_file> [--json] [--first]", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --json    Output as JSON array", file=sys.stderr)
        print("  --first    Output only the first image reference", file=sys.stderr)
        sys.exit(1)
    
    # Filter out options from arguments to find the log file
    args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    if not args:
        print("Error: No log file specified", file=sys.stderr)
        print("Usage: python extract_image_refs.py <log_file> [--json] [--first]", file=sys.stderr)
        sys.exit(1)
    
    log_file = Path(args[0])
    output_json = '--json' in sys.argv
    first_only = '--first' in sys.argv
    
    if not log_file.exists():
        print(f"Error: File not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        image_refs = extract_image_refs(log_file)
        
        if first_only:
            image_refs = [image_refs[0]] if image_refs else []
        
        if output_json:
            if first_only and image_refs:
                print(image_refs[0])
            else:
                print(json.dumps(image_refs, indent=2))
        else:
            if first_only:
                if image_refs:
                    print(image_refs[0])
                else:
                    print("No image references found", file=sys.stderr)
                    sys.exit(1)
            else:
                if len(image_refs) == 1:
                    print(image_refs[0])
                else:
                    print(f"Found {len(image_refs)} image reference(s):")
                    for i, img_ref in enumerate(image_refs, 1):
                        print(f"  {i}. {img_ref}")
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

