# SF-AgentBench

**A Specialized Benchmarking Framework for Evaluating AI Agents on Salesforce Development**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Overview

SF-AgentBench is a rigorous benchmarking framework designed to evaluate AI agents—such as Claude Code, Codex, or Gemini Orchestrator—on their ability to design and build Salesforce solutions. While existing benchmarks like SWE-bench effectively assess code generation in file-based languages (Python, Java), they fail to capture the architectural complexity of Platform-as-a-Service (PaaS) environments like Salesforce.

Salesforce development is a hybrid practice requiring:
- **Declarative metadata** orchestration
- **Proprietary programming languages** (Apex, SOQL, LWC)
- **Stateful database interactions** within a multi-tenant environment
- **Strict execution limits** (Governor Limits)

SF-AgentBench addresses these unique challenges with a purpose-built evaluation framework.

## Key Features

### 🎯 Curriculum-Aligned Evaluation
Grounded in official Salesforce certifications:
- **Administrator (ADM-201)** — Schema, automation, security
- **Platform Developer I & II (PD1/PD2)** — Apex, integrations, LWC

### 🏆 Superbadge Methodology
Uses complex, scenario-based problem solving as the gold standard—moving beyond atomic code generation to holistic solution architecture.

### 🔧 Agent-Computer Interface (ACI)
A novel interface wrapping the Salesforce CLI (`sf`) that enables agents to:
- Operate securely within ephemeral Scratch Orgs
- Deploy metadata and execute tests
- Query data and run static analysis

### 📊 Multi-Layered Evaluation
Five distinct evaluation layers ensure comprehensive assessment:

| Layer | Metric | Description |
|-------|--------|-------------|
| **1** | Deployment Validation | Can the solution deploy without errors? |
| **2** | Functional Testing | Do Apex tests pass? What's the coverage? |
| **3** | Static Analysis (PMD) | Code quality, security, and performance checks |
| **4** | Metadata Diffing | Semantic comparison against golden configurations |
| **5** | LLM-as-a-Judge Rubric | Design patterns, bulkification, best practices |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SF-AgentBench Harness                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Task      │  │   Agent     │  │      Evaluation         │  │
│  │   Loader    │  │   Runner    │  │      Pipeline           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    Agent-Computer Interface (ACI)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │sf_deploy │ │sf_query  │ │sf_test   │ │sf_scan_code      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                     Salesforce CLI (sf)                         │
├─────────────────────────────────────────────────────────────────┤
│                   Ephemeral Scratch Org Pool                    │
└─────────────────────────────────────────────────────────────────┘
```

## Task Difficulty Tiers

| Tier | Complexity | Example | Skills Tested |
|------|------------|---------|---------------|
| **Tier 1** | Single-domain, declarative | Validation Rule + Flow for lead scoring | Schema, Validation Rules, Flows |
| **Tier 2** | Multi-domain, declarative + simple code | Screen Flow calling Apex action | Screen Flow, Invocable Apex, Testing |
| **Tier 3** | Complex code, async processing | Apex Specialist Superbadge | Triggers, Queueable, Bulkification |
| **Tier 4** | Full-stack, LWC, integrations | LWC Specialist Superbadge | LWC, Apex Services, Wire, Callouts |

## Project Structure

```
sf-agentbench/
├── README.md
├── docs/
│   └── development/
│       ├── Salesforce AI Benchmark Design.md
│       └── Salesforce AI Benchmark Design.pdf
├── harness/                    # Benchmark orchestration (planned)
│   ├── aci/                    # Agent-Computer Interface tools
│   ├── evaluators/             # Scoring and evaluation logic
│   └── runners/                # Task execution engine
├── tasks/                      # Benchmark tasks (planned)
│   ├── tier-1/
│   ├── tier-2/
│   ├── tier-3/
│   └── tier-4/
└── results/                    # Agent run outputs (planned)
```

## Getting Started

### Prerequisites

- **Salesforce CLI** (`sf`) — [Install Guide](https://developer.salesforce.com/tools/salesforcecli)
- **DevHub-enabled Org** — Required for Scratch Org creation
- **Node.js 18+** — For harness execution
- **Python 3.10+** — For evaluation scripts

### Installation

```bash
# Clone the repository
git clone https://github.com/bhanudas/sf-agentbench.git
cd sf-agentbench

# Install dependencies (coming soon)
npm install
```

### Running a Benchmark Task

```bash
# Coming soon
sf-agentbench run --task apex-specialist --agent claude-code
```

## Scoring Methodology

The composite score combines all evaluation layers:

```
Final_Score = (
    0.20 × deployment_success +
    0.40 × apex_test_pass_rate +
    0.10 × (1 - pmd_penalty) +
    0.15 × metadata_accuracy +
    0.15 × rubric_score
)
```

## Roadmap

### Phase 1: Foundation (Months 1-2)
- [ ] DevHub setup with Scratch Org pool management
- [ ] ACI tool wrappers for core `sf` commands
- [ ] Basic harness for task loading and evaluation
- [ ] 10 Tier 1 & 2 benchmark tasks

### Phase 2: Expansion (Months 3-4)
- [ ] PMD/Code Analyzer integration
- [ ] Metadata diffing for Flows and Profiles
- [ ] 10 Tier 3 tasks
- [ ] Baseline runs with leading AI agents

### Phase 3: Maturity (Months 5-6)
- [ ] LLM-as-a-Judge rubric evaluation
- [ ] 5 Tier 4 tasks
- [ ] Public leaderboard
- [ ] Research paper submission

## Documentation

- [Technical Design Document](docs/development/Salesforce%20AI%20Benchmark%20Design.md) — Comprehensive framework architecture and methodology

## Contributing

Contributions are welcome! Please read our contributing guidelines (coming soon) before submitting PRs.

### Areas for Contribution
- New benchmark tasks (especially Tier 3 & 4)
- ACI tool implementations
- Evaluation metric refinements
- Documentation improvements

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by [SWE-bench](https://www.swebench.com/) and [SWE-agent](https://swe-agent.com/)
- Task methodology adapted from [Salesforce Trailhead Superbadges](https://trailhead.salesforce.com/superbadges)
- Built for the AI agent research community

---

<p align="center">
  <strong>SF-AgentBench</strong> — Bridging AI Agents and Enterprise Platform Development
</p>
