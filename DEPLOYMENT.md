# Toolkit Data Contracts & Drift Detection - Deployment Guide

## ðŸš€ Quick Start

### Prerequisites
- Python 3.9+
- Docker & Docker Compose (optional)

### Option 1: Docker Deployment (Recommended)

```bash
# Navigate to directory
cd data-contracts-drift

# Build image
docker-compose build

# Run contract inference
docker-compose run --rm infer

# Run drift check
docker-compose run --rm check

# Interactive shell
docker-compose run --rm data-contracts bash
```

### Option 2: Local Installation

```bash
# Install from source
pip install -e ".[dev]"

# Verify installation
toolkit-contracts --version

# Run tests
pytest
```

## ðŸ”§ Configuration

### Environment Variables

See `.env.example` for all options.

**Key Settings:**
- `DEFAULT_SAMPLE_SIZE`: Number of samples for contract inference
- `DEFAULT_DRIFT_THRESHOLD`: Sensitivity for drift detection
- `STRICT_TYPE_CHECKING`: Enable strict type validation

### CLI Usage

```bash
# Infer contract
toolkit-contracts infer \
  --input data/samples.jsonl \
  --out contracts/contract.json \
  --sample-size 1000

# Create baseline profile
toolkit-contracts profile \
  --input data/baseline.jsonl \
  --contract contracts/contract.json \
  --out profiles/baseline.profile.json

# Check for drift
toolkit-contracts check \
  --input data/new_batch.jsonl \
  --contract contracts/contract.json \
  --baseline profiles/baseline.profile.json \
  --threshold 0.1
```

## ðŸ“Š Production Deployment

### 1. CI/CD Integration

**GitHub Actions Example:**
```yaml
- name: Check Data Quality
  run: |
    toolkit-contracts check \
      --input data/production_batch.jsonl \
      --contract contracts/production.json \
      --baseline profiles/baseline.profile.json
```

**Exit Codes:**
- `0`: No drift detected, all validations passed
- `1`: Drift detected or validation failures
- `2`: Error in execution

### 2. Batch Processing

```bash
# Process large datasets
for file in data/*.jsonl; do
  toolkit-contracts check \
    --input "$file" \
    --contract contract.json \
    --baseline baseline.profile.json \
    --verbose
done
```

### 3. Monitoring Integration

```python
from toolkit_data_contracts_drift.monitoring import get_health_status

# Check system health
status = get_health_status()
print(status)

# Check specific contract
from pathlib import Path
status = get_health_status(contract_path=Path("contract.json"))
```

## ðŸ”’ Security

### 1. Data Privacy
- Contracts contain schema information only, not actual data
- Profiles contain statistical summaries, not raw data
- No data is transmitted externally

### 2. File Permissions
```bash
# Restrict contract files
chmod 600 contracts/*.json

# Restrict profile files
chmod 600 profiles/*.json
```

## ðŸ“ˆ Best Practices

### 1. Contract Management
- Version contracts with your code
- Store contracts in version control
- Update contracts when schema changes
- Document contract changes

### 2. Baseline Profiles
- Create profiles from representative data
- Update profiles periodically
- Store multiple profiles for different time periods
- Monitor profile drift over time

### 3. Drift Detection
- Set appropriate thresholds for your use case
- Monitor drift trends, not just individual checks
- Investigate drift causes before updating baselines
- Alert on significant drift

## ðŸ› Troubleshooting

### Common Issues

**Contract Inference Fails:**
```bash
# Ensure input is valid JSONL
cat data/samples.jsonl | jq -c . > data/valid.jsonl

# Check sample size
toolkit-contracts infer --input data/samples.jsonl --sample-size 100
```

**Drift Always Detected:**
```bash
# Lower threshold
toolkit-contracts check --threshold 0.2

# Check baseline profile
cat profiles/baseline.profile.json | jq .
```

**Performance Issues:**
```bash
# Increase batch size
export BATCH_SIZE=50000

# Use multiple workers
export MAX_WORKERS=8
```

## ðŸ“ž Support

- Documentation: [README.md](README.md)
- Examples: [examples/](examples/)
- Issues: GitHub Issues
- Email: <support-email>




