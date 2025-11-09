#!/usr/bin/env python3
"""
Script to extract component information from Conforma log files.

The components are defined in a JSON block in the log file and contain
git repository URLs and revisions needed to locate pipeline definitions.

Usage:
    python extract_components.py <log_file> [--json] [--name <component-name>]
    python extract_components.py lifecycle-agent-conforma-staging-on-pr-4-20-4n2pl-verify.log
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional


def extract_components(log_file: Path) -> List[Dict]:
    """Extract component information from the log file."""
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the line with the opening brace that contains "components" or "application"
    json_start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('{') and ('"components"' in line or '"component"' in line or '"application"' in line):
            json_start_idx = i
            break
    
    if json_start_idx is None:
        raise ValueError("No components JSON block found in log file")
    
    # Find the complete JSON block by counting braces
    json_lines = []
    brace_count = 0
    for i in range(json_start_idx, len(lines)):
        line = lines[i]
        json_lines.append(line)
        brace_count += line.count('{') - line.count('}')
        # Stop when we've balanced all braces
        if brace_count == 0 and i > json_start_idx:
            break
    
    json_str = ''.join(json_lines)
    
    try:
        data = json.loads(json_str)
        
        # Handle both "components" (array) and "component" (single object) formats
        if 'components' in data:
            components = data['components']
        elif 'component' in data:
            components = [data['component']]
        else:
            raise ValueError("No 'components' or 'component' key found in JSON block")
        
        if not components:
            raise ValueError("Components array is empty")
        
        return components
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse components JSON: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_components.py <log_file> [--json] [--name <component-name>]", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --json              Output as JSON", file=sys.stderr)
        print("  --name <name>        Filter by component name", file=sys.stderr)
        sys.exit(1)
    
    # Filter out options from arguments to find the log file
    args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    if not args:
        print("Error: No log file specified", file=sys.stderr)
        print("Usage: python extract_components.py <log_file> [--json] [--name <component-name>]", file=sys.stderr)
        sys.exit(1)
    
    log_file = Path(args[0])
    output_json = '--json' in sys.argv
    filter_name = None
    
    # Extract --name value
    if '--name' in sys.argv:
        name_idx = sys.argv.index('--name')
        if name_idx + 1 < len(sys.argv):
            filter_name = sys.argv[name_idx + 1]
    
    if not log_file.exists():
        print(f"Error: File not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        components = extract_components(log_file)
        
        # Filter by name if specified
        if filter_name:
            components = [c for c in components if c.get('name') == filter_name]
            if not components:
                print(f"Error: No component found with name '{filter_name}'", file=sys.stderr)
                sys.exit(1)
        
        if output_json:
            if len(components) == 1:
                print(json.dumps(components[0], indent=2))
            else:
                print(json.dumps(components, indent=2))
        else:
            if len(components) == 1:
                comp = components[0]
                print(f"Component: {comp.get('name', 'N/A')}")
                if 'source' in comp and 'git' in comp['source']:
                    git = comp['source']['git']
                    print(f"  Git URL: {git.get('url', 'N/A')}")
                    print(f"  Revision: {git.get('revision', 'N/A')}")
                    if 'dockerfileUrl' in git:
                        print(f"  Dockerfile: {git.get('dockerfileUrl', 'N/A')}")
            else:
                print(f"Found {len(components)} component(s):\n")
                for i, comp in enumerate(components, 1):
                    print(f"{i}. {comp.get('name', 'N/A')}")
                    if 'source' in comp and 'git' in comp['source']:
                        git = comp['source']['git']
                        print(f"   Git URL: {git.get('url', 'N/A')}")
                        print(f"   Revision: {git.get('revision', 'N/A')}")
                    print()
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

