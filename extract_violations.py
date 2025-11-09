#!/usr/bin/env python3
"""
Script to extract violations from Conforma log files.

Usage:
    python extract_violations.py <log_file>
    python extract_violations.py managed-zxd9h-verify-conforma.log
"""

import re
import sys
import json
from typing import List, Dict, Optional
from pathlib import Path


def parse_violation_block(lines: List[str], start_idx: int) -> tuple[Optional[Dict], int]:
    """
    Parse a violation block starting at start_idx.
    Returns (violation_dict, next_index) or (None, next_index) if not a valid violation.
    """
    if start_idx >= len(lines):
        return None, start_idx
    
    # Check if this line starts a violation
    line = lines[start_idx].strip()
    violation_match = re.match(r'✕\s+\[Violation\]\s+(.+)', line)
    if not violation_match:
        return None, start_idx + 1
    
    violation = {
        'rule': violation_match.group(1).strip(),
        'image_ref': None,
        'reason': None,
        'term': None,
        'title': None,
        'description': None,
        'solution': None,
    }
    
    idx = start_idx + 1
    current_field = None
    current_value = []
    
    while idx < len(lines):
        line = lines[idx].strip()
        
        # Empty line indicates end of violation block
        if not line:
            break
        
        # Check for field markers
        if line.startswith('ImageRef:'):
            if current_field and current_value:
                violation[current_field] = '\n'.join(current_value).strip()
            current_field = 'image_ref'
            current_value = [line.replace('ImageRef:', '').strip()]
        elif line.startswith('Reason:'):
            if current_field and current_value:
                violation[current_field] = '\n'.join(current_value).strip()
            current_field = 'reason'
            current_value = [line.replace('Reason:', '').strip()]
        elif line.startswith('Term:'):
            if current_field and current_value:
                violation[current_field] = '\n'.join(current_value).strip()
            current_field = 'term'
            current_value = [line.replace('Term:', '').strip()]
        elif line.startswith('Title:'):
            if current_field and current_value:
                violation[current_field] = '\n'.join(current_value).strip()
            current_field = 'title'
            current_value = [line.replace('Title:', '').strip()]
        elif line.startswith('Description:'):
            if current_field and current_value:
                violation[current_field] = '\n'.join(current_value).strip()
            current_field = 'description'
            current_value = [line.replace('Description:', '').strip()]
        elif line.startswith('Solution:'):
            if current_field and current_value:
                violation[current_field] = '\n'.join(current_value).strip()
            current_field = 'solution'
            current_value = [line.replace('Solution:', '').strip()]
        else:
            # Continuation of current field
            if current_field:
                current_value.append(line)
            else:
                # If we haven't seen a field marker yet, this might be continuation of reason
                if not violation['reason']:
                    violation['reason'] = line
                else:
                    current_value.append(line)
        
        idx += 1
    
    # Store the last field
    if current_field and current_value:
        violation[current_field] = '\n'.join(current_value).strip()
    
    return violation, idx


def extract_violations(log_file: Path) -> List[Dict]:
    """Extract all violations from a log file."""
    violations = []
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    idx = 0
    while idx < len(lines):
        violation, next_idx = parse_violation_block(lines, idx)
        if violation:
            violations.append(violation)
        idx = next_idx
    
    return violations


def format_violation(violation: Dict, index: int) -> str:
    """Format a violation for human-readable output."""
    output = []
    output.append(f"\n{'='*80}")
    output.append(f"Violation #{index + 1}")
    output.append(f"{'='*80}")
    output.append(f"Rule: {violation['rule']}")
    if violation.get('image_ref'):
        output.append(f"ImageRef: {violation['image_ref']}")
    if violation.get('reason'):
        output.append(f"Reason: {violation['reason']}")
    if violation.get('term'):
        output.append(f"Term: {violation['term']}")
    if violation.get('title'):
        output.append(f"Title: {violation['title']}")
    if violation.get('description'):
        output.append(f"Description: {violation['description']}")
    if violation.get('solution'):
        output.append(f"Solution: {violation['solution']}")
    return '\n'.join(output)


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_violations.py <log_file> [--json]", file=sys.stderr)
        sys.exit(1)
    
    # Filter out '--json' from arguments to find the log file
    args = [arg for arg in sys.argv[1:] if arg != '--json']
    if not args:
        print("Error: No log file specified", file=sys.stderr)
        print("Usage: python extract_violations.py <log_file> [--json]", file=sys.stderr)
        sys.exit(1)
    
    log_file = Path(args[0])
    output_json = '--json' in sys.argv
    
    if not log_file.exists():
        print(f"Error: File not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    
    violations = extract_violations(log_file)
    
    if output_json:
        print(json.dumps(violations, indent=2))
    else:
        if not violations:
            print("No violations found in the log file.")
        else:
            print(f"Found {len(violations)} violation(s):\n")
            for i, violation in enumerate(violations):
                print(format_violation(violation, i))
            print(f"\n{'='*80}")
            print(f"Total: {len(violations)} violation(s)")


if __name__ == "__main__":
    main()

