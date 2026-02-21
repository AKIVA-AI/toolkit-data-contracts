"""
Example: ML Pipeline Data Quality with Contracts

This example demonstrates how to use data contracts in an ML pipeline
to ensure data quality and detect drift.
"""

import json
from pathlib import Path
from toolkit_data_contracts_drift.contract import infer_contract, validate_data, create_profile, check_drift


def main():
    """Main example workflow"""
    print("=" * 60)
    print("ðŸ” Toolkit Data Contracts - ML Pipeline Example")
    print("=" * 60)
    
    # Step 1: Create sample training data
    print("\nðŸ“Š Step 1: Creating sample training data...")
    training_data = [
        {
            "user_id": 1001,
            "age": 25,
            "income": 50000,
            "credit_score": 720,
            "loan_amount": 10000,
            "approved": True
        },
        {
            "user_id": 1002,
            "age": 35,
            "income": 75000,
            "credit_score": 680,
            "loan_amount": 15000,
            "approved": True
        },
        {
            "user_id": 1003,
            "age": 45,
            "income": 60000,
            "credit_score": 650,
            "loan_amount": 20000,
            "approved": False
        },
    ]
    
    # Save training data
    training_file = Path("training_data.jsonl")
    with open(training_file, "w") as f:
        for record in training_data:
            f.write(json.dumps(record) + "\n")
    print(f"âœ… Created {len(training_data)} training records")
    
    # Step 2: Infer contract from training data
    print("\nðŸ“ Step 2: Inferring data contract...")
    contract = infer_contract(training_data)
    
    contract_file = Path("loan_contract.json")
    with open(contract_file, "w") as f:
        json.dump(contract, f, indent=2)
    
    print(f"âœ… Contract inferred with {len(contract['schema']['fields'])} fields")
    print(f"   Fields: {', '.join(contract['schema']['fields'].keys())}")
    
    # Step 3: Create baseline profile
    print("\nðŸ“ˆ Step 3: Creating baseline profile...")
    profile = create_profile(training_data, contract)
    
    profile_file = Path("baseline_profile.json")
    with open(profile_file, "w") as f:
        json.dump(profile, f, indent=2)
    
    print(f"âœ… Baseline profile created")
    print(f"   Total records: {profile['total_records']}")
    
    # Step 4: Validate new production data
    print("\nâœ… Step 4: Validating new production data...")
    production_data = [
        {
            "user_id": 2001,
            "age": 30,
            "income": 65000,
            "credit_score": 700,
            "loan_amount": 12000,
            "approved": True
        },
        {
            "user_id": 2002,
            "age": 28,
            "income": 55000,
            "credit_score": 690,
            "loan_amount": 8000,
            "approved": True
        },
    ]
    
    validation_results = []
    for record in production_data:
        result = validate_data(record, contract)
        validation_results.append(result)
    
    passed = sum(1 for r in validation_results if r["valid"])
    print(f"âœ… Validation: {passed}/{len(production_data)} records passed")
    
    # Step 5: Check for drift
    print("\nðŸ” Step 5: Checking for data drift...")
    drift_result = check_drift(production_data, contract, profile)
    
    if drift_result["drift_detected"]:
        print(f"âš ï¸  Drift detected!")
        print(f"   Drift score: {drift_result['drift_score']:.3f}")
        print(f"   Affected fields: {', '.join(drift_result.get('drifted_fields', []))}")
    else:
        print(f"âœ… No significant drift detected")
        print(f"   Drift score: {drift_result['drift_score']:.3f}")
    
    # Step 6: Simulate drift scenario
    print("\nâš¡ Step 6: Simulating drift scenario...")
    drifted_data = [
        {
            "user_id": 3001,
            "age": 22,  # Younger age
            "income": 35000,  # Lower income
            "credit_score": 600,  # Lower credit score
            "loan_amount": 25000,  # Higher loan amount
            "approved": False
        },
        {
            "user_id": 3002,
            "age": 21,
            "income": 30000,
            "credit_score": 580,
            "loan_amount": 30000,
            "approved": False
        },
    ]
    
    drift_result = check_drift(drifted_data, contract, profile)
    
    if drift_result["drift_detected"]:
        print(f"âš ï¸  Drift detected in simulated data!")
        print(f"   Drift score: {drift_result['drift_score']:.3f}")
        print(f"   This indicates the data distribution has changed significantly")
    
    # Cleanup
    print("\nðŸ§¹ Cleaning up example files...")
    training_file.unlink()
    contract_file.unlink()
    profile_file.unlink()
    
    print("\n" + "=" * 60)
    print("âœ… Example Complete!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("1. Infer contracts from training data")
    print("2. Create baseline profiles for drift detection")
    print("3. Validate production data against contracts")
    print("4. Monitor for drift to catch data quality issues")
    print("5. Integrate into CI/CD pipelines for automated checks")


if __name__ == "__main__":
    main()



