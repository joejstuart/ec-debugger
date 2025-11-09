#!/usr/bin/env python3
"""
Script to extract policy configuration from Conforma log files.

Usage:
    python extract_policy.py <log_file> [--json] [--pretty]
    python extract_policy.py managed-zxd9h-verify-conforma.log
"""

import json
import sys
from pathlib import Path


def extract_policy(log_file: Path) -> dict:
    """Extract the policy configuration from a log file."""
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the STEP-SHOW-CONFIG marker
    config_start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == 'STEP-SHOW-CONFIG':
            config_start_idx = i + 1
            break
    
    if config_start_idx is None:
        raise ValueError("STEP-SHOW-CONFIG section not found in log file")
    
    # Find the JSON block - it starts after STEP-SHOW-CONFIG
    # The JSON is indented, so we need to collect lines until we find the closing brace
    json_lines = []
    brace_count = 0
    started = False
    
    for i in range(config_start_idx, len(lines)):
        line = lines[i]
        stripped = line.strip()
        
        # Skip empty lines at the start
        if not stripped and not started:
            continue
        
        # Start collecting when we see the opening brace
        if stripped.startswith('{'):
            started = True
        
        if started:
            json_lines.append(stripped)
            # Count braces to find the end of the JSON object
            brace_count += stripped.count('{') - stripped.count('}')
            
            # When brace_count reaches 0, we've closed the main object
            if brace_count == 0 and stripped.endswith('}'):
                break
    
    if not json_lines:
        raise ValueError("Could not find JSON policy configuration")
    
    # Join the lines and parse as JSON
    json_str = ' '.join(json_lines)
    try:
        policy_data = json.loads(json_str)
        return policy_data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON policy configuration: {e}")


def format_policy(policy_data: dict, pretty: bool = False) -> str:
    """Format policy data for output."""
    if pretty:
        return json.dumps(policy_data, indent=2)
    else:
        return json.dumps(policy_data)


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_policy.py <log_file> [--json] [--pretty]", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --json    Output only the policy JSON (default: includes metadata)", file=sys.stderr)
        print("  --pretty  Pretty-print the JSON output", file=sys.stderr)
        sys.exit(1)
    
    # Filter out options from arguments to find the log file
    args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    if not args:
        print("Error: No log file specified", file=sys.stderr)
        print("Usage: python extract_policy.py <log_file> [--json] [--pretty]", file=sys.stderr)
        sys.exit(1)
    
    log_file = Path(args[0])
    output_json = '--json' in sys.argv
    pretty = '--pretty' in sys.argv
    
    if not log_file.exists():
        print(f"Error: File not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    
    try:
        policy_data = extract_policy(log_file)
        
        if output_json:
            # Output only the policy section
            if 'policy' in policy_data:
                print(format_policy(policy_data['policy'], pretty))
            else:
                print(format_policy(policy_data, pretty))
        else:
            # Output the full configuration with metadata
            print(format_policy(policy_data, pretty))
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

