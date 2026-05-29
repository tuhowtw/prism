"""
Dynamic Optimization: Consumption-Savings Model Simulation & Analysis
======================================================================

A comprehensive macro-economic simulation demonstrating consumer optimization
with labor income, calibrated with real-world parameters. 

Covers:
- Model solution using closed-form Euler equation methods
- Four policy experiments (interest rate, patience, income shock, IES)
- Comprehensive visualizations and economic interpretation

Author: Macro Economics Simulation Suite
Based on: Dynamic Optimization & Vibe Coding Lecture Notes
"""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".cache/matplotlib").resolve()))

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass
from typing import Tuple, Dict, List
import warnings
warnings.filterwarnings('ignore')

# Set visualization style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# ============================================================================
# 1. DATA CLASSES & PARAMETER DEFINITIONS
# ============================================================================

@dataclass
class ConsumptionSavingsParams:
    """Parameters for the consumption-savings model with labor income."""
    T: int = 40                    # Planning horizon (working life, years)
    sigma: float = 2.0             # IES parameter (IES = 1/sigma)
    beta: float = 0.96             # Discount factor (annual)
    R: float = 1.04                # Gross real return on savings
    k0: float = 1.0                # Initial capital (normalized)
    w0: float = 0.50               # Initial labor income (normalized)
    g_w: float = 0.02              # Real wage growth rate
    
    def __post_init__(self):
        """Validate parameters."""
        assert 0 < self.beta < 1, "Discount factor must be in (0,1)"
        assert self.sigma > 0, "IES parameter must be positive"
        assert self.R > 0, "Gross return must be positive"
        assert self.k0 >= 0, "Initial capital must be non-negative"
        assert self.w0 >= 0, "Initial income must be non-negative"


# ============================================================================
# 2. CORE MODEL SOLVER
# ============================================================================

class ConsumptionSavingsModel:
    """
    Solves the finite-horizon consumption-savings problem using 
    Euler equation methods with CIES utility.
    
    The consumer maximizes:
        sum_t beta^t * u(c_t)
    
    Subject to:
        c_t + k_{t+1} = R*k_t + w_t
        k_0 given, k_{T+1} = 0 (consume all by end of life)
    
    With CIES utility:
        u(c) = (c^(1-sigma) - 1) / (1-sigma)
    """
    
    def __init__(self, params: ConsumptionSavingsParams):
        self.params = params
        self.income_path = None
        self.lifetime_wealth = None
        self.consumption = None
        self.capital = None
        self.euler_check = None
        self.budget_residual = None
        
    def compute_income_path(self) -> np.ndarray:
        """
        Compute the labor income path.
        w_t = w_0 * (1 + g_w)^t
        """
        t = np.arange(self.params.T + 1)
        income = self.params.w0 * (1 + self.params.g_w)**t
        self.income_path = income
        return income
    
    def compute_lifetime_wealth(self) -> float:
        """
        Compute lifetime wealth (present value of all resources).
        W_0 = R*k_0 + sum_t w_t / R^t
        """
        if self.income_path is None:
            self.compute_income_path()
        
        discount_factors = 1.0 / (self.params.R ** np.arange(self.params.T + 1))
        pv_income = np.sum(self.income_path * discount_factors)
        lifetime_wealth = self.params.R * self.params.k0 + pv_income
        
        self.lifetime_wealth = lifetime_wealth
        return lifetime_wealth
    
    def compute_optimal_consumption(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute optimal consumption and savings paths.
        
        Returns:
            (consumption, capital) paths
        """
        # Compute income and lifetime wealth
        if self.income_path is None:
            self.compute_income_path()
        if self.lifetime_wealth is None:
            self.compute_lifetime_wealth()
        
        params = self.params
        
        # Consumption growth factor: gamma = (beta*R)^(1/sigma)
        beta_R_ratio = params.beta * params.R
        gamma = beta_R_ratio ** (1.0 / params.sigma)
        
        # Discount factor in the denominator: phi = gamma / R
        phi = gamma / params.R
        
        # Initial consumption (closed-form solution)
        if abs(phi - 1.0) < 1e-10:  # Handle case where phi = 1
            c0 = self.lifetime_wealth / (params.T + 1)
        else:
            numerator = 1.0 - phi
            denominator = 1.0 - phi**(params.T + 1)
            c0 = self.lifetime_wealth * (numerator / denominator)
        
        # Consumption path: c_t = gamma^t * c_0
        t = np.arange(params.T + 1)
        consumption = gamma**t * c0
        
        # Capital/savings path: k_{t+1} = R*k_t + w_t - c_t
        capital = np.zeros(params.T + 2)
        capital[0] = params.k0
        
        for t in range(params.T + 1):
            capital[t + 1] = params.R * capital[t] + self.income_path[t] - consumption[t]
        
        self.consumption = consumption
        self.capital = capital
        
        return consumption, capital
    
    def verify_solution(self, verbose: bool = True) -> Dict[str, bool]:
        """
        Verify that the solution satisfies all economic and mathematical conditions.
        
        Returns:
            Dictionary of verification results
        """
        if self.consumption is None or self.capital is None:
            self.compute_optimal_consumption()
        
        checks = {}
        
        # 1. Terminal condition: k_{T+1} = 0
        terminal_error = abs(self.capital[self.params.T + 1])
        checks['terminal_condition'] = terminal_error < 1e-8
        
        # 2. Budget constraint: c_t + k_{t+1} = R*k_t + w_t
        budget_residuals = []
        for t in range(self.params.T + 1):
            lhs = self.consumption[t] + self.capital[t + 1]
            rhs = self.params.R * self.capital[t] + self.income_path[t]
            residuals = abs(lhs - rhs)
            budget_residuals.append(residuals)
        self.budget_residual = np.array(budget_residuals)
        checks['budget'] = np.max(self.budget_residual) < 1e-8
        
        # 3. All consumption positive
        checks['consumption_positive'] = np.all(self.consumption > 0)
        
        # 4. Euler equation: c_{t+1}/c_t = (beta*R)^(1/sigma)
        consumption_growth = self.consumption[1:] / self.consumption[:-1]
        theoretical_growth = (self.params.beta * self.params.R) ** (1.0 / self.params.sigma)
        euler_errors = np.abs(consumption_growth - theoretical_growth)
        self.euler_check = euler_errors
        checks['euler_equation'] = np.max(euler_errors) < 1e-6
        
        if verbose:
            print("\n" + "="*60)
            print("VERIFICATION REPORT")
            print("="*60)
            print(f"[OK] Terminal Condition (k_T+1): {checks['terminal_condition']} "
                  f"(error: {terminal_error:.2e})")
            print(f"[OK] Budget Constraint: {checks['budget']} "
                  f"(max residual: {np.max(self.budget_residual):.2e})")
            print(f"[OK] Consumption Positive: {checks['consumption_positive']}")
            print(f"[OK] Euler Equation: {checks['euler_equation']} "
                  f"(max error: {np.max(euler_errors):.2e})")
            
            all_checks = all(checks.values())
            status = "PASSED" if all_checks else "FAILED"
            print(f"\nOVERALL: {status}")
            print("="*60 + "\n")
        
        return checks
    
    def get_summary(self) -> Dict:
        """Return a summary of key economic metrics."""
        if self.consumption is None:
            self.compute_optimal_consumption()
        
        beta_R = self.params.beta * self.params.R
        consumption_growth_rate = beta_R ** (1.0 / self.params.sigma) - 1
        
        avg_consumption = np.mean(self.consumption)
        avg_savings_rate = np.mean(1.0 - self.consumption / 
                                  (self.params.R * self.capital[:-1] + self.income_path))
        
        return {
            'lifetime_wealth': self.lifetime_wealth,
            'initial_consumption': self.consumption[0],
            'terminal_consumption': self.consumption[-1],
            'avg_consumption': avg_consumption,
            'max_capital': np.max(self.capital[:-1]),
            'consumption_growth_rate': consumption_growth_rate,
            'avg_savings_rate': avg_savings_rate,
        }


# ============================================================================
# 3. VISUALIZATION FUNCTIONS
# ============================================================================

def plot_baseline_dynamics(model: ConsumptionSavingsModel, 
                          save_path: str = None) -> None:
    """
    Create a 2x2 subplot showing the baseline consumption-savings dynamics.
    
    Plots:
    - Top-left: Consumption path
    - Top-right: Capital/savings path
    - Bottom-left: Savings rate
    - Bottom-right: Euler equation verification
    """
    if model.consumption is None:
        model.compute_optimal_consumption()
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Consumption-Savings Dynamics (Baseline)\n'
                 f'β={model.params.beta:.3f}, R={model.params.R:.3f}, σ={model.params.sigma:.3f}',
                 fontsize=14, fontweight='bold')
    
    t = np.arange(model.params.T + 1)
    
    # Plot 1: Consumption Path
    ax = axes[0, 0]
    ax.plot(t, model.consumption, 'o-', linewidth=2, markersize=5, color='steelblue', label='Consumption')
    ax.axhline(np.mean(model.consumption), color='red', linestyle='--', alpha=0.7, label='Mean consumption')
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Consumption (c_t)', fontsize=11)
    ax.set_title('Optimal Consumption Path', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Capital Path
    ax = axes[0, 1]
    t_capital = np.arange(model.params.T + 2)
    ax.plot(t_capital, model.capital, 'o-', linewidth=2, markersize=5, color='darkgreen', label='Capital (k_t)')
    ax.axhline(0, color='red', linestyle='--', alpha=0.5)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Capital (k_t)', fontsize=11)
    ax.set_title('Capital (Savings) Path', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Savings Rate
    ax = axes[1, 0]
    total_income = model.params.R * model.capital[:-1] + model.income_path
    savings_rate = model.capital[1:model.params.T + 1] / total_income
    ax.plot(t, savings_rate * 100, 'o-', linewidth=2, markersize=5, color='darkorange')
    ax.axhline(0, color='red', linestyle='--', alpha=0.5)
    ax.fill_between(t, 0, savings_rate * 100, where=(savings_rate > 0), alpha=0.3, color='green', label='Saving')
    ax.fill_between(t, 0, savings_rate * 100, where=(savings_rate <= 0), alpha=0.3, color='red', label='Dissaving')
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Savings Rate (%)', fontsize=11)
    ax.set_title('Savings Rate over Time', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Euler Equation Check
    ax = axes[1, 1]
    consumption_growth = model.consumption[1:] / model.consumption[:-1]
    theoretical_growth = (model.params.beta * model.params.R) ** (1.0 / model.params.sigma)
    ax.plot(t[:-1], consumption_growth, 'o-', linewidth=2, markersize=5, 
            color='steelblue', alpha=0.7, label='Actual c_{t+1}/c_t')
    ax.axhline(theoretical_growth, color='red', linestyle='--', linewidth=2, 
               label=f'Theoretical (β·R)^(1/σ) = {theoretical_growth:.4f}')
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Consumption Growth', fontsize=11)
    ax.set_title('Euler Equation Verification', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_policy_experiment(baseline: ConsumptionSavingsModel,
                          counterfactual: ConsumptionSavingsModel,
                          experiment_name: str,
                          save_path: str = None) -> None:
    """
    Create a 2x2 comparison plot between baseline and counterfactual scenarios.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Policy Experiment: {experiment_name}',
                 fontsize=14, fontweight='bold')
    
    t = np.arange(baseline.params.T + 1)
    
    # Plot 1: Consumption Comparison
    ax = axes[0, 0]
    ax.plot(t, baseline.consumption, 'o-', linewidth=2, markersize=4, 
            color='steelblue', label='Baseline', alpha=0.8)
    ax.plot(t, counterfactual.consumption, 's-', linewidth=2, markersize=4,
            color='crimson', label='Counterfactual', alpha=0.8)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Consumption', fontsize=11)
    ax.set_title('Consumption Paths Comparison', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Capital Comparison
    ax = axes[0, 1]
    t_capital = np.arange(baseline.params.T + 2)
    ax.plot(t_capital, baseline.capital, 'o-', linewidth=2, markersize=4,
            color='darkgreen', label='Baseline', alpha=0.8)
    ax.plot(t_capital, counterfactual.capital, 's-', linewidth=2, markersize=4,
            color='darkred', label='Counterfactual', alpha=0.8)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Capital', fontsize=11)
    ax.set_title('Capital (Savings) Paths Comparison', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Consumption Difference
    ax = axes[1, 0]
    delta_c = counterfactual.consumption - baseline.consumption
    colors = ['red' if x < 0 else 'green' for x in delta_c]
    ax.bar(t, delta_c, color=colors, alpha=0.7)
    ax.axhline(0, color='black', linestyle='-', linewidth=0.8)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Change in Consumption (Δc_t)', fontsize=11)
    ax.set_title('Consumption Difference', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Plot 4: Welfare Comparison (Utility)
    ax = axes[1, 1]
    baseline_params = baseline.params
    baseline_utility = np.cumsum(baseline_params.beta**t * 
                                  baseline.consumption**(1 - baseline_params.sigma) / 
                                  (1 - baseline_params.sigma))
    counterfactual_utility = np.cumsum(baseline_params.beta**t * 
                                        counterfactual.consumption**(1 - baseline_params.sigma) / 
                                        (1 - baseline_params.sigma))
    
    ax.plot(t, baseline_utility, 'o-', linewidth=2, color='steelblue', label='Baseline', alpha=0.8)
    ax.plot(t, counterfactual_utility, 's-', linewidth=2, color='crimson', label='Counterfactual', alpha=0.8)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Cumulative Utility', fontsize=11)
    ax.set_title('Welfare Comparison (Cumulative Utility)', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


# ============================================================================
# 4. POLICY EXPERIMENTS
# ============================================================================

def experiment_interest_rate_change(baseline_params: ConsumptionSavingsParams,
                                   delta_R: float = 0.01) -> Tuple[ConsumptionSavingsModel,
                                                                     ConsumptionSavingsModel]:
    """
    Experiment 1: Interest Rate Change (Monetary Policy Effect)
    
    Shows how an increase in the real interest rate affects consumption and savings.
    Economic intuition: Higher R increases both substitution and wealth effects.
    """
    # Baseline
    baseline = ConsumptionSavingsModel(baseline_params)
    baseline.compute_optimal_consumption()
    
    # Counterfactual: Higher interest rate
    cf_params = ConsumptionSavingsParams(
        T=baseline_params.T,
        sigma=baseline_params.sigma,
        beta=baseline_params.beta,
        R=baseline_params.R + delta_R,  # Increase rate
        k0=baseline_params.k0,
        w0=baseline_params.w0,
        g_w=baseline_params.g_w
    )
    counterfactual = ConsumptionSavingsModel(cf_params)
    counterfactual.compute_optimal_consumption()
    
    return baseline, counterfactual


def experiment_patience_increase(baseline_params: ConsumptionSavingsParams,
                                delta_beta: float = 0.01) -> Tuple[ConsumptionSavingsModel,
                                                                    ConsumptionSavingsModel]:
    """
    Experiment 2: Patience Increase (β increase)
    
    Shows how an increase in patience (lower discount rate) affects savings behavior.
    Higher β means less impatience, leading to more saving and lower current consumption.
    """
    # Baseline
    baseline = ConsumptionSavingsModel(baseline_params)
    baseline.compute_optimal_consumption()
    
    # Counterfactual: More patient
    cf_params = ConsumptionSavingsParams(
        T=baseline_params.T,
        sigma=baseline_params.sigma,
        beta=min(baseline_params.beta + delta_beta, 0.99),  # Increase patience, max at 0.99
        R=baseline_params.R,
        k0=baseline_params.k0,
        w0=baseline_params.w0,
        g_w=baseline_params.g_w
    )
    counterfactual = ConsumptionSavingsModel(cf_params)
    counterfactual.compute_optimal_consumption()
    
    return baseline, counterfactual


def experiment_income_shock(baseline_params: ConsumptionSavingsParams,
                           shock_magnitude: float = -0.20,
                           shock_duration: int = 10) -> Tuple[ConsumptionSavingsModel,
                                                               ConsumptionSavingsModel]:
    """
    Experiment 3: Negative Income Shock (Recession Scenario)
    
    Shows how an unexpected income loss (recession) affects consumption and savings.
    Households typically smooth consumption by reducing savings to maintain living standards.
    """
    # Baseline
    baseline = ConsumptionSavingsModel(baseline_params)
    baseline.compute_optimal_consumption()
    
    # Counterfactual: Shock to income in first shock_duration periods
    cf_params = ConsumptionSavingsParams(
        T=baseline_params.T,
        sigma=baseline_params.sigma,
        beta=baseline_params.beta,
        R=baseline_params.R,
        k0=baseline_params.k0,
        w0=baseline_params.w0,
        g_w=baseline_params.g_w
    )
    counterfactual = ConsumptionSavingsModel(cf_params)
    
    # Override income path with shock
    counterfactual.compute_income_path()
    for t in range(min(shock_duration, counterfactual.params.T + 1)):
        counterfactual.income_path[t] *= (1 + shock_magnitude)
    
    counterfactual.compute_optimal_consumption()
    
    return baseline, counterfactual


def experiment_ies_comparative_statics(baseline_params: ConsumptionSavingsParams) -> Dict:
    """
    Experiment 4: IES Comparative Statics (σ Variations)
    
    Shows how the Intertemporal Elasticity of Substitution (IES = 1/σ) affects
    consumption growth and savings. Higher σ means lower IES, less responsiveness
    to interest rates.
    """
    sigma_values = [0.5, 1.0, 2.0, 3.0]  # IES = 2.0, 1.0, 0.5, 0.33
    results = {}
    
    for sigma in sigma_values:
        params = ConsumptionSavingsParams(
            T=baseline_params.T,
            sigma=sigma,
            beta=baseline_params.beta,
            R=baseline_params.R,
            k0=baseline_params.k0,
            w0=baseline_params.w0,
            g_w=baseline_params.g_w
        )
        model = ConsumptionSavingsModel(params)
        model.compute_optimal_consumption()
        results[sigma] = model
    
    return results


# ============================================================================
# 5. COMPREHENSIVE ANALYSIS & REPORTING
# ============================================================================

def print_economic_interpretation(experiment_name: str,
                                 baseline_summary: Dict,
                                 cf_summary: Dict,
                                 params_change: Dict) -> None:
    """Print economic interpretation of policy experiment results."""
    print("\n" + "="*70)
    print(f"EXPERIMENT: {experiment_name}")
    print("="*70)
    
    print("\nPARameter Change:")
    for key, value in params_change.items():
        print(f"  • {key}: {value}")
    
    print("\nEconomic Effects:")
    c0_change = ((cf_summary['initial_consumption'] - baseline_summary['initial_consumption']) / 
                 baseline_summary['initial_consumption'] * 100)
    savings_change = cf_summary['avg_savings_rate'] - baseline_summary['avg_savings_rate']
    wealth_change = ((cf_summary['lifetime_wealth'] - baseline_summary['lifetime_wealth']) / 
                     baseline_summary['lifetime_wealth'] * 100)
    
    print(f"  • Change in initial consumption (c₀): {c0_change:+.2f}%")
    print(f"  • Change in average savings rate: {savings_change:+.2f} percentage points")
    print(f"  • Lifetime wealth impact: {wealth_change:+.2f}%")
    
    print("\nInterpretation & Policy Implications:")


def generate_comprehensive_report(baseline_params: ConsumptionSavingsParams,
                                 save_figures: bool = False) -> None:
    """Generate a comprehensive simulation report with all experiments."""
    
    print("\n" + "="*70)
    print("MACRO-ECONOMIC SIMULATION: CONSUMPTION-SAVINGS OPTIMIZATION")
    print("="*70)
    
    # ==================== BASELINE SCENARIO ====================
    print("\n[SECTION 1] BASELINE SCENARIO")
    print("-" * 70)
    
    baseline = ConsumptionSavingsModel(baseline_params)
    baseline.compute_optimal_consumption()
    baseline.verify_solution(verbose=True)
    
    baseline_summary = baseline.get_summary()
    print("\nBaseline Summary Statistics:")
    print(f"  • Lifetime Wealth (W₀): {baseline_summary['lifetime_wealth']:.4f}")
    print(f"  • Initial Consumption (c₀): {baseline_summary['initial_consumption']:.4f}")
    print(f"  • Average Consumption: {baseline_summary['avg_consumption']:.4f}")
    print(f"  • Terminal Consumption (c_T): {baseline_summary['terminal_consumption']:.4f}")
    print(f"  • Consumption Growth Rate: {baseline_summary['consumption_growth_rate']*100:.2f}% p.a.")
    print(f"  • Average Savings Rate: {baseline_summary['avg_savings_rate']*100:.2f}%")
    print(f"  • Peak Capital Holdings: {baseline_summary['max_capital']:.4f}")
    
    plot_baseline_dynamics(baseline, 
                          save_path="baseline_dynamics.png" if save_figures else None)
    
    # ==================== EXPERIMENT 1: Interest Rate ====================
    print("\n[SECTION 2] EXPERIMENT 1: INTEREST RATE CHANGE (Monetary Policy)")
    print("-" * 70)
    
    base_exp1, cf_exp1 = experiment_interest_rate_change(baseline_params, delta_R=0.01)
    cf_exp1_summary = cf_exp1.get_summary()
    print_economic_interpretation(
        "Interest Rate Increase (+1%)",
        baseline_summary,
        cf_exp1_summary,
        {'Gross Return': f'{baseline_params.R:.3f} → {cf_exp1.params.R:.3f}'}
    )
    print(f"  • A higher real interest rate increases the return to saving.")
    print(f"  • Substitution effect: Incentivizes more saving (future consumption cheaper).")
    print(f"  • Wealth effect: Makes household feel richer, could increase current consumption.")
    print(f"  • Net effect depends on parameter values and elasticity of substitution (IES).")
    print(f"  • With σ={baseline_params.sigma}, consumption growth increases.")
    
    plot_policy_experiment(base_exp1, cf_exp1, "Interest Rate Change",
                          save_path="exp1_interest_rate.png" if save_figures else None)
    
    # ==================== EXPERIMENT 2: Patience ====================
    print("\n[SECTION 3] EXPERIMENT 2: PATIENCE INCREASE (β increase)")
    print("-" * 70)
    
    base_exp2, cf_exp2 = experiment_patience_increase(baseline_params, delta_beta=0.02)
    cf_exp2_summary = cf_exp2.get_summary()
    print_economic_interpretation(
        "Increase in Patience (β increase)",
        baseline_summary,
        cf_exp2_summary,
        {'Discount Factor': f'{baseline_params.beta:.4f} → {cf_exp2.params.beta:.4f}'}
    )
    print(f"  • More patient consumers (higher β) have lower discount rates.")
    print(f"  • They value future consumption more relative to present consumption.")
    print(f"  • Result: Lower current consumption, higher savings, faster wealth accumulation.")
    print(f"  • This explains heterogeneity in saving behavior across households.")
    print(f"  • Policy implication: Financial education (patience) drives wealth inequality.")
    
    plot_policy_experiment(base_exp2, cf_exp2, "Patience Increase",
                          save_path="exp2_patience.png" if save_figures else None)
    
    # ==================== EXPERIMENT 3: Income Shock ====================
    print("\n[SECTION 4] EXPERIMENT 3: NEGATIVE INCOME SHOCK (Recession)")
    print("-" * 70)
    
    base_exp3, cf_exp3 = experiment_income_shock(baseline_params, 
                                                shock_magnitude=-0.20, 
                                                shock_duration=10)
    cf_exp3_summary = cf_exp3.get_summary()
    print_economic_interpretation(
        "Negative Income Shock (recession, -20% for 10 years)",
        baseline_summary,
        cf_exp3_summary,
        {'Shock': '−20% of labor income, first 10 periods'}
    )
    print(f"  • Unexpected income loss forces households to adjust their consumption paths.")
    print(f"  • Consumption smoothing: Households use savings to maintain consumption.")
    print(f"  • Mechanism: Lifetime wealth declines, so consumption must be lower overall.")
    print(f"  • Short-term: Dissaving (capital depletion) to partially stabilize consumption.")
    print(f"  • Long-term: Households adjust to permanently lower consumption due to lower W₀.")
    print(f"  • Policy: Unemployment insurance can help smooth consumption during shocks.")
    
    plot_policy_experiment(base_exp3, cf_exp3, "Negative Income Shock",
                          save_path="exp3_income_shock.png" if save_figures else None)
    
    # ==================== EXPERIMENT 4: IES ====================
    print("\n[SECTION 5] EXPERIMENT 4: IES COMPARATIVE STATICS (σ variations)")
    print("-" * 70)
    
    ies_results = experiment_ies_comparative_statics(baseline_params)
    
    print("IES Elasticity parameter cross-variation (σ = 0.5, 1.0, 2.0, 3.0):")
    print(f"  • IES = 1/σ, so higher σ means LOWER substitutability across time")
    print(f"  • Households vary in their willingness to shift consumption over time\n")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('IES Comparative Statics: Effect of σ on Optimal Paths',
                 fontsize=14, fontweight='bold')
    
    t = np.arange(baseline_params.T + 1)
    colors = ['steelblue', 'darkgreen', 'crimson', 'purple']
    
    # Plot 1: Consumption paths
    ax = axes[0, 0]
    for (sigma, model), color in zip(ies_results.items(), colors):
        ax.plot(t, model.consumption, 'o-', alpha=0.7, color=color, 
               label=f'σ={sigma} (IES={1/sigma:.2f})', markersize=3)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Consumption', fontsize=11)
    ax.set_title('Consumption Paths for Different σ', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Consumption growth rates
    ax = axes[0, 1]
    for (sigma, model), color in zip(ies_results.items(), colors):
        c_growth = (model.params.beta * model.params.R) ** (1.0 / sigma) - 1
        ax.scatter(sigma, c_growth * 100, s=200, color=color, alpha=0.7, 
                  label=f'σ={sigma}', edgecolors='black', linewidth=2)
    ax.set_xlabel('IES Parameter (σ)', fontsize=11)
    ax.set_ylabel('Consumption Growth Rate (%)', fontsize=11)
    ax.set_title('Effect of σ on Consumption Growth', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Plot 3: Capital paths
    ax = axes[1, 0]
    t_cap = np.arange(baseline_params.T + 2)
    for (sigma, model), color in zip(ies_results.items(), colors):
        ax.plot(t_cap, model.capital, 'o-', alpha=0.7, color=color,
               label=f'σ={sigma}', markersize=3)
    ax.set_xlabel('Year (t)', fontsize=11)
    ax.set_ylabel('Capital', fontsize=11)
    ax.set_title('Savings Paths for Different σ', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Summary metrics
    ax = axes[1, 1]
    sigma_list = list(ies_results.keys())
    savings_rates = [ies_results[s].get_summary()['avg_savings_rate'] * 100 
                     for s in sigma_list]
    c_growth_rates = [((ies_results[s].params.beta * ies_results[s].params.R) ** 
                      (1.0 / s) - 1) * 100 for s in sigma_list]
    
    ax_twin = ax.twinx()
    bars = ax.bar([str(s) for s in sigma_list], savings_rates, alpha=0.7, color='steelblue', label='Savings Rate')
    line = ax_twin.plot([str(s) for s in sigma_list], c_growth_rates, 'ro-', linewidth=2, 
                       markersize=8, label='Consumption Growth')
    
    ax.set_xlabel('IES Parameter (σ)', fontsize=11)
    ax.set_ylabel('Average Savings Rate (%)', fontsize=11, color='steelblue')
    ax_twin.set_ylabel('Consumption Growth (%)', fontsize=11, color='red')
    ax.set_title('Savings Rate & Growth by σ', fontsize=12, fontweight='bold')
    ax.tick_params(axis='y', labelcolor='steelblue')
    ax_twin.tick_params(axis='y', labelcolor='red')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    if save_figures:
        plt.savefig("exp4_ies_statics.png", dpi=300, bbox_inches='tight')
    plt.show()
    
    print("\nHeterogeneity Insights:")
    for sigma in sigma_list:
        model = ies_results[sigma]
        summary = model.get_summary()
        growth_rate = (model.params.beta * model.params.R) ** (1.0 / sigma) - 1
        print(f"  σ={sigma} (IES={1/sigma:.2f}): c₀={summary['initial_consumption']:.4f}, "
              f"growth={growth_rate*100:.2f}%, savings={summary['avg_savings_rate']*100:.2f}%")
    
    # ==================== FINAL SUMMARY ====================
    print("\n" + "="*70)
    print("ECONOMIC INSIGHTS & POLICY TAKEAWAYS")
    print("="*70)
    
    print("""
1. CONSUMPTION SMOOTHING (Core Principle)
   • Rational consumers spread resources across time, preferring stable consumption
   • Higher utility from smooth paths (diminishing marginal utility)
   • Shocks → temporary dissaving → adjust to new equilibrium

2. INTEREST RATE EFFECTS (Monetary Policy)
   • Higher rates → faster consumption growth but ambiguous level effect
   • Substitution effect (future cons. cheaper) vs. Wealth effect (feel richer)
   • With σ=2, substitution effect dominates, consumption still relatively smooth

3. PATIENCE & WEALTH INEQUALITY
   • Patient households (high β) save more → accumulate more wealth
   • This mechanism explains persistent inequality across households
   • Financial literacy education could increase β, boost aggregate saving

4. INCOME SHOCKS & PRECAUTIONARY SAVING
   • Recession forces immediate downward adjustment in lifetime consumption
   • Households partially buffer shocks using accumulated savings
   • Policy: Unemployment insurance provides additional smoothing

5. INTERTEMPORAL ELASTICITY OF SUBSTITUTION
   • σ=2 (IES=0.5) is empirically standard for macro models
   • Higher σ → lower IES → less time substitution → flatter consumption
   • Core parameter determining consumer behavior to interest rate shocks
   
6. POLICY IMPLICATIONS
   • Monetary policy (interest rate ↑) has persistent effects on saving behavior
   • Redistribution affects aggregate precautionary saving
   • Business cycle shocks require automatic stabilizers (UI, safety nets)
   • Consumer financial literacy is long-term wealth determinant
    """)
    
    print("\n" + "="*70)
    print("SIMULATION COMPLETE")
    print("="*70 + "\n")


# ============================================================================
# 6. MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Create baseline parameters (from lecture calibration)
    baseline_params = ConsumptionSavingsParams(
        T=40,           # 40-year working life
        sigma=2.0,      # Standard macro calibration
        beta=0.96,      # 4% annual discount rate
        R=1.04,         # 4% real interest rate
        k0=1.0,         # Normalized initial capital
        w0=0.50,        # Normalized initial labor income
        g_w=0.02        # 2% real wage growth
    )
    
    # Generate comprehensive report with all experiments and visualizations
    generate_comprehensive_report(baseline_params, save_figures=False)
    
    print("\n[OK] Simulation complete! Check plots for detailed visualizations.\n")
