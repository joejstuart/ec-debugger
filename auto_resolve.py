#!/usr/bin/env python3
"""
Mellea-based script to analyze violations and propose fixes.

This script:
1. Extracts violations from log files
2. Examines policy rules and tests to understand what triggers violations
3. Proposes fixes with examples

Usage:
    python auto_resolve.py <log_file>
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import mellea
from mellea.backends.types import ModelOption
from mellea.stdlib.requirement import req
from mellea.stdlib.sampling import RejectionSamplingStrategy

# Try to import model_ids for convenience
try:
    from mellea.backends import model_ids
except ImportError:
    model_ids = None


def extract_violations(log_file: Path) -> List[Dict]:
    """Extract violations using the deterministic script."""
    try:
        result = subprocess.run(
            ["python3", "extract_violations.py", str(log_file), "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error extracting violations: {e.stderr}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing violations JSON: {e}", file=sys.stderr)
        return []


def extract_policy_config(log_file: Path) -> Optional[Dict]:
    """Extract policy configuration using the deterministic script."""
    try:
        result = subprocess.run(
            ["python3", "extract_policy.py", str(log_file), "--json", "--pretty"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        return None
    except json.JSONDecodeError:
        return None


def extract_components(log_file: Path) -> List[Dict]:
    """Extract component information using the deterministic script."""
    try:
        result = subprocess.run(
            ["python3", "extract_components.py", str(log_file), "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else [data]
    except subprocess.CalledProcessError:
        return []
    except json.JSONDecodeError:
        return []


def match_component_to_violation(violation_image_ref: str, components: List[Dict]) -> Optional[Dict]:
    """Match a violation's image reference to a component."""
    if not violation_image_ref or not components:
        return None
    
    violation_digest = None
    if "@sha256:" in violation_image_ref:
        violation_digest = violation_image_ref.split("@sha256:")[-1]
    
    for component in components:
        component_image = component.get("containerImage", "")
        if not component_image:
            continue
        
        if component_image == violation_image_ref:
            return component
        
        if violation_digest and "@sha256:" in component_image:
            component_digest = component_image.split("@sha256:")[-1]
            if component_digest == violation_digest:
                return component
        
        violation_image_name = violation_image_ref.split("@")[0] if "@" in violation_image_ref else violation_image_ref
        component_image_name = component_image.split("@")[0] if "@" in component_image else component_image
        if violation_image_name == component_image_name and violation_digest:
            if violation_digest in component_image:
                return component
    
    return None


def load_example_pipeline_run() -> Optional[str]:
    """Load the example pipelineRun definition from the pipelineRuns folder."""
    pipeline_runs_dir = Path("pipelineRuns")
    if not pipeline_runs_dir.exists():
        return None
    
    # Look for any YAML files in the pipelineRuns folder
    pipeline_run_files = []
    for pattern in ["*.yaml", "*.yml"]:
        for file_path in pipeline_runs_dir.glob(pattern):
            if file_path.is_file():
                rel_path = file_path.relative_to(Path("."))
                pipeline_run_files.append(f"{rel_path}:\n{file_path.read_text(encoding='utf-8')}\n")
    
    if pipeline_run_files:
        return "\n---\n".join(pipeline_run_files)
    
    return None


def fetch_policy_rule(rule_name: str, policy_repo_path: Optional[Path] = None) -> Optional[str]:
    """Fetch the policy rule source code from the policy repository."""
    if '.' not in rule_name:
        return None
    
    package, rule = rule_name.split('.', 1)
    rule_file = f"{rule}.rego"
    
    # Try to find in local policy repo if provided
    if policy_repo_path and policy_repo_path.exists():
        rule_path = policy_repo_path / "policy" / "release" / package / rule_file
        if rule_path.exists():
            return rule_path.read_text(encoding='utf-8')
        # Also check subdirectories
        package_dir = policy_repo_path / "policy" / "release" / package
        if package_dir.exists():
            for subdir in package_dir.iterdir():
                if subdir.is_dir():
                    potential_rule = subdir / rule_file
                    if potential_rule.exists():
                        return potential_rule.read_text(encoding='utf-8')
    
    # Try to clone and fetch if policy repo not available locally
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "policy"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/conforma/policy.git", str(repo_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                rule_path = repo_path / "policy" / "release" / package / rule_file
                if rule_path.exists():
                    return rule_path.read_text(encoding='utf-8')
                # Check subdirectories
                package_dir = repo_path / "policy" / "release" / package
                if package_dir.exists():
                    for subdir in package_dir.iterdir():
                        if subdir.is_dir():
                            potential_rule = subdir / rule_file
                            if potential_rule.exists():
                                return potential_rule.read_text(encoding='utf-8')
    except Exception:
        pass
    
    return None


def fetch_policy_rule_test(rule_name: str, policy_repo_path: Optional[Path] = None) -> Optional[str]:
    """Fetch the policy rule test file from the policy repository."""
    if '.' not in rule_name:
        return None
    
    package, rule = rule_name.split('.', 1)
    test_file = f"{package}_test.go"
    
    # Try to find in local policy repo if provided
    if policy_repo_path and policy_repo_path.exists():
        test_path = policy_repo_path / "policy" / "release" / package / test_file
        if test_path.exists():
            return test_path.read_text(encoding='utf-8')
    
    # Try to clone and fetch if policy repo not available locally
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "policy"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "https://github.com/conforma/policy.git", str(repo_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                test_path = repo_path / "policy" / "release" / package / test_file
                if test_path.exists():
                    return test_path.read_text(encoding='utf-8')
    except Exception:
        pass
    
    return None


def fetch_crd_schema() -> Optional[str]:
    """Fetch the EnterpriseContractPolicy CRD schema."""
    crd_url = "https://raw.githubusercontent.com/conforma/crds/refs/heads/main/config/crd/bases/appstudio.redhat.com_enterprisecontractpolicies.yaml"
    try:
        with urllib.request.urlopen(crd_url, timeout=10) as response:
            schema = response.read().decode('utf-8')
            # Truncate if too long - keep first 8000 chars which should cover the key spec definitions
            if len(schema) > 8000:
                return schema[:8000] + "\n... (truncated - see full schema at the URL)"
            return schema
    except Exception:
        return None


def group_violations_by_rule(violations: List[Dict]) -> Dict[str, List[Dict]]:
    """Group violations by their rule field."""
    grouped = {}
    for violation in violations:
        rule = violation.get("rule", "unknown")
        if rule not in grouped:
            grouped[rule] = []
        grouped[rule].append(violation)
    return grouped


def generate_fix_proposals(
    m: mellea.MelleaSession,
    violations: List[Dict],
    log_file: Path,
) -> List[Dict]:
    """Generate fix proposals for all violations.
    
    Violations with the same rule are grouped together and get a single proposal.
    Examines policy rule source code, tests, policy configuration, and pipelineRun definitions.
    """
    proposals = []
    
    # Extract policy configuration and components
    print(f"  Extracting policy configuration...")
    policy_config = extract_policy_config(log_file)
    
    print(f"  Extracting component information...")
    components = extract_components(log_file)
    
    # Group violations by rule
    grouped_violations = group_violations_by_rule(violations)
    total_groups = len(grouped_violations)
    
    print(f"\nGrouped {len(violations)} violation(s) into {total_groups} unique rule(s)\n")
    
    # Check for local policy repo
    policy_repo_path = Path("policy")
    if not policy_repo_path.exists():
        policy_repo_path = None
    
    for group_idx, (rule, rule_violations) in enumerate(grouped_violations.items(), 1):
        print(f"[{group_idx}/{total_groups}] Processing rule: {rule} ({len(rule_violations)} violation(s))")
        
        # Fetch policy rule and tests
        print(f"  Fetching policy rule source...")
        policy_rule_code = fetch_policy_rule(rule, policy_repo_path) or "Policy rule source not available"
        
        print(f"  Fetching policy rule tests...")
        policy_rule_test_code = fetch_policy_rule_test(rule, policy_repo_path) or "Policy rule tests not available"
        
        # Fetch CRD schema for policy configuration reference
        print(f"  Fetching CRD schema...")
        crd_schema = fetch_crd_schema() or "CRD schema not available"
        
        # Load example pipelineRun definition
        print(f"  Loading example pipelineRun definition...")
        pipeline_run_raw = load_example_pipeline_run()
        if pipeline_run_raw:
            pipeline_run_def = pipeline_run_raw[:3000] + "\n... (truncated)" if len(pipeline_run_raw) > 3000 else pipeline_run_raw
            print(f"  ✓ Example pipelineRun definition loaded")
        else:
            pipeline_run_def = "PipelineRun definition not available (no example found in pipelineRuns folder)"
            print(f"  ⚠ Could not load example pipelineRun definition")
        
        # Prepare policy config string
        policy_config_str = json.dumps(policy_config, indent=2) if policy_config else "Policy configuration not available"
        if len(policy_config_str) > 3000:
            policy_config_str = policy_config_str[:3000] + "\n... (truncated)"
        
        # Truncate if too long
        if len(policy_rule_code) > 4000:
            policy_rule_code = policy_rule_code[:4000] + "\n... (truncated)"
        if len(policy_rule_test_code) > 4000:
            policy_rule_test_code = policy_rule_test_code[:4000] + "\n... (truncated)"
        if len(crd_schema) > 8000:
            crd_schema = crd_schema[:8000] + "\n... (truncated)"
        
        # Generate fix proposal
        print(f"  Generating fix proposal...")
        violation_json = json.dumps(rule_violations, indent=2)
        
        # Extract solution field(s) from violations if available
        solutions = []
        for v in rule_violations:
            solution = v.get("solution", "").strip()
            if solution and solution not in solutions:
                solutions.append(solution)
        solution_text = "\n".join(solutions) if solutions else "No solution provided in violation"
        
        # Build context about policy rule structure
        package, rule_name = rule.split('.', 1) if '.' in rule else (rule, "")
        policy_rule_context = f"""Policy Rule Location Information:
- Violations reference rules using the format: package.rule_name
- For rule '{rule}': package='{package}', rule='{rule_name}'
- Policy rules are located in: policy/release/{package}/{package}.rego
- Test files are located in: policy/release/{package}/{package}_test.go
- The policy repository is at: https://github.com/conforma/policy.git
- Rules examine artifacts like: attestation (build provenance), SBOM (package lists), and image contents"""
        
        result = m.instruct(
            """{{policy_rule_context}}

Analyze the violation and propose a fix.

Violation details:
{{violation}}

Policy rule source code:
{{policy_rule}}

Policy rule tests:
{{policy_rule_test}}

Solution guidance from violation:
{{solution}}

EnterpriseContractPolicy CRD Schema:
{{crd_schema}}

Policy Configuration:
{{policy_config}}

PipelineRun Definition:
{{pipeline_run}}

STEP 1: Examine the policy rule source code and tests to understand what the rule checks and why the violation occurred.

STEP 2: Review the policy configuration and pipelineRun definition to determine WHERE the fix should be applied:
- If the fix requires updating task bundles, find where task bundles are referenced in the pipelineRun definition
- If the fix requires policy configuration changes (ruleData, exclusions, etc.), review the current policy configuration structure
- If the fix requires pipeline changes, identify the specific files and locations in the pipelineRun definition
- Use the policy configuration to understand the current setup and what needs to be modified

STEP 3: Propose a fix with specific examples showing:
- Exactly where the change needs to be made (file path, line numbers if possible, or specific sections)
- The exact changes needed (before/after examples)
- Why this fix addresses the violation 

CRITICAL: Policy exceptions (exclusions, volatileConfig) should be the LAST RESORT. 

IMPORTANT DISTINCTION:
- Policy configuration changes (like ruleData) are VALID and ACCEPTABLE solutions
- Policy exceptions (exclusions, volatileConfig) are LAST RESORT and should be avoided when possible

Before proposing policy exceptions, consider these alternatives in order of preference:
1. Fix the underlying issue (e.g., update build process, fix SBOM generation, fix pipelineRun definition)
2. Use ruleData configuration if the rule supports it (check the policy rule source code and tests) - this is a VALID policy configuration change, not an exception
3. Other policy configuration changes that don't involve exceptions
4. Only if none of the above are feasible, propose a policy exception (exclusion or volatileConfig)

If you must propose a policy exception, you MUST:
- Explain why other solutions (including ruleData and other policy config changes) are not feasible
- Consult the CRD schema to ensure the exception format is correct
- Use the exact structure shown in the schema

Focus on providing a clear, actionable fix proposal with specific examples of what needs to be changed.""",
            requirements=[
                req("The output must be clear and actionable"),
                req("Consider fixing the underlying issue before proposing policy exceptions"),
                req("Check if ruleData configuration is available before proposing exclusions"),
                req("Only propose policy exceptions (exclusions/volatileConfig) as a last resort"),
                req("If proposing policy exceptions, explain why other solutions are not feasible"),
                req("If proposing policy configuration changes, ensure they conform to the CRD schema structure"),
                req("Provide a fix proposal with specific examples of what needs to be changed (policy config, pipeline, SBOM, etc.)"),
                req("Briefly explain why the violation occurred (1-2 sentences)"),
                req("Consider the solution field from the violation when proposing fixes"),
                req("Do not just summarize what the rule checks - focus on the fix"),
            ],
            strategy=RejectionSamplingStrategy(loop_budget=3),
            model_options={ModelOption.TEMPERATURE: 0},
            user_variables={
                "violation": violation_json,
                "policy_rule": policy_rule_code,
                "policy_rule_test": policy_rule_test_code,
                "solution": solution_text,
                "policy_rule_context": policy_rule_context,
                "crd_schema": crd_schema,
                "policy_config": policy_config_str,
                "pipeline_run": pipeline_run_def if pipeline_run_def else "PipelineRun definition not available",
            },
            return_sampling_results=True,
        )
        
        if result.success:
            proposal_text = str(result.result)
        else:
            # Fallback to first sample if validation failed
            proposal_text = result.sample_generations[0].value if result.sample_generations else "Failed to generate proposal"
        
        # Get image ref from first violation for display
        image_ref = rule_violations[0].get("image_ref", "")
        
        proposals.append({
            "rule": rule,
            "violation_count": len(rule_violations),
            "violations": rule_violations,
            "image_ref": image_ref,
            "proposal": proposal_text,
        })
        
        print(f"  ✓ Proposal generated\n")
    
    return proposals


def main():
    if len(sys.argv) < 2:
        print("Usage: python auto_resolve.py <log_file>", file=sys.stderr)
        sys.exit(1)
    
    log_file = Path(sys.argv[1])
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Analyzing log file: {log_file}")
    print("=" * 80)
    
    # Extract violations
    print("\n[1/3] Extracting violations...")
    violations = extract_violations(log_file)
    if not violations:
        print("No violations found in log file.")
        sys.exit(0)
    
    print(f"Found {len(violations)} violation(s)")
    
    # Initialize Mellea session
    print("\n[2/2] Initializing Mellea session...")
    backend_name = os.environ.get("MELLEA_BACKEND_NAME")
    model_id = os.environ.get("MELLEA_MODEL_ID")
    
    if backend_name or model_id:
        if model_id and model_ids:
            if model_id.isupper() and '_' in model_id and hasattr(model_ids, model_id):
                model_id = getattr(model_ids, model_id)
        
        kwargs = {}
        if backend_name:
            kwargs["backend_name"] = backend_name
        if model_id:
            kwargs["model_id"] = model_id
        
        print(f"  Using backend: {backend_name or 'default'}, model: {model_id or 'default'}")
        m = mellea.start_session(**kwargs)
    else:
        m = mellea.start_session()
    
    # Generate fix proposals
    print("\n" + "=" * 80)
    print("Generating fix proposals...")
    print("=" * 80)
    
    proposals = generate_fix_proposals(m, violations, log_file)
    
    if not proposals:
        print("\nNo fix proposals generated.")
    else:
        total_violations_covered = sum(p.get("violation_count", 1) for p in proposals)
        print(f"\n{'=' * 80}")
        print(f"Generated {len(proposals)} proposal(s) covering {total_violations_covered} violation(s)")
        print(f"{'=' * 80}\n")
        
        for i, proposal in enumerate(proposals, 1):
            violation_count = proposal.get("violation_count", 1)
            print(f"\n{'#' * 80}")
            print(f"# Fix Proposal #{i} - Rule: {proposal['rule']}")
            print(f"{'#' * 80}")
            if violation_count > 1:
                print(f"\n**Covers {violation_count} violation(s) with the same rule**")
            print(f"\n**Image**: {proposal['image_ref']}")
            print(f"\n**Proposal:**\n")
            print(proposal["proposal"])
            print(f"\n{'-' * 80}\n")
    
    print("Done!")


if __name__ == "__main__":
    main()
