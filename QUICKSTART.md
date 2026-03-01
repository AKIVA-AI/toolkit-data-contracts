# Toolkit Data Contracts & Drift Detection - Quick Start

Get started with data quality monitoring in 5 minutes!

## ðŸš€ Installation

```bash
# Install
pip install -e ".[dev]"

# Verify
toolkit-contracts --help
```

## ðŸ“ Basic Workflow

### 1. Prepare Sample Data

Create `samples.jsonl`:
```json
{"user_id": 1, "age": 25, "income": 50000, "approved": true}
{"user_id": 2, "age": 35, "income": 75000, "approved": true}
{"user_id": 3, "age": 45, "income": 60000, "approved": false}
```

### 2. Infer Contract

```bash
toolkit-contracts infer \
  --input samples.jsonl \
  --out contract.json
```

**Output (`contract.json`):**
```json
{
  "allow_extra_fields": true,
  "fields": {
    "user_id": {"required": true, "types": ["integer"]},
    "age": {"required": true, "types": ["integer"]},
    "income": {"required": true, "types": ["integer"]},
    "approved": {"required": true, "types": ["boolean"]}
  },
  "version": 1
}
```

### 3. Create Baseline Profile

```bash
toolkit-contracts profile \
  --input samples.jsonl \
  --contract contract.json \
  --out baseline.profile.json
```

### 4. Validate New Data

```bash
# Check new batch
toolkit-contracts check \
  --input new_batch.jsonl \
  --contract contract.json \
  --baseline baseline.profile.json
```

**Output:**
```
âœ“ All records valid
âœ“ No significant drift detected
  Drift score: 0.05
```

## ðŸŽ¯ Common Use Cases

### ML Pipeline Validation

```bash
# Before training
toolkit-contracts check \
  --input training_data.jsonl \
  --contract model_contract.json

# Before inference
toolkit-contracts check \
  --input inference_batch.jsonl \
  --contract model_contract.json \
  --baseline training_profile.json
```

### API Data Validation

```python
from toolkit_data_contracts_drift.contract import validate_records
import json

# Load contract
with open("api_contract.json") as f:
    contract = json.load(f)

# Validate request
issues = validate_records(contract=contract, records=[request_data])
if issues:
    return {"error": [i.message for i in issues]}, 400
```

### ETL Quality Gates

```bash
# In your ETL pipeline
toolkit-contracts check \
  --input extracted_data.jsonl \
  --contract etl_contract.json \
  --baseline source_profile.json \
  || exit 1  # Fail pipeline on drift
```

## ðŸ³ Docker Usage

```bash
# Build
docker-compose build

# Run inference
docker-compose run --rm data-contracts \
  toolkit-contracts infer \
  --input /app/data/samples.jsonl \
  --out /app/contracts/contract.json

# Run check
docker-compose run --rm data-contracts \
  toolkit-contracts check \
  --input /app/data/new_batch.jsonl \
  --contract /app/contracts/contract.json \
  --baseline /app/profiles/baseline.profile.json
```

## ðŸ§ª Run Examples

```bash
# ML pipeline example
python examples/ml_pipeline_example.py
```

## ðŸ’¡ Tips

1. **Start Simple**: Infer contracts from clean data
2. **Version Contracts**: Store in version control
3. **Update Baselines**: Refresh profiles periodically
4. **Set Thresholds**: Tune drift sensitivity for your use case
5. **Monitor Trends**: Track drift over time, not just single checks

## ðŸ“š Next Steps

- Read [README.md](README.md) for detailed documentation
- Check [DEPLOYMENT.md](DEPLOYMENT.md) for production setup
- Explore [examples/](examples/) for more use cases
- Review [tests/](tests/) for implementation patterns

## ðŸ†˜ Need Help?

- Full docs: [README.md](README.md)
- Deployment: [DEPLOYMENT.md](DEPLOYMENT.md)
- Support: <support-email>

---

**Ready to ensure data quality? Start validating now!**
