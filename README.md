# Systematic Quant Trading

> A structured learning path and research workspace for quantitative finance, systematic trading, and quantitative development.

This repository brings together market knowledge, mathematical foundations, research methods, trading-system implementation, interactive visualisations, and hands-on projects. It is designed to make the full journey visible: understand the market, formulate a hypothesis, build a signal, construct a portfolio, test it honestly, and account for execution and risk.

The material is actively evolving. Some areas are polished reference material, while others are working notes, experiments, notebooks, and research in progress.

## Contents

- [Repository at a Glance](#repository-at-a-glance)
- [Suggested Learning Path](#suggested-learning-path)
- [Repository Map](#repository-map)
- [Getting Started](#getting-started)
- [Research Workflow](#research-workflow)
- [Technology](#technology)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)

## Repository at a Glance

| Area | What you will find |
| --- | --- |
| Foundations | Financial markets, mathematics, probability, statistics, Python, and data handling |
| Core quant finance | Returns, portfolio mechanics, risk, regression, time series, derivatives, volatility, macroeconomics, and optimisation |
| Quantitative research | Alpha research, factor models, statistical arbitrage, portfolio construction, backtesting, validation, machine learning, and execution |
| Quantitative development | Software engineering, data engineering, APIs, databases, testing, research infrastructure, and performance engineering |
| Advanced trading | Systematic trading, market making, high-frequency trading, execution, volatility, crypto, FX, options, futures, and cross-asset research |
| Advanced models | Stochastic processes and calculus, Monte Carlo, state-space and hidden Markov models, Kalman filters, extreme value theory, copulas, and advanced machine learning |
| Projects | Beginner through expert projects using notebooks, datasets, reports, and backtesting workflows |
| Visualisations | Browser-based simulators for pricing, risk, portfolios, market microstructure, execution, and backtesting |
| Research and reference | Papers, research notes, literature reviews, cheat sheets, formulas, glossaries, handbooks, and interview preparation |

## Suggested Learning Path

The numbered folders form a progression, but they can also be used as independent reference areas.

1. Start with [Foundations](01_Foundations/README.md) to build market, mathematical, statistical, Python, and data fluency.
2. Study [Core Quant Finance](02_Core_Quant_Finance/README.md) to connect those foundations to portfolio mathematics, risk, derivatives, volatility, and time series.
3. Move into [Quantitative Research](03_Quantitative_Research/README.md) and follow the research lifecycle from alpha discovery through validation and execution.
4. Use [Quantitative Development](04_Quantitative_Development/README.md) to make research code testable, reproducible, observable, and efficient.
5. Explore [Advanced Trading](05_Advanced_Trading/README.md) and [Advanced Models](06_Advanced_Models/README.md) once the core workflow is familiar.
6. Consolidate the material through [Projects](07_Projects/README.md), beginning with the beginner track and progressing by difficulty.
7. Build intuition with [Interactive Visualisations](08_Interactive_Visualisations/README.md), then use [Research](09_Research/README.md), [Interview Preparation](10_Interview_Preparation/README.md), and [Reference](11_Reference/README.md) for deeper study and quick lookup.

## Repository Map

### Foundations and Core Finance

- [01 Foundations](01_Foundations/README.md): financial markets and instruments, market mechanics, mathematics, probability and statistics, Python, programming, macro context, and data handling.
- [02 Core Quant Finance](02_Core_Quant_Finance/README.md): returns, portfolio mechanics, risk, regression, time series, derivatives, volatility, macroeconomics, optimisation, and model risk.

### Research and Implementation

- [03 Quantitative Research](03_Quantitative_Research/README.md): signal and factor research, statistical arbitrage, portfolio construction, backtesting, validation, machine learning, execution, and research data.
- [04 Quantitative Development](04_Quantitative_Development/README.md): engineering practices that support reliable research and production-oriented trading systems.

### Trading and Models

- [05 Advanced Trading](05_Advanced_Trading/README.md): systematic strategies, market making, high-frequency trading, execution, volatility trading, crypto, FX, options and futures, and cross-asset approaches.
- [06 Advanced Models](06_Advanced_Models/README.md): stochastic modelling, simulation, regime and state-space models, tail-risk methods, dependence modelling, and machine learning.

### Applied Work and Study Tools

- [07 Projects](07_Projects/README.md): end-to-end projects organised into beginner, intermediate, advanced, and expert tracks. The beginner track includes momentum, pairs trading, portfolio optimisation, event-based strategies, risk surfaces, and OHLCV validation.
- [08 Interactive Visualisations](08_Interactive_Visualisations/README.md): self-contained HTML tools covering Black-Scholes and binomial pricing, Greeks, implied volatility, portfolio diversification, factor exposure, stochastic processes, regime switching, order books, market impact, margin, and execution.
- [09 Research](09_Research/README.md): papers, research notes, and literature reviews.
- [10 Interview Preparation](10_Interview_Preparation/README.md): preparation for quantitative research, development, trading, probability, mental maths, market microstructure, and resume discussions.
- [11 Reference](11_Reference/README.md): cheat sheets, formula sheets, glossaries, and handbooks for quick lookup.

## Getting Started

### Clone the repository

```bash
git clone <repository-url>
cd Systematic-Quant-Trading
```

### Conda environment

The checked-in Conda file is the most complete environment specification:

```bash
conda env create -f environment.yml
conda activate systematic_quant_finance
```

### Python virtual environment

For a lighter pip-based setup:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The project targets Python 3.10 or newer. JupyterLab is included in the dependency set for notebook-based work.

### Open the interactive tools

The files in [08 Interactive Visualisations](08_Interactive_Visualisations/README.md) are standalone HTML applications. Open an HTML file directly in a modern browser, or serve the repository locally if your browser blocks local assets:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000/08_Interactive_Visualisations/`.

## Research Workflow

The repository is organised around a repeatable research loop:

1. **Understand the market:** define the instrument, participants, mechanics, liquidity, and risks.
2. **State a hypothesis:** describe the economic or behavioural rationale before looking for a favourable result.
3. **Prepare data:** document sources, frequency, timestamps, survivorship assumptions, corporate actions, and missing data.
4. **Build the signal:** keep feature generation, signal logic, portfolio construction, and execution assumptions distinct.
5. **Backtest honestly:** include transaction costs, slippage, turnover, position limits, and realistic information timing.
6. **Validate robustness:** use out-of-sample tests, walk-forward analysis, sensitivity checks, and stress scenarios.
7. **Review risk and implementation:** evaluate drawdowns, concentration, liquidity, model risk, and operational failure modes.
8. **Document the result:** record assumptions, limitations, metrics, and what would invalidate the idea.

Performance numbers without this context are not sufficient evidence of a tradable strategy.

## Technology

The main stack is Python and the scientific Python ecosystem:

- **Research and data:** NumPy, pandas, SciPy, pandas-datareader-compatible workflows, PyArrow, and yfinance
- **Statistics and modelling:** statsmodels, scikit-learn, XGBoost, LightGBM, ARCH, and CVXPY
- **Visualisation:** matplotlib, seaborn, and Plotly
- **Backtesting:** backtesting.py and vectorbt
- **Development:** JupyterLab, pytest, Black, Ruff, and pre-commit

See [requirements.txt](requirements.txt), [environment.yml](environment.yml), and [pyproject.toml](pyproject.toml) for the maintained dependency and tooling configuration.

## Contributing

Contributions that improve accuracy, clarity, reproducibility, navigation, or practical usefulness are welcome. Useful additions include new notebooks, worked examples, visualisations, references, tests, interview material, and corrections to existing content.

Before contributing, read [CONTRIBUTING.md](CONTRIBUTING.md). Please keep research assumptions explicit, avoid committing secrets or unnecessarily large generated files, and include documentation for new datasets or experiments.

## Disclaimer

All content is provided for educational and research purposes only. Nothing in this repository constitutes financial advice, an investment recommendation, or an offer to buy or sell any financial instrument. Backtested or simulated results are hypothetical and do not guarantee future performance.

_This is a living body of work. Concepts, experiments, and implementations will continue to evolve._
