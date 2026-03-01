"""
Example: ML Pipeline Data Quality with Contracts

This example demonstrates how to use data contracts in an ML pipeline
to ensure data quality and detect drift.
"""

import json
from pathlib import Path

from toolkit_data_contracts_drift.contract import (
    drift_check,
    infer_contract,
    profile_records,
    validate_records,
)


def main():
    """Main example workflow"""
    print("=" * 60)
    print("Toolkit Data Contracts - ML Pipeline Example")
    print("=" * 60)

    # Step 1: Create sample training data
    print("\nStep 1: Creating sample training data...")
    training_data = [
        {
            "user_id": 1001,
            "age": 25,
            "income": 50000,
            "credit_score": 720,
            "loan_amount": 10000,
            "approved": True,
        },
        {
            "user_id": 1002,
            "age": 35,
            "income": 75000,
            "credit_score": 680,
            "loan_amount": 15000,
            "approved": True,
        },
        {
            "user_id": 1003,
            "age": 45,
            "income": 60000,
            "credit_score": 650,
            "loan_amount": 20000,
            "approved": False,
        },
    ]

    # Save training data
    training_file = Path("training_data.jsonl")
    with open(training_file, "w") as f:
        for record in training_data:
            f.write(json.dumps(record) + "\n")
    print(f"  Created {len(training_data)} training records")

    # Step 2: Infer contract from training data
    print("\nStep 2: Inferring data contract...")
    contract = infer_contract(training_data)

    contract_file = Path("loan_contract.json")
    with open(contract_file, "w") as f:
        json.dump(contract, f, indent=2)

    print(f"  Contract inferred with {len(contract['fields'])} fields")
    print(f"  Fields: {', '.join(contract['fields'].keys())}")

    # Step 3: Create baseline profile
    print("\nStep 3: Creating baseline profile...")
    profile = profile_records(contract=contract, records=training_data)

    profile_file = Path("baseline_profile.json")
    with open(profile_file, "w") as f:
        json.dump(profile.to_json(), f, indent=2)

    print("  Baseline profile created")
    print(f"  Fields profiled: {len(profile.field_stats)}")

    # Step 4: Validate new production data
    print("\nStep 4: Validating new production data...")
    production_data = [
        {
            "user_id": 2001,
            "age": 30,
            "income": 65000,
            "credit_score": 700,
            "loan_amount": 12000,
            "approved": True,
        },
        {
            "user_id": 2002,
            "age": 28,
            "income": 55000,
            "credit_score": 690,
            "loan_amount": 8000,
            "approved": True,
        },
    ]

    issues = validate_records(contract=contract, records=production_data)

    if issues:
        print(f"  Validation found {len(issues)} issues:")
        for issue in issues:
            print(f"    - {issue.field}: {issue.message} (count={issue.count})")
    else:
        print(f"  Validation: {len(production_data)}/{len(production_data)} records passed")

    # Step 5: Check for drift
    print("\nStep 5: Checking for data drift...")
    current_profile = profile_records(contract=contract, records=production_data)
    drift_issues = drift_check(baseline=profile, current=current_profile)

    if drift_issues:
        print("  Drift detected!")
        for issue in drift_issues:
            print(f"    - {issue.field}: {issue.message}")
    else:
        print("  No significant drift detected")

    # Step 6: Simulate drift scenario
    print("\nStep 6: Simulating drift scenario...")
    drifted_data = [
        {
            "user_id": 3001,
            "age": 22,
            "income": 35000,
            "credit_score": 600,
            "loan_amount": 25000,
            "approved": False,
        },
        {
            "user_id": 3002,
            "age": 21,
            "income": 30000,
            "credit_score": 580,
            "loan_amount": 30000,
            "approved": False,
        },
    ]

    drifted_profile = profile_records(contract=contract, records=drifted_data)
    drift_issues = drift_check(baseline=profile, current=drifted_profile)

    if drift_issues:
        print("  Drift detected in simulated data!")
        for issue in drift_issues:
            print(f"    - {issue.field}: {issue.message}")
        print("  This indicates the data distribution has changed significantly")
    else:
        print("  No drift detected (try adjusting thresholds)")

    # Cleanup
    print("\nCleaning up example files...")
    training_file.unlink()
    contract_file.unlink()
    profile_file.unlink()

    print("\n" + "=" * 60)
    print("Example Complete!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("1. Infer contracts from training data")
    print("2. Create baseline profiles for drift detection")
    print("3. Validate production data against contracts")
    print("4. Monitor for drift to catch data quality issues")
    print("5. Integrate into CI/CD pipelines for automated checks")


if __name__ == "__main__":
    main()
