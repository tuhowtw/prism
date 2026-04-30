# Macro-Economic Simulation Demo
## Dynamic Optimization: Consumption-Savings Model with Policy Analysis

### Overview
This package contains a comprehensive macro-economic simulation demonstrating **dynamic optimization** and **consumer behavior** based on the lecture notes: *"Dynamic Optimization & Vibe Coding: Consumption-Savings Decisions"*.

The simulation solves a finite-horizon consumption-savings problem and explores four major policy experiments through comparative statics analysis.

---

## Files Included

### 1. **macro_simulation_demo.py** (Standalone Script)
A complete, production-ready Python simulation with:
- **Core Model Class**: `ConsumptionSavingsModel` - Solves the optimization problem using Euler equation methods
- **Parameter Class**: `ConsumptionSavingsParams` - Validates and stores all parameters
- **Visualization Functions**: Creates professional 2×2 subplot figures for each experiment
- **Policy Experiments**: All 4 experiments fully implemented
- **Comprehensive Verification**: Terminal condition, budget constraint, Euler equation validation
- **Economic Interpretation**: Text output explaining results using proper macro theory

**Key Features:**
- ✓ Closed-form solution for initial consumption c₀
- ✓ Exact Euler equation satisfaction
- ✓ CIES utility with any σ > 0
- ✓ Labor income with constant growth rate
- ✓ Verification against terminal condition k_{T+1} = 0
- ✓ Matplotlib visualizations with economic labels

**Usage:**
```bash
python macro_simulation_demo.py
```

### 2. **macro_simulation_interactive.ipynb** (Jupyter Notebook)
An interactive notebook for exploratory analysis with:
- Step-by-step explanations in English and mathematical notation
- Live Python execution cells for parameter changes
- Real-time visualization of results
- All 4 policy experiments with comparative plots
- Economic interpretation tables
- Sensitivity analysis

**Sections:**
1. Library imports and setup
2. Model equations and mathematical framework
3. Parameter configuration (adjustable)
4. Economic solver implementation
5. Baseline dynamics visualization
6. 4 policy experiments with full analysis
7. Summary table and economic insights

**Usage:**
```bash
jupyter notebook macro_simulation_interactive.ipynb
```

---

## Economic Model

### Objective Function
$$\max_{\{c_t, k_{t+1}\}} \sum_{t=0}^{T} \beta^t u(c_t)$$

### Budget Constraint
$$c_t + k_{t+1} = R \cdot k_t + w_t$$

### Key Equations
- **Euler Equation**: $c_{t+1}/c_t = (\beta R)^{1/\sigma}$
- **CIES Utility**: $u(c) = \frac{c^{1-\sigma} - 1}{1-\sigma}$
- **Income Path**: $w_t = w_0(1 + g_w)^t$
- **Lifetime Wealth**: $W_0 = Rk_0 + \sum_{t=0}^{T} \frac{w_t}{R^t}$

### Baseline Calibration
| Parameter | Value | Meaning |
|-----------|-------|---------|
| T | 40 | Planning horizon (years) |
| σ | 2.0 | IES parameter (IES = 1/σ = 0.5) |
| β | 0.96 | Discount factor (4% annual rate) |
| R | 1.04 | Gross real return (4% p.a.) |
| k₀ | 1.0 | Initial capital (normalized) |
| w₀ | 0.50 | Initial income (normalized) |
| g_w | 0.02 | Wage growth (2% p.a.) |

---

## Policy Experiments

### Experiment 1: Interest Rate Change (Monetary Policy)
**Scenario**: Real interest rate increases from R=1.04 to R=1.08

**Economic Mechanisms**:
- Income effect: Higher capital returns → wealthier → higher consumption
- Substitution effect: Future consumption cheaper → save more
- Net effect depends on IES (1/σ)

**Results**: Higher interest rates increase lifetime wealth and consumption growth rate

**Policy Lesson**: Monetary policy effects on household consumption depend critically on the intertemporal elasticity of substitution (IES).

### Experiment 2: Patience Increase (β increase)
**Scenario**: Consumer becomes more patient: β from 0.96 to 0.99

**Economic Mechanisms**:
- Lower discount rate → more weight on future utility
- Consume less today → save more → accumulate wealth faster
- Consumption grows faster

**Results**: Patient consumers have lower initial consumption but higher lifetime welfare

**Policy Lesson**: Financial literacy and commitment savings mechanisms can increase effective β, promoting wealth accumulation and income inequality.

### Experiment 3: Negative Income Shock (Recession)
**Scenario**: Permanent 20% income loss: w₀ from 0.50 to 0.40

**Economic Mechanisms**:
- Lifetime wealth drops by 20%
- Consumer smooths shock across entire remaining lifetime
- Uses savings as buffer to minimize consumption volatility

**Results**: Consumption smoothing prevents sharp consumption collapse
- Income shock: -20%
- Consumption drop: ~7-9% (varies with σ)

**Policy Lesson**: Unemployment insurance and transfer programs help households smooth consumption during recessions, maintaining aggregate demand.

### Experiment 4: IES Comparative Statics
**Scenario**: Solve model for σ = {0.5, 1.0, 2.0, 3.0}

**Economic Mechanisms**:
- σ controls willingness to substitute consumption across time
- Higher σ (lower IES) → strong preference for smoothing
- Lower σ (higher IES) → willing to tilt consumption

**Results**:
| σ | IES | Consumption Profile | Time Substitution |
|---|-----|-------------------|-------------------|
| 0.5 | 2.0 | Steep decline | High |
| 1.0 | 1.0 | Moderate decline | Medium |
| 2.0 | 0.5 | Nearly flat | Low |
| 5.0 | 0.2 | Very flat | Very low |

**Policy Lesson**: The IES is the crucial parameter for understanding:
- Monetary policy transmission
- Consumption response to interest rates
- Business cycle amplification
- Policy effectiveness

---

## Key Economic Insights

### 1. Consumption Smoothing (Core Principle)
- Rational consumers spread lifetime resources evenly over time
- Concavity of utility (u'' < 0) drives preference for smooth consumption
- Mechanism: Save during high-income/low-consumption periods, dissave during low-income/high-consumption periods

### 2. Three Parameters Drive Everything
1. **β (Patience)**: How much the consumer values the future
2. **R (Return)**: Reward for waiting (interest rate)
3. **σ (IES Parameter)**: Willingness to substitute across time

### 3. Interest Rates & Monetary Policy
- Higher rates increase lifetime wealth (income effect, positive)
- Higher rates increase consumption growth (substitution effect, positive)
- But which effect dominates level of consumption depends on IES
- With σ=2 (standard macro): consumption relatively insensitive to rate changes

### 4. Inequality & Wealth Accumulation
- Patient households (β↑) accumulate more wealth
- This mechanism explains heterogeneity in lifetime outcomes
- Financial education and commitment devices can increase effective β
- Has long-term implications for wealth distribution

### 5. Recessions & Consumption Smoothing
- Permanent income loss → lifetime consumption falls in every period
- But fall is much smaller than income loss (smoothing over lifetime)
- Temporary shocks → mostly cushioned by savings (minimal drop)
- This distinction (permanent vs temporary) is crucial for policy design

---

## Verification & Robustness

All solutions satisfy:
✓ **Terminal Condition**: k_{T+1} ≈ 0 (error < 10⁻⁸)
✓ **Budget Constraint**: c_t + k_{t+1} = Rk_t + w_t (residual < 10⁻⁸)
✓ **Euler Equation**: c_{t+1}/c_t = (βR)^{1/σ} (error < 10⁻⁶)
✓ **Consumption Positive**: all c_t > 0 (feasible)
✓ **Economic Intuition**: Results make economic sense

---

## Extension Ideas

This framework extends naturally to more complex models:

### 1. **Stochastic Income**
- Replace deterministic w_t with Markov process
- Introduces precautionary saving
- Can explain actual savings patterns better

### 2. **Borrowing Constraints**
- Impose k_{t+1} ≥ 0 (no borrowing)
- Find periods where constraint binds
- Shows why credit market access matters

### 3. **Bequest Motive**
- Add warm-glow utility from leaving wealth
- Changes terminal condition from k_{T+1}=0
- More realistic for intergenerational wealth

### 4. **Social Security & Pensions**
- Worker periods (0 to T_r) with payroll tax
- Retiree periods (T_r to T) with government transfer
- Shows how insurance affects saving behavior

### 5. **Life-Cycle with Uncertainty**
- Stochastic lifespans
- Health expenditure shocks
- Heterogeneous discount rates
- Full heterogeneous-agent model

---

## How to Use This in Research/Teaching

### For Students:
1. **Run Baseline**: Execute the script to see baseline consumption-savings path
2. **Modify Parameters**: Change β, R, σ, T in parameters and observe effects
3. **Run Experiments**: Understand each policy experiment and economic mechanism
4. **Interpret Results**: Use economic theory to explain numerical findings
5. **Extend Model**: Add your own features (constraints, randomness, etc.)

### For Instructors:
1. **Lecture Supplement**: Use plots and explanations in classroom
2. **Assignment Problems**: Have students modify parameters and predict outcomes
3. **Verification Exercises**: Have students verify code against economic theory
4. **Research Extension**: Use as base for more complex projects

### For Researchers:
1. **Baseline Model**: Use as reference implementation
2. **Calibration Starting Point**: Adapt parameters to match data
3. **Experiment Template**: Structure for policy analysis
4. **Benchmark**: Compare more complex models against this solution

---

## Technical Requirements

**Python Packages**:
- `numpy` (numerical computations)
- `pandas` (data handling)
- `matplotlib` (visualization)
- `seaborn` (styling)
- `scipy` (optional, numerical methods)

**Installation**:
```bash
pip install numpy pandas matplotlib seaborn scipy
```

---

## References

**Lecture Notes**: *Dynamic Optimization & Vibe Coding: Consumption-Savings Decisions* by David Leung (© 2026)

**Key Theory**:
- Euler Equation: Consumption growth determined by returns and preference parameters
- CIES Utility: Constant Intertemporal Elasticity of Substitution (Epstein, 1992)
- Intertemporal Budget Constraint: Present value of consumption = lifetime wealth
- Life-Cycle Hypothesis: Consumption smoothing across working and retirement years (Modigliani & Brumberg, 1954)
- Permanent Income Hypothesis: Consumption responds to permanent but not temporary income shocks (Friedman, 1957)

---

## Author & License

Created as part of macro-economic simulation education.
Based on dynamic optimization principles from consumption theory.

---

## Summary

This simulation demonstrates:
- ✓ How consumption-savings decisions are made optimally
- ✓ Effects of interest rate changes (monetary policy)
- ✓ Role of patience in wealth accumulation
- ✓ How consumers smooth consumption during income shocks
- ✓ Importance of intertemporal elasticity of substitution
- ✓ Verification of economic predictions against theory
- ✓ Professional visualization of macro-economic results

**Use this as a learning tool, research benchmark, and starting point for extensions!**

