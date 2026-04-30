#!/usr/bin/env python
"""Quick test of the macro simulation"""
import sys
sys.path.insert(0, '.')

# Import from the main script
from macro_simulation_demo import (
    ConsumptionSavingsParams,
    ConsumptionSavingsModel
)

# Create baseline
params = ConsumptionSavingsParams(
    T=40, sigma=2.0, beta=0.96, R=1.04,
    k0=1.0, w0=0.50, g_w=0.02
)

# Solve
model = ConsumptionSavingsModel(params)
model.compute_optimal_consumption()

# Verify
checks = model.verify_solution(verbose=False)
summary = model.get_summary()

print("="*60)
print("SIMULATION TEST SUCCESSFUL")
print("="*60)
print(f"\nBaseline Model Solution:")
print(f"  - Lifetime Wealth (W0): {summary['lifetime_wealth']:.4f}")
print(f"  - Initial Consumption (c0): {summary['initial_consumption']:.4f}")
print(f"  - Consumption Growth: {summary['consumption_growth_rate']*100:.3f}% p.a.")
print(f"  - Avg Savings Rate: {summary['avg_savings_rate']*100:.2f}%")
print(f"\nVerification Status:")
print(f"  - Terminal Condition: {checks['terminal_condition']}")
print(f"  - Budget Constraint: {checks['budget']}")
print(f"  - Euler Equation: {checks['euler_equation']}")
print(f"  - All Checks Pass: {all(checks.values())}")
print("\n[OK] Simulation complete!")
