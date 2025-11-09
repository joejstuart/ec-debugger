# Auto Resolve - Violation Fix Proposal Tool

This tool analyzes Enterprise Contract violations from log files and proposes fixes using AI-powered analysis.

## Overview

`auto_resolve.py` examines violations, policy rules, and tests to understand what triggers violations, then proposes actionable fixes with specific examples.

## Prerequisites

1. **Python 3** (with standard library)
2. **uv** - Python package manager (install from https://github.com/astral-sh/uv)
3. **Dependencies** - Install using uv:
   ```bash
   uv sync
   ```
   This will install Mellea and other dependencies from `pyproject.toml`
4. **Helper scripts** - The following scripts must be in the same directory:
   - `extract_violations.py`
   - `extract_policy.py`
   - `extract_components.py`
   - `extract_image_refs.py`
5. **Policy repository** (optional) - For faster rule fetching:
   ```bash
   git clone https://github.com/conforma/policy.git
   ```
   If not present, the script will clone it automatically when needed.
6. **Example pipelineRun** (optional) - Place example pipelineRun YAML files in the `pipelineRuns/` folder

## Usage

### Basic Usage

```bash
uv run python auto_resolve.py <log_file>
```

Example:
```bash
uv run python auto_resolve.py lifecycle-agent-conforma-staging-on-pr-4-20-4n2pl-verify.log
```

Alternatively, if you've activated the virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python auto_resolve.py <log_file>
```

### What It Does

1. **Extracts violations** from the log file
2. **Groups violations** by rule
3. **For each unique rule**:
   - Fetches the policy rule source code
   - Fetches the policy rule tests
   - Fetches the CRD schema
   - Loads policy configuration from the log
   - Loads example pipelineRun definition (if available)
   - Uses AI to analyze and propose fixes

4. **Outputs fix proposals** with:
   - What the rule checks
   - Why the violation occurred
   - Specific examples of what needs to be changed
   - Where changes should be applied (policy config, pipelineRun, etc.)

## Configuration

### Mellea Backend and Model

You can configure the Mellea backend and model using environment variables:

```bash
export MELLEA_BACKEND_NAME=ollama
export MELLEA_MODEL_ID=llama3.2
uv run python auto_resolve.py <log_file>
```

Or use model constants:
```bash
export MELLEA_MODEL_ID=IBM_GRANITE_3_3_8B
uv run python auto_resolve.py <log_file>
```

If not specified, Mellea will use its default configuration.

## Output

The script outputs fix proposals for each unique violation rule, including:

- **Rule name** and number of violations
- **Image reference** associated with the violation
- **Proposed fix** with:
  - Explanation of what needs to be fixed
  - Specific examples (before/after)
  - File paths and locations where changes are needed
  - Rationale for the fix

## Fix Proposal Priorities

The tool is instructed to prioritize fixes in this order:

1. **Fix the underlying issue** (build process, SBOM generation, pipelineRun definition)
2. **Use ruleData configuration** (if the rule supports it) - This is a valid policy configuration change
3. **Other policy configuration changes** that don't involve exceptions
4. **Policy exceptions** (exclusions, volatileConfig) - Only as a last resort

## Example Output

```
================================================================================
Generated 2 proposal(s) covering 3 violation(s)
================================================================================

################################################################################
# Fix Proposal #1 - Rule: sbom_spdx.allowed_package_sources
################################################################################

**Covers 2 violation(s) with the same rule**

**Image**: quay.io/example/image@sha256:abc123...

**Proposal:**

[AI-generated fix proposal with specific examples]
```

## Troubleshooting

### Policy Rule Not Found

If a policy rule cannot be found:
- Ensure you have network access (for automatic cloning)
- Or clone the policy repository locally: `git clone https://github.com/conforma/policy.git`

### PipelineRun Definition Not Available

If you see "PipelineRun definition not available":
- Create a `pipelineRuns/` folder
- Add example pipelineRun YAML files to it
- The script will use these as reference

### Mellea Errors

If you encounter Mellea-related errors:
- Check that dependencies are installed: `uv pip list | grep mellea` or `uv tree`
- Verify your backend configuration
- Check network connectivity if using remote backends
- Ensure you're using `uv run` or have activated the virtual environment

## Files Used

- **Input**: Log file from Conforma/Enterprise Contract validation
- **Helper scripts**: `extract_violations.py`, `extract_policy.py`, `extract_components.py`, `extract_image_refs.py`
- **Policy repository**: `policy/` (local) or fetched from GitHub
- **Example pipelineRuns**: `pipelineRuns/*.yaml` (optional)

## Notes

- The script groups violations by rule to avoid duplicate proposals
- Policy exceptions (exclusions) are only suggested as a last resort
- The tool focuses on actionable fixes with specific examples
- All analysis is based on the policy rule source code, tests, and violation details

