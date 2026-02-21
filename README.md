# Toolkit Data Contracts & Drift Detection

Enterprise-grade data contract management and drift detection for ML/LLM pipelines to prevent silent schema changes and data quality regressions.

## Overview

The Toolkit Data Contracts & Drift Detection tool provides a lightweight, dependency-free solution for maintaining data quality and consistency in machine learning pipelines. It automatically infers data contracts from samples, validates new data against established contracts, and detects drift before it impacts model performance.

## Key Features

### ðŸ“‹ **Contract Management**
- **Automatic Contract Inference**: Generate contracts from JSONL samples
- **Schema Validation**: Enforce data structure and type constraints
- **Version Control**: Track contract evolution over time
- **Flexible Configuration**: Allow extra fields, required fields, custom types

### ðŸ” **Drift Detection**
- **Statistical Profiling**: Build comprehensive baseline profiles
- **Distribution Analysis**: Track changes in data distributions
- **Quality Gates**: Automated validation with configurable thresholds
- **CI/CD Integration**: Exit codes for pipeline integration

### ðŸš€ **Enterprise Features**
- **Zero Dependencies**: Lightweight, easy to deploy
- **CLI Interface**: Simple command-line tools
- **JSON Format**: Human-readable contracts and profiles
- **Batch Processing**: Handle large datasets efficiently

## Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   Data Samples  â”‚â”€â”€â”€â–¶â”‚ Contract Inferenceâ”‚â”€â”€â”€â–¶â”‚ Data Contract  â”‚
â”‚                 â”‚    â”‚                 â”‚    â”‚                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                                         â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   New Data      â”‚â”€â”€â”€â–¶â”‚  Validation     â”‚â—€â”€â”€â”€â”‚ Baseline Profileâ”‚
â”‚                 â”‚    â”‚                 â”‚    â”‚                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                 â”‚
                                 â–¼
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â”‚  Drift Report   â”‚
                       â”‚                 â”‚
                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

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

## Detailed Usage

### 1. Contract Inference

Generate a data contract from your sample data:

```bash
toolkit-contracts infer \
  --input samples.jsonl \
  --out contract.json \
  --sample-size 1000 \
  --confidence-threshold 0.95
```

**Sample Input (`samples.jsonl`):**
```json
{"user_id": 12345, "name": "John Doe", "email": "john@example.com", "age": 30, "active": true}
{"user_id": 67890, "name": "Jane Smith", "email": "jane@example.com", "age": 25, "active": false}
```

**Generated Contract (`contract.json`):**
```json
{
  "version": 1,
  "inferred_at": "2024-01-15T10:30:00Z",
  "sample_size": 1000,
  "confidence_threshold": 0.95,
  "allow_extra_fields": true,
  "fields": {
    "user_id": {
      "types": ["integer"],
      "required": true,
      "min_value": 1,
      "max_value": 999999,
      "null_count": 0,
      "confidence": 1.0
    },
    "name": {
      "types": ["string"],
      "required": true,
      "min_length": 1,
      "max_length": 100,
      "pattern": "^[A-Za-z\\s]+$",
      "confidence": 0.98
    },
    "email": {
      "types": ["string"],
      "required": true,
      "pattern": "^[\\w\\.-]+@[\\w\\.-]+\\.[a-zA-Z]{2,}$",
      "confidence": 0.95
    },
    "age": {
      "types": ["integer"],
      "required": false,
      "min_value": 18,
      "max_value": 100,
      "confidence": 0.92
    },
    "active": {
      "types": ["boolean"],
      "required": true,
      "confidence": 1.0
    }
  },
  "statistics": {
    "total_fields": 5,
    "required_fields": 4,
    "optional_fields": 1,
    "inference_confidence": 0.97
  }
}
```

### 2. Baseline Profiling

Create a comprehensive profile of your baseline data:

```bash
toolkit-contracts profile \
  --input baseline.jsonl \
  --contract contract.json \
  --out baseline.profile.json \
  --include-distributions \
  --percentiles [25,50,75,90,95,99]
```

**Generated Profile (`baseline.profile.json`):**
```json
{
  "profile_version": 1,
  "created_at": "2024-01-15T10:35:00Z",
  "dataset_info": {
    "total_records": 10000,
    "file_size_mb": 45.2,
    "processing_time_seconds": 2.3
  },
  "field_profiles": {
    "user_id": {
      "type": "integer",
      "count": 10000,
      "null_count": 0,
      "unique_count": 10000,
      "statistics": {
        "min": 1,
        "max": 999999,
        "mean": 500000.5,
        "std": 288675.1,
        "percentiles": {
          "p25": 250000.75,
          "p50": 500000.5,
          "p75": 750000.25,
          "p90": 900000.1,
          "p95": 950000.05,
          "p99": 990000.01
        }
      },
      "distribution": {
        "histogram": [
          {"range": [1, 100000], "count": 1000},
          {"range": [100001, 200000], "count": 1000},
          {"range": [200001, 300000], "count": 1000},
          {"range": [300001, 400000], "count": 1000},
          {"range": [400001, 500000], "count": 1000},
          {"range": [500001, 600000], "count": 1000},
          {"range": [600001, 700000], "count": 1000},
          {"range": [700001, 800000], "count": 1000},
          {"range": [800001, 900000], "count": 1000},
          {"range": [900001, 999999], "count": 1000}
        ]
      }
    },
    "age": {
      "type": "integer",
      "count": 9500,
      "null_count": 500,
      "unique_count": 83,
      "statistics": {
        "min": 18,
        "max": 100,
        "mean": 35.2,
        "std": 12.8,
        "percentiles": {
          "p25": 25,
          "p50": 34,
          "p75": 45,
          "p90": 58,
          "p95": 67,
          "p99": 85
        }
      }
    }
  }
}
```

### 3. Validation and Drift Detection

Validate new data against contracts and detect drift:

```bash
toolkit-contracts check \
  --input new_batch.jsonl \
  --contract contract.json \
  --baseline baseline.profile.json \
  --drift-threshold 0.1 \
  --output validation_report.json \
  --verbose
```

**Validation Report (`validation_report.json`):**
```json
{
  "validation_result": {
    "status": "failed",
    "exit_code": 4,
    "timestamp": "2024-01-15T10:40:00Z",
    "summary": {
      "total_records": 1000,
      "valid_records": 850,
      "invalid_records": 150,
      "validation_rate": 0.85
    },
    "contract_violations": {
      "missing_required_fields": 45,
      "type_mismatches": 23,
      "value_constraints": 12,
      "pattern_violations": 8
    },
    "drift_analysis": {
      "overall_drift_score": 0.23,
      "drift_detected": true,
      "drift_threshold": 0.1,
      "field_drift": {
        "age": {
          "drift_score": 0.34,
          "drift_type": "distribution_shift",
          "baseline_mean": 35.2,
          "current_mean": 42.8,
          "statistical_test": "ks_test",
          "p_value": 0.001
        },
        "user_id": {
          "drift_score": 0.05,
          "drift_type": "none",
          "status": "stable"
        }
      }
    },
    "recommendations": [
      "Update contract to allow null values for age field",
      "Investigate age distribution shift - possible data quality issue",
      "Consider retraining model if age shift is permanent"
    ]
  }
}
```

## Advanced Configuration

### Contract Configuration

Create custom contract configurations:

```json
{
  "version": 1,
  "allow_extra_fields": false,
  "strict_mode": true,
  "field_validation": {
    "user_id": {
      "types": ["integer"],
      "required": true,
      "constraints": {
        "min": 1,
        "max": 1000000
      }
    },
    "email": {
      "types": ["string"],
      "required": true,
      "constraints": {
        "pattern": "^[\\w\\.-]+@[\\w\\.-]+\\.[a-zA-Z]{2,}$",
        "max_length": 255
      }
    },
    "age": {
      "types": ["integer", "null"],
      "required": false,
      "constraints": {
        "min": 0,
        "max": 150
      }
    }
  },
  "drift_detection": {
    "enabled": true,
    "threshold": 0.1,
    "statistical_tests": ["ks_test", "chi_square"],
    "features": ["age", "user_id"]
  }
}
```

### CLI Options

```bash
# Contract inference options
toolkit-contracts infer \
  --input samples.jsonl \
  --out contract.json \
  --sample-size 1000 \
  --confidence-threshold 0.95 \
  --include-nulls \
  --strict-types

# Profiling options
toolkit-contracts profile \
  --input baseline.jsonl \
  --contract contract.json \
  --out baseline.profile.json \
  --include-distributions \
  --percentiles [25,50,75,90,95,99] \
  --histogram-bins 50 \
  --correlation-matrix

# Validation options
toolkit-contracts check \
  --input new_batch.jsonl \
  --contract contract.json \
  --baseline baseline.profile.json \
  --drift-threshold 0.1 \
  --output report.json \
  --verbose \
  --fail-on-drift \
  --sample-validation
```

## Integration Examples

### CI/CD Pipeline Integration

```yaml
# .github/workflows/data-validation.yml
name: Data Quality Validation

on:
  push:
    paths: ['data/**']
  pull_request:
    paths: ['data/**']

jobs:
  validate-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Toolkit Data Contracts
        run: pip install toolkit-data-contracts-drift
      
      - name: Validate New Data
        run: |
          toolkit-contracts check \
            --input data/new_batch.jsonl \
            --contract contracts/data_contract.json \
            --baseline profiles/baseline.profile.json \
            --drift-threshold 0.1 \
            --fail-on-drift
      
      - name: Upload Validation Report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: validation-report
          path: validation_report.json
```

### Python API Integration

```python
from toolkit_data_contracts_drift import ContractInferencer, ProfileBuilder, DriftDetector

# Initialize components
inferencer = ContractInferencer()
profiler = ProfileBuilder()
detector = DriftDetector()

# Infer contract from samples
contract = inferencer.infer_from_file(
    "samples.jsonl",
    sample_size=1000,
    confidence_threshold=0.95
)

# Save contract
contract.save("contract.json")

# Build baseline profile
profile = profiler.build_profile(
    "baseline.jsonl",
    contract=contract,
    include_distributions=True
)

# Save profile
profile.save("baseline.profile.json")

# Validate new data
validation_result = detector.validate_and_detect_drift(
    "new_batch.jsonl",
    contract=contract,
    baseline_profile=profile,
    drift_threshold=0.1
)

# Handle results
if validation_result.drift_detected:
    print(f"âš ï¸  Drift detected with score: {validation_result.drift_score}")
    for recommendation in validation_result.recommendations:
        print(f"ðŸ’¡ {recommendation}")
else:
    print("âœ… Data validation passed")

# Exit with appropriate code for CI/CD
exit(validation_result.exit_code)
```

### Airflow Integration

```python
# airflow/dags/data_quality_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from toolkit_data_contracts_drift import DriftDetector
import json

def validate_data_quality(**context):
    detector = DriftDetector()
    
    validation_result = detector.validate_and_detect_drift(
        input_file="{{ var.value.data_path }}/new_batch.jsonl",
        contract_file="{{ var.value.contract_path }}/contract.json",
        baseline_profile_file="{{ var.value.profile_path }}/baseline.profile.json",
        drift_threshold=0.1
    )
    
    # Store results
    validation_result.save("/tmp/validation_report.json")
    
    # Push to XCom for downstream tasks
    context['task_instance'].xcom_push(
        key='validation_result',
        value=validation_result.to_dict()
    )
    
    if validation_result.drift_detected:
        raise ValueError(f"Data drift detected: {validation_result.drift_score}")

with DAG(
    'data_quality_validation',
    schedule_interval='@hourly',
    start_date=datetime(2024, 1, 1),
    catchup=False
) as dag:
    
    validate_task = PythonOperator(
        task_id='validate_data_quality',
        python_callable=validate_data_quality
    )
```

## Production Deployment

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Toolkit Data Contracts
RUN pip install toolkit-data-contracts-drift

# Copy contracts and profiles
COPY contracts/ /app/contracts/
COPY profiles/ /app/profiles/

# Create entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
```

```bash
# entrypoint.sh
#!/bin/bash
set -e

echo "Starting Toolkit Data Contracts validation..."

# Validate new data
toolkit-contracts check \
  --input /data/new_batch.jsonl \
  --contract /app/contracts/data_contract.json \
  --baseline /app/profiles/baseline.profile.json \
  --drift-threshold ${DRIFT_THRESHOLD:-0.1} \
  --output /reports/validation_report.json \
  --verbose

echo "Validation completed with exit code: $?"
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: data-contracts-validation
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: data-contracts
            image: akiva/data-contracts:latest
            env:
            - name: DRIFT_THRESHOLD
              value: "0.1"
            volumeMounts:
            - name: data-volume
              mountPath: /data
            - name: config-volume
              mountPath: /app/config
            command:
            - toolkit-contracts
            - check
            - --input
            - /data/new_batch.jsonl
            - --contract
            - /app/config/contract.json
            - --baseline
            - /app/config/baseline.profile.json
            - --drift-threshold
            - $(DRIFT_THRESHOLD)
          volumes:
          - name: data-volume
            persistentVolumeClaim:
              claimName: data-pvc
          - name: config-volume
            configMap:
              name: data-contracts-config
          restartPolicy: OnFailure
```

## Monitoring and Alerting

### Prometheus Metrics

```python
# Export validation metrics to Prometheus
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
VALIDATION_COUNTER = Counter('data_contracts_validations_total', 'Total validations', ['status'])
DRIFT_SCORE_GAUGE = Gauge('data_contracts_drift_score', 'Latest drift score')
VALIDATION_DURATION = Histogram('data_contracts_validation_duration_seconds', 'Validation duration')

def validate_with_metrics(input_file, contract_file, baseline_file):
    with VALIDATION_DURATION.time():
        result = detector.validate_and_detect_drift(
            input_file, contract_file, baseline_file
        )
    
    # Update metrics
    VALIDATION_COUNTER.labels(status=result.status).inc()
    DRIFT_SCORE_GAuge.set(result.drift_score)
    
    return result
```

### Slack Integration

```python
import requests
import json

def send_slack_alert(validation_result):
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK"
    
    if validation_result.drift_detected:
        message = {
            "text": "ðŸš¨ Data Drift Detected",
            "attachments": [{
                "color": "danger",
                "fields": [
                    {"title": "Drift Score", "value": str(validation_result.drift_score), "short": True},
                    {"title": "Validation Rate", "value": f"{validation_result.validation_rate:.2%}", "short": True},
                    {"title": "Top Issues", "value": "\n".join(validation_result.recommendations[:3]), "short": False}
                ]
            }]
        }
        
        requests.post(webhook_url, json=message)
```

## Troubleshooting

### Common Issues

#### Contract Inference Fails
```bash
# Check data format
head -n 5 samples.jsonl

# Validate JSONL format
python -c "import json; [json.loads(line) for line in open('samples.jsonl')]"

# Increase sample size
toolkit-contracts infer --input samples.jsonl --out contract.json --sample-size 5000
```

#### High False Positive Drift
```bash
# Adjust drift threshold
toolkit-contracts check --input new_batch.jsonl --contract contract.json --baseline baseline.profile.json --drift-threshold 0.2

# Use specific statistical tests
toolkit-contracts check --input new_batch.jsonl --contract contract.json --baseline baseline.profile.json --statistical-tests ks_test
```

#### Performance Issues
```bash
# Sample validation for large datasets
toolkit-contracts check --input large_dataset.jsonl --contract contract.json --baseline baseline.profile.json --sample-validation --sample-size 10000

# Parallel processing
export Toolkit_CONTRACTS_WORKERS=4
toolkit-contracts check --input large_dataset.jsonl --contract contract.json --baseline baseline.profile.json
```

## Best Practices

### Contract Management
1. **Version Control**: Store contracts in Git with proper versioning
2. **Regular Updates**: Re-infer contracts when data evolves significantly
3. **Documentation**: Include field descriptions and business rules
4. **Testing**: Validate contracts against known good and bad datasets

### Drift Detection
1. **Baseline Selection**: Use representative, high-quality baseline data
2. **Threshold Tuning**: Adjust drift thresholds based on business requirements
3. **Monitoring**: Track drift scores over time to identify patterns
4. **Alerting**: Set up appropriate alerts for different drift levels

### CI/CD Integration
1. **Early Validation**: Validate data as early as possible in pipelines
2. **Fail Fast**: Configure pipelines to fail on critical data quality issues
3. **Reporting**: Generate detailed reports for debugging and compliance
4. **Rollback**: Maintain ability to rollback to previous data versions

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone <your-repo-url>
cd data-contracts-drift

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black .

# Run type checking
mypy .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [Full documentation](https://<docs-url>/data-contracts-drift)
- **Issues**: use the hosting repository's issue tracker
- **Community**: [Discord Server](https://discord.gg/akiva)
- **Email**: <support-email>

---

**Toolkit Data Contracts & Drift Detection** - Ensure data quality and prevent silent regressions.

Built with â¤ï¸ by the Toolkit team.



