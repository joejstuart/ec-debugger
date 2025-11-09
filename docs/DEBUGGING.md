# EC Auto Resolver

This repository contains scripts to extract violations and policy information from Conforma log files, and instructions for reproducing violations.

## Quick Start with Mellea

For an automated workflow that reproduces violations and proposes fixes using local LLMs:

```bash
# Make sure Ollama is running and you have a model available
# Then run the automated resolver:
python3 auto_resolve.py <log_file> --reproduce --propose-fix
```

This will:
1. Extract violations from the log file
2. Generate step-by-step reproduction instructions
3. Propose fixes for each violation

See `auto_resolve.py` for the implementation using the Mellea framework.

## Scripts

### Extract Violations
Extract all violations from a Conforma log file:
```bash
python3 extract_violations.py <log_file> [--json]
```

Example:
```bash
python3 extract_violations.py managed-zxd9h-verify-conforma.log
```

### Extract Policy
Extract the policy configuration from a Conforma log file:
```bash
python3 extract_policy.py <log_file> [--json] [--pretty]
```

Example:
```bash
python3 extract_policy.py managed-zxd9h-verify-conforma.log --json --pretty
```

### Extract Image References
Extract image references from the STEP-VALIDATE section:
```bash
python3 extract_image_refs.py <log_file> [--json] [--first]
```

Example:
```bash
# Get all image references
python3 extract_image_refs.py managed-zxd9h-verify-conforma.log

# Get only the first image reference
python3 extract_image_refs.py managed-zxd9h-verify-conforma.log --first
```

### Extract Component Information
Extract component information (git URLs and revisions) from the log file:
```bash
python3 extract_components.py <log_file> [--json] [--name <component-name>]
```

Example:
```bash
# Get all components
python3 extract_components.py lifecycle-agent-conforma-staging-on-pr-4-20-4n2pl-verify.log

# Get a specific component by name
python3 extract_components.py lifecycle-agent-conforma-staging-on-pr-4-20-4n2pl-verify.log --name recert-4-20

# Output as JSON
python3 extract_components.py lifecycle-agent-conforma-staging-on-pr-4-20-4n2pl-verify.log --name recert-4-20 --json
```

## How to Reproduce Violations

To reproduce a violation locally using the Conforma CLI, follow these steps:

### 1. Clone and Build the CLI

```bash
# Clone the Conforma CLI repository
git clone git@github.com:conforma/cli.git

# Build the CLI
cd cli
make build
```

### 2. Extract Required Values from the Log File

You need three values from the log file:

1. **IMAGE**: The image reference from the `STEP-VALIDATE` section (found in the `ImageRef` field, or `COMPONENTS` list if multiple)
2. **POLICY**: The policy configuration (extracted from the `STEP-SHOW-CONFIG` section)
3. **PUBLIC_KEY**: The public key from the policy configuration (found in the `key` field)

#### Using the Extraction Scripts

```bash
LOG_FILE="managed-zxd9h-verify-conforma.log"

# Extract the image reference from STEP-VALIDATE section
IMAGE=$(python3 extract_image_refs.py "${LOG_FILE}" --first)

# Extract the policy JSON (only the policy section) and save to a file
python3 extract_policy.py "${LOG_FILE}" --json --pretty > /tmp/policy.json
POLICY_FILE="/tmp/policy.json"

# Extract the public key from the policy and save to a file
python3 extract_policy.py "${LOG_FILE}" --pretty | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['key'])" > /tmp/public_key.pem
PUBLIC_KEY="/tmp/public_key.pem"
```

Alternatively, you can manually extract:
- **IMAGE**: From the `STEP-VALIDATE` section, use the `ImageRef` value (or `COMPONENTS` list if multiple)
- **POLICY**: From the `STEP-SHOW-CONFIG` section, extract the `policy` object
- **PUBLIC_KEY**: From the `STEP-SHOW-CONFIG` section, extract the `key` field value

### 3. Run the Validation

```bash
cd cli

./dist/ec validate image \
  --image "${IMAGE}" \
  --policy "${POLICY_FILE}" \
  --public-key "${PUBLIC_KEY}" \
  --ignore-rekor \
  --output text
```

**Note:** If you encounter errors about missing OCI data bundles (e.g., `konflux-vanguard/data-acceptable-bundles`), you may need to remove that data source from the policy temporarily. The validation will still work and reproduce the violations.

This should reproduce the same violations found in the log file.

## Locating Pipeline Definitions

When fixing violations related to Tekton Tasks or Pipelines (e.g., `trusted_task.trusted`, `tasks.required_untrusted_task_found`), you need to locate the pipeline definition in the component's git repository.

### Finding the Component Git Repository

The git repository for each component is defined in the log file under the `components` field (or `component` for single component mode). The structure looks like:

```json
{
  "components": [
    {
      "name": "component-name",
      "containerImage": "quay.io/...",
      "source": {
        "git": {
          "url": "https://github.com/org/repo.git",
          "revision": "commit-sha",
          "dockerfileUrl": "Dockerfile"
        }
      }
    }
  ]
}
```

### Pipeline Location

Pipeline definitions are located in the `.tekton` directory of the component's git repository:

```
<component-repo>/
  .tekton/
    pipeline.yaml          # Main pipeline definition
    pipeline-run.yaml     # PipelineRun definitions (if any)
    tasks/                 # Task definitions (if any)
    ...
```

### Steps to Fix Pipeline-Related Violations

1. **Extract component information from the log**:
   ```bash
   # Extract component information using the script
   python3 extract_components.py log-file.log --name <component-name>
   
   # Or get all components
   python3 extract_components.py log-file.log
   
   # Or output as JSON for easier parsing
   python3 extract_components.py log-file.log --name <component-name> --json
   ```

2. **Clone the component repository**:
   ```bash
   git clone <git-url>
   cd <repo-name>
   git checkout <revision>
   ```

3. **Locate the pipeline definition**:
   ```bash
   cd .tekton
   ls -la
   ```

4. **Update the pipeline** to fix the violation (e.g., update task references to use trusted versions)

5. **Commit and push** the changes

6. **Rebuild the image** to verify the fix

## Policy Rules

To understand or modify the policy rules:

```bash
# Clone the policy repository
git clone git@github.com:conforma/policy.git

# Rules are located in:
policy/release/
```

### Rule Naming Convention

Violations reference rules using the format: `package.rule_name`

For example:
- `sbom_spdx.allowed_package_sources` means:
  - Package: `sbom_spdx`
  - Rule: `allowed_package_sources`
  - File location: `policy/release/sbom_spdx/allowed_package_sources.rego` (or similar)


### Artifacts the Policy Rules Examine
- **attestation**: Contains build provenance and metadata
- **sbom**: Contains the list of packages and their sources

#### Download the Attestation
```bash
cosign download attestation ${IMAGE} | jq .payload | tr -d '"' | base64 -d | jq
```

#### Download the SBOM
```bash
cosign download sbom ${IMAGE}
```

## Policy Configuration Schema

The policy configuration follows the [EnterpriseContractPolicy CRD schema](https://raw.githubusercontent.com/conforma/crds/refs/heads/main/config/crd/bases/appstudio.redhat.com_enterprisecontractpolicies.yaml). The key structure is:

```yaml
spec:
  sources:
    - name: <optional-name>
      policy:
        - <policy-source-url>  # e.g., "oci::quay.io/enterprise-contract/ec-release-policy:latest"
      data:
        - <data-source-url>    # Optional: additional data sources
      config:
        include:
          - <rule-pattern>     # e.g., "@redhat", "test", "java"
        exclude:
          - <rule-pattern>     # e.g., "cve.cve_blockers", "sbom_spdx.allowed_package_sources:pkg:..."
      ruleData:
        <key>: <value>         # Arbitrary key-value data visible to policy rules
      volatileConfig:
        exclude:
          - value: <rule-pattern>
            effectiveUntil: <date-time>  # Optional: time-based exclusion
            reference: <url>              # Optional: link to related info
            imageDigest: <sha256:...>    # Optional: image-specific exclusion
```

### Key Configuration Fields

- **`sources`**: Array of policy source groups. Each source defines:
  - **`policy`**: List of policy source URLs (required, minItems: 1)
  - **`data`**: List of data source URLs (optional)
  - **`config`**: Rule filtering configuration
    - **`include`**: Rules to include (takes precedence over excludes)
    - **`exclude`**: Rules to exclude (failures don't block success)
  - **`ruleData`**: Key-value data accessible to policy rules
  - **`volatileConfig`**: Time-based or image-specific exclusions

### Exclusion Format

**⚠️ Important: Exclusions should be used as a last resort.** Before adding exclusions, understand what the rule checks and determine the appropriate fix.

Policy rules examine:
- **Attestation**: Build provenance, metadata, and build process information
- **SBOM**: Software Bill of Materials containing package lists and their sources
- **Image**: Direct inspection of the container image contents

The appropriate fix depends on what the rule is checking:

1. **Configure rule data**: Some rules support configuration via `ruleData` (e.g., `allowed_package_sources` for `sbom_spdx.allowed_package_sources`). Check the rule's documentation or source code in `policy/release/` to see if ruleData configuration is available.

2. **Fix the underlying issue**: 
   - If the rule checks the SBOM, fix the build process to use allowed sources or generate correct SBOM data
   - If the rule checks the attestation, fix the build process to produce compliant attestations
   - If the rule inspects the image, modify the image contents or build process to meet requirements

3. **Review all available rules**: See all policy rules in the [policy repository](https://github.com/conforma/policy) under `policy/release/` to understand what each rule validates and what configuration options are available.

Exclusions bypass rule functionality and don't scale well. Only use them when:
- Rule data configuration is not available or insufficient for the use case
- Fixing the underlying issue (build process, image contents, etc.) is not feasible
- The violation represents an acceptable exception that needs to be documented

Exclusions can be specified in several formats:

1. **Rule name only**: `"cve.cve_blockers"` - excludes all instances of the rule
2. **Rule with term**: `"sbom_spdx.allowed_package_sources:pkg:generic/..."` - excludes specific instances
3. **Collection**: `"@redhat"` - includes/excludes a predefined collection

### Volatile Configuration

Volatile exclusions support time-based and image-specific filtering:

```yaml
volatileConfig:
  exclude:
    - value: "test.no_failed_tests:sast-coverity-check"
      effectiveUntil: "2025-12-30T00:00:00Z"
      reference: "https://issues.redhat.com/browse/PSSECAUT-1051"
    - value: "some.rule"
      imageDigest: "sha256:1e7b633db296319a1c62b1ff026e12e2f830382f1201f55240996c5fc473b3aa"
```

For the complete schema definition, see the [EnterpriseContractPolicy CRD](https://raw.githubusercontent.com/conforma/crds/refs/heads/main/config/crd/bases/appstudio.redhat.com_enterprisecontractpolicies.yaml).
