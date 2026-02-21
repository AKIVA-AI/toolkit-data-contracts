# Toolkit Data Contracts and Drift Detection

Enterprise-grade data contract management and drift detection for ML/LLM pipelines to prevent silent schema changes and data quality regressions.

## Overview

The Toolkit Data Contracts and Drift Detection tool provides a lightweight, dependency-free solution for maintaining data quality and consistency in machine learning pipelines. It automatically infers data contracts from samples, validates new data against established contracts, and detects drift before it impacts model performance.

## Key Features

### Contract Management
- **Automatic Contract Inference**: Generate contracts from JSONL samples
- **Schema Validation**: Enforce data structure and type constraints
- **Version Control**: Track contract evolution over time
- **Flexible Configuration**: Allow extra fields, required fields, custom types

### Drift Detection
- **Statistical Profiling**: Build comprehensive baseline profiles
- **Distribution Analysis**: Track changes in data distributions
- **Quality Gates**: Automated validation with configurable thresholds
- **CI/CD Integration**: Exit codes for pipeline integration

### Enterprise Features
- **Zero Dependencies**: Lightweight, easy to deploy
- **CLI Interface**: Simple command-line tools
- **JSON Format**: Human-readable contracts and profiles
- **Batch Processing**: Handle large datasets efficiently

## Quick Start

### Installation

```bash
# Install from source
git clone <your-repo-url>
cd data-contracts-drift
pip install -e ".[dev]"

# Install in production
pip install toolkit-data-contracts-drift
```

### Basic Usage

```bash
# 1. Infer contract from sample data
toolkit-contracts infer --input samples.jsonl --out contract.json

# 2. Create baseline profile
toolkit-contracts profile --input baseline.jsonl --contract contract.json --out baseline.profile.json

# 3. Validate new data and check for drift
toolkit-contracts check --input new_batch.jsonl --contract contract.json --baseline baseline.profile.json
```

## CLI Commands

- `infer` - Generate contract from JSONL samples
- `profile` - Create baseline profile from data
- `check` - Validate data and detect drift

## Exit Codes

- `0` - Validation passed
- `4` - Validation failed or drift detected

## License

MIT License - see LICENSE file for details.
