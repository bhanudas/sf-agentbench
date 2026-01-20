# Architectural Design and Benchmarking Framework for Agentic Salesforce Development: A Comprehensive Technical Report

---

## 1. Executive Summary

The emergence of agentic Artificial Intelligence (AI) necessitates a paradigm shift in how we evaluate model capabilities. While current benchmarks like SWE-bench effectively assess code generation in file-based languages such as Python or Java, they fail to capture the architectural complexity of Platform-as-a-Service (PaaS) environments like Salesforce. Salesforce development is not merely a coding discipline; it is a hybrid practice requiring the orchestration of declarative metadata, proprietary programming languages (Apex, SOQL), and stateful database interactions within a multi-tenant environment governed by strict execution limits.

This report presents a rigorous technical design for **SF-AgentBench**, a specialized benchmarking framework designed to evaluate AI agents—powered by tools like Claude Code, Codex, or Gemini Orchestrator—on their ability to design and build Salesforce solutions. The framework is grounded in the official Salesforce curriculum, specifically mapping to the Administrator (ADM-201) and Platform Developer (PD1/PD2) certifications. It utilizes the "Superbadge" methodology—complex, scenario-based problem solving—as the gold standard for evaluation, moving beyond atomic code generation to holistic solution architecture.

The proposed architecture introduces a novel **Agent-Computer Interface (ACI)** that wraps the Salesforce CLI (`sf`), enabling agents to operate securely within ephemeral Scratch Orgs. This design addresses the unique challenges of the domain: the coupling of metadata and data, the enforcement of Governor Limits, and the necessity of destructive testing. By integrating multi-layered evaluation metrics—including deployment validation, functional Apex testing, static code analysis (PMD), and metadata configuration diffing—the framework provides a nuanced assessment of an agent's true capability. This report details the skills taxonomy, the orchestration architecture, the design of agentic tools, and the scoring methodologies required to distinguish between hallucinated configuration and functional enterprise delivery.

---

## 2. Domain Analysis: The Salesforce Competency Taxonomy

To construct a valid benchmark, one must first deconstruct the domain into testable atomic and composite skills. The Salesforce ecosystem presents a unique challenge for AI models trained on general-purpose codebases because the "source of truth" is often split between the local file system (metadata) and the cloud environment (database schema and configuration).

### 2.1 The Hybrid Nature of Salesforce Engineering

Salesforce engineering is characterized by the coexistence of **Declarative Development** (low-code/no-code) and **Programmatic Development** (code). An effective AI agent must understand when to apply which paradigm and how they interact. This hybrid nature creates specific failure modes for AI agents that pure coding benchmarks miss.

- **Metadata Dependency**: A programmatic trigger often relies on a declarative field existing on an object. An agent failing to deploy the `CustomField` metadata before the `ApexTrigger` will encounter a deployment failure. This requires the agent to understand dependency graphs and deployment order, a skill distinct from syntax generation.[^1]

- **Governor Limits**: Unlike local execution environments (like a Python container), Salesforce enforces strict runtime limits (SOQL queries, CPU time, heap size) to ensure multi-tenant stability. Agents must generate "bulkified" code that processes collections of records rather than iterating individual operations. A structurally correct Python function might translate to a disastrously inefficient Apex trigger if the agent does not conceptually grasp "bulkification".[^3]

- **Contextual Security**: Visibility of data is controlled by a complex intersection of Profiles, Permission Sets, and Sharing Rules. An agent might write a perfect query, but if the running user lacks the Permission Set to see the field, the query returns null. Agents must demonstrate the ability to configure these security layers correctly to ensure the code actually functions in production.[^5]

### 2.2 Administrator Skills Curriculum (ADM-201 & Advanced Admin)

The benchmark must test the following administrative domains, derived from the ADM-201 exam guide and real-world administrative tasks.

#### 2.2.1 Configuration and Object Architecture

- **Schema Management**: Creating Custom Objects, Fields (Master-Detail, Lookup, Formula), and Page Layouts. The agent must understand the implications of field types on reporting and relationships. For instance, converting a Master-Detail relationship to a Lookup has profound security implications regarding record ownership that an agent must navigate.

- **Data Validation**: Implementing Validation Rules using formulas (e.g., `AND`, `OR`, `ISBLANK`, `VLOOKUP`). This tests the agent's logical reasoning and understanding of Salesforce formula syntax, which differs significantly from Excel or standard programming logic. The agent must construct boolean logic that evaluates to `TRUE` to block an action, a "negative logic" pattern that often confuses basic models.[^8]

- **User Interface**: Configuring Lightning App Builder pages, Record Types, and assigning them to Profiles. This involves manipulating XML metadata for `FlexiPage` and `Layout` components.

#### 2.2.2 Process Automation

- **Flow Orchestration**: Designing Screen Flows, Record-Triggered Flows, and Autolaunched Flows. As Salesforce retires Workflow Rules and Process Builder, Flow has become the primary automation engine. The benchmark must test the agent's ability to generate the complex XML metadata for a Flow, which includes `<decisions>`, `<loops>`, `<assignments>`, and `<recordCreates>`. This is effectively visual programming serialized into XML.[^10]

- **Approval Processes**: Defining multi-step approval logic, entry criteria, and approver assignment. The agent must configure the `ApprovalProcess` metadata, defining steps, rejection actions, and recall actions.[^12]

#### 2.2.3 Security and Access

- **Security Model**: Configuring Organization-Wide Defaults (OWD), Role Hierarchies, and Sharing Rules.

- **Permissions**: Creating Permission Sets and Profiles to grant granular access to objects and fields. The agent must be able to modify the `Profile` metadata to set `<fieldPermissions>` and `<objectPermissions>` correctly without overwriting existing settings.[^5]

### 2.3 Developer Skills Curriculum (PD1 & PD2)

The developer track requires the agent to manipulate the platform via code, tested against the PD1 and PD2 competencies.[^2]

#### 2.3.1 Apex Fundamentals and Logic

- **Triggers**: Writing triggers that handle events (`before insert`, `after update`) and adhering to the "One Trigger Per Object" pattern. The agent must handle `Trigger.new`, `Trigger.old`, and context variables (`Trigger.isInsert`, `Trigger.isBefore`). It must demonstrate recursion handling to prevent stack depth overflows.[^3]

- **Object-Oriented Design**: Implementing interfaces, abstract classes, and virtual methods within the Apex type system.

- **Testing**: Writing `@IsTest` classes with `System.assert` to validate logic and ensuring 75% code coverage. This includes using `Test.startTest()` and `Test.stopTest()` to reset governor limits and testing user contexts with `System.runAs()`.[^17]

#### 2.3.2 Data Integration and Asynchronous Processing

- **SOQL/SOSL**: Constructing efficient queries, understanding relationship queries (Parent-to-Child subqueries, Child-to-Parent dot notation), and strictly avoiding queries inside loops.

- **Asynchronous Apex**: Implementing `Batchable`, `Queueable`, `Schedulable`, and `Future` methods for long-running processes. The agent must understand when to use `Queueable` (chaining jobs) vs `Future` (simple primitive parameter calls).[^14]

- **APIs**: Designing Apex REST services (`@RestResource`) and consuming external web services (WSDL to Apex, HTTP Callouts). The agent must handle authentication via Named Credentials rather than hardcoding endpoints.[^20]

#### 2.3.3 User Interface Development

- **Lightning Web Components (LWC)**: Writing JavaScript controllers, HTML templates, and CSS. The agent must understand the reactive wire service (`@wire`) for data provisioning and the interaction between parent and child components via events and public properties (`@api`).[^21][^22]

- **Aura Components**: While legacy, understanding Aura is still required for certain platform extensions and Lightning Out scenarios.

---

## 3. Orchestration Architecture: The Agent Execution Environment

The benchmark framework requires a sophisticated orchestration layer that manages the lifecycle of Salesforce environments, provisions agent tooling, and collects evaluation artifacts. This section details the proposed architecture, drawing inspiration from the SWE-agent model while adapting it to the unique constraints of the Salesforce platform.[^23]

### 3.1 The Ephemeral Scratch Org Model

Unlike a Docker container that can be spun up in seconds, a Salesforce development environment requires a "Scratch Org"—a temporary, configurable, and disposable Salesforce instance. Scratch Orgs are central to the Salesforce DX (Developer Experience) workflow and are the only practical way to run automated tests against a clean, isolated state.[^24]

#### 3.1.1 Scratch Org Definition Files

Each benchmark task will be associated with a `project-scratch-def.json` file that specifies the org's edition, features, and settings. For example, a task involving Service Cloud features would require:

```json
{
  "orgName": "SF-AgentBench - Service Cloud Task",
  "edition": "Developer",
  "features": ["ServiceCloud", "Communities"],
  "settings": {
    "caseSettings": {
      "systemUserEmail": "admin@example.com"
    },
    "knowledgeSettings": {
      "enableKnowledge": true
    }
  }
}
```

This definition file is critical. An incorrectly specified definition will cause the agent to fail not because of its solution logic, but because the required platform features are unavailable. The benchmark harness must ensure these definitions are accurate and pre-validated.[^26]

#### 3.1.2 Org Snapshots for Rapid Provisioning

Standard Scratch Org creation takes 1-3 minutes, which is acceptable for a single run but becomes a bottleneck at scale. To accelerate benchmarking, the framework should leverage **Org Snapshots**. A snapshot captures the state of a fully configured Scratch Org (with base metadata and data deployed) and allows new orgs to be spun up from that snapshot in significantly less time.[^25]

**Workflow:**

1. **Baseline Org Creation**: A Scratch Org is created manually with all prerequisite metadata (e.g., standard objects, required packages).
2. **Snapshot Capture**: The org state is captured as a snapshot.
3. **Agent Run**: For each benchmark run, a new Scratch Org is created from the snapshot.
4. **Evaluation & Teardown**: The agent's work is evaluated, and the org is deleted.

This model ensures reproducibility and isolates agent runs from one another.

#### 3.1.3 Resource Allocation and Limits

Salesforce DevHub accounts have limits on the number of active Scratch Orgs and daily creation limits. A production-grade benchmark harness must implement a queueing system to manage agent runs within these constraints.[^30][^31]

| Resource               | Limit (Enterprise DevHub) |
|------------------------|---------------------------|
| Active Scratch Orgs    | 200                       |
| Daily Scratch Org Creates | 80                     |
| Snapshot Storage       | 5 snapshots               |

### 3.2 Data Provisioning Strategies

Many benchmark tasks require pre-existing data (e.g., "Given a list of Accounts with related Opportunities, write a batch job..."). Provisioning this data reliably is a non-trivial problem.

#### 3.2.1 `sf data tree import`

The Salesforce CLI provides `sf data tree import` to load records from JSON files that preserve relationships via reference IDs.[^28]

```bash
sf data tree import --files Account.json,Contact.json --plan data-plan.json
```

**Limitation**: This command struggles with self-referential lookups (e.g., an `Account` with a `ParentId` pointing to another `Account` in the same import). The order of operations matters, and the CLI does not always resolve it correctly.[^32]

#### 3.2.2 SFDMU Plugin

For more complex data scenarios, the **Salesforce Data Move Utility (SFDMU)** plugin is recommended. It handles complex relationships, external ID mapping, and can migrate data between orgs.[^29]

```bash
sf sfdmu run --sourceusername source_org --targetusername target_scratch_org
```

The benchmark framework should use SFDMU for tasks requiring complex data hierarchies.

### 3.3 The Agent-Computer Interface (ACI)

The ACI is the set of tools exposed to the AI agent. A well-designed ACI is crucial for agent performance; a poorly designed one can handicap even a capable model.[^37] For SF-AgentBench, the ACI wraps the Salesforce CLI (`sf`) and provides structured, domain-specific commands.

#### 3.3.1 Core Tool Design Principles

1. **Atomic Actions**: Each tool should perform one clear action (e.g., `deploy_metadata`, `run_apex_tests`). Combining actions reduces the agent's ability to diagnose failures.

2. **Structured Output**: Tool outputs should be machine-readable (JSON) rather than human-readable prose. This allows the agent to parse results programmatically.

3. **Error Contextualization**: When a command fails, the tool should return the specific error message from the Salesforce API, not a generic failure. Deployment errors, for example, should include the component name, line number, and error code.

4. **Idempotency**: Where possible, tools should be idempotent. Running `deploy_metadata` twice with the same input should not cause errors.

#### 3.3.2 Proposed Tool Catalog

| Tool Name            | Description                                                              | Underlying CLI Command                     |
|----------------------|--------------------------------------------------------------------------|--------------------------------------------|
| `sf_deploy`          | Deploys metadata from the local project to the Scratch Org.              | `sf project deploy start`                  |
| `sf_retrieve`        | Retrieves metadata from the Scratch Org to the local project.            | `sf project retrieve start`                |
| `sf_run_apex_tests`  | Executes Apex test classes and returns pass/fail results with coverage.  | `sf apex run test`                         |
| `sf_run_anonymous`   | Executes anonymous Apex code for quick validation or data manipulation.  | `sf apex run`                              |
| `sf_query`           | Executes a SOQL query and returns records.                               | `sf data query`                            |
| `sf_create_record`   | Creates a single record of a specified sObject type.                     | `sf data create record`                    |
| `sf_import_data`     | Imports data from a plan file.                                           | `sf data tree import`                      |
| `sf_scan_code`       | Runs static analysis (PMD) on the codebase.                              | `sf scanner run`                           |
| `sf_org_open`        | Returns the login URL for the Scratch Org (for debugging/verification).  | `sf org open --url-only`                   |

#### 3.3.3 Example Tool Interaction

**Agent Request:**

```json
{
  "tool": "sf_deploy",
  "parameters": {
    "source_path": "force-app/main/default"
  }
}
```

**Harness Response (Success):**

```json
{
  "status": "success",
  "deployed_components": 15,
  "details": [
    {"type": "ApexClass", "name": "AccountTriggerHandler", "state": "Changed"},
    {"type": "CustomField", "name": "Account.Industry_Score__c", "state": "Created"}
  ]
}
```

**Harness Response (Failure):**

```json
{
  "status": "failure",
  "errors": [
    {
      "component": "ApexClass/AccountTriggerHandler",
      "line": 45,
      "column": 12,
      "message": "Variable does not exist: acountRecord",
      "error_code": "FIELD_INTEGRITY_EXCEPTION"
    }
  ]
}
```

---

## 4. Benchmark Task Design: The Superbadge Methodology

The Salesforce "Superbadge" is a credential earned by completing a complex, multi-faceted project in a hands-on environment. Unlike simple coding challenges, Superbadges require the practitioner to synthesize multiple skills—schema design, automation, code, and testing—to deliver a complete solution. This methodology is the ideal template for SF-AgentBench tasks.[^33][^34]

### 4.1 Task Structure

Each benchmark task is a self-contained project with the following components:

| Component              | Description                                                                                           |
|------------------------|-------------------------------------------------------------------------------------------------------|
| `README.md`            | The problem statement, written as a business requirements document from a fictional stakeholder.      |
| `project-scratch-def.json` | The Scratch Org definition specifying required features and settings.                             |
| `sfdx-project.json`    | The SFDX project configuration.                                                                       |
| `force-app/`           | The source directory. May contain pre-existing "starter" metadata the agent must extend.             |
| `data/`                | JSON files for `sf data tree import` to provision prerequisite records.                               |
| `evaluation/`          | Contains evaluation scripts, expected metadata snapshots, and Apex test classes for validation.      |

### 4.2 Example Task: Apex Specialist Superbadge (Adapted)

This task is adapted from the official Trailhead Apex Specialist Superbadge.[^35][^36]

#### 4.2.1 Business Requirements (`README.md` Excerpt)

> **How Much Maintenance Superbadge**
>
> You are a developer at HowWeRoll Rentals, a recreational vehicle (RV) rental company. The company needs to automate its vehicle maintenance process.
>
> **Requirements:**
>
> 1. **Maintenance Request Automation**: When a maintenance request of type "Repair" or "Routine Maintenance" is closed, automatically create a new "Routine Maintenance" request for the same vehicle. The due date should be calculated based on the shortest maintenance cycle of all equipment items associated with the original request.
>
> 2. **Bulkification**: The solution must handle up to 300 maintenance requests being closed simultaneously.
>
> 3. **Asynchronous Processing**: Due to the complex calculations, the automated creation of new requests must occur asynchronously.
>
> 4. **Test Coverage**: Provide at least 75% code coverage for all Apex classes.

#### 4.2.2 Pre-Provisioned Metadata (`force-app/` Contents)

- `Case.object-meta.xml`: Standard Case object used for Maintenance Requests.
- `Equipment__c.object-meta.xml`: Custom object for tracking RV equipment.
- `Equipment_Maintenance_Item__c.object-meta.xml`: Junction object linking Equipment to Maintenance Requests.
- `Vehicle__c.object-meta.xml`: Custom object representing an RV.

#### 4.2.3 Pre-Provisioned Data (`data/` Contents)

- `Vehicle__c.json`: 10 vehicle records.
- `Equipment__c.json`: 50 equipment records with varying `Maintenance_Cycle__c` values.
- `Case.json`: 5 open maintenance request records.
- `Equipment_Maintenance_Item__c.json`: 20 junction records linking equipment to cases.

### 4.3 Difficulty Tiering

Tasks should be tiered by complexity, mapping roughly to certification levels.

| Tier       | Complexity                                     | Example Task                                      | Skills Tested                                        |
|------------|------------------------------------------------|---------------------------------------------------|------------------------------------------------------|
| **Tier 1** | Single-domain, declarative focus.              | Create a Validation Rule and Flow for lead scoring. | Schema, Validation Rules, Record-Triggered Flow.     |
| **Tier 2** | Multi-domain, declarative + simple code.       | Build a screen flow that calls an Apex action.    | Screen Flow, Invocable Apex, Apex Testing.           |
| **Tier 3** | Complex code, async processing, integrations.  | Apex Specialist Superbadge (adapted).             | Triggers, Queueable Apex, Bulkification, Testing.    |
| **Tier 4** | Full-stack, LWC, external integrations.        | LWC Specialist Superbadge (adapted).              | LWC, Apex Services, Wire Adapters, Callouts.         |

---

## 5. Evaluation Metrics and Scoring Methodology

A robust benchmark requires a multi-layered evaluation framework. Relying solely on "does the code compile?" is insufficient; the benchmark must assess functional correctness, code quality, and solution design.

### 5.1 Layer 1: Deployment Validation

**Metric**: `deployment_success` (Boolean)

The most basic check is whether the agent's solution can be successfully deployed to the Scratch Org. The `sf project deploy start` command returns a detailed status.

**Scoring**:
- `1.0` if deployment succeeds with no errors.
- `0.0` if deployment fails.

**Error Categorization**: Deployment errors should be logged and categorized for analysis (e.g., missing dependency, syntax error, type mismatch). This data is valuable for understanding agent failure modes.

### 5.2 Layer 2: Functional Testing (Apex Tests)

**Metric**: `apex_test_pass_rate` (Float, 0.0 - 1.0)

The benchmark harness runs a predefined set of Apex test classes located in the `evaluation/` directory. These tests are designed to validate the business logic specified in the requirements.

**Scoring**:
- `(Number of Passing Tests) / (Total Number of Tests)`

**Code Coverage**: While 75% coverage is a Salesforce platform requirement, the benchmark should also record the coverage percentage achieved by the agent's own test classes (if they wrote any). This secondary metric (`agent_test_coverage`) indicates whether the agent understands the importance of testing.

```bash
sf apex run test --test-level RunSpecifiedTests --tests EvaluationTestClass --code-coverage --result-format json
```

### 5.3 Layer 3: Static Code Analysis (PMD/Code Analyzer)

**Metric**: `pmd_violations` (Integer)

Salesforce provides the Code Analyzer (powered by PMD) to detect code smells, security vulnerabilities, and performance issues.[^43][^44]

**Scoring**:
- A penalty can be applied based on the number and severity of violations.
- `score_modifier = -0.01 * (critical_violations * 3 + high_violations * 2 + medium_violations)`

**Key Rules to Enforce**:
- `ApexCRUDViolation`: Detects missing CRUD/FLS checks.
- `AvoidSoqlInLoops`: Detects SOQL queries inside loops (non-bulkified code).
- `ApexUnitTestClassShouldHaveAsserts`: Ensures test classes have meaningful assertions.

```bash
sf scanner run --target "force-app" --format json
```

### 5.4 Layer 4: Metadata Configuration Diffing

**Metric**: `metadata_accuracy` (Float, 0.0 - 1.0)

For declarative tasks (e.g., "Create a Flow that..."), functional tests may not be sufficient. The benchmark should compare the agent's generated metadata against a canonical "golden" metadata file.

**Approach**:
1. Define the expected metadata (e.g., `expected/flows/My_Flow.flow-meta.xml`).
2. After the agent deploys, retrieve the metadata from the org.
3. Perform a semantic diff, ignoring non-essential attributes like `xmlns` versions or whitespace.

**Tools**:
- `sfdx-git-delta` can be adapted to compare metadata between the agent's output and the expected baseline.[^47][^51]
- Custom diffing logic may be required for complex types like Flows, where node order may vary but functional equivalence is maintained.

### 5.5 Layer 5: Holistic Solution Rubric (LLM-as-a-Judge)

**Metric**: `rubric_score` (Float, 0.0 - 1.0)

For nuanced evaluation—such as code readability, adherence to design patterns ("One Trigger Per Object"), and appropriate use of declarative vs. programmatic solutions—an LLM-as-a-Judge approach can be employed.[^45][^46]

**Rubric Example**:

| Criterion                      | Weight | Description                                                                 |
|--------------------------------|--------|-----------------------------------------------------------------------------|
| Correct Use of Async Apex      | 0.25   | Did the agent use `Queueable` or `Batchable` where appropriate?             |
| Bulkification                  | 0.25   | Are DML and SOQL operations performed on collections, not single records?   |
| Test Quality                   | 0.20   | Do the agent's tests use `System.assert` effectively and cover edge cases?  |
| Code Readability               | 0.15   | Are variables named clearly? Is logic separated into helper methods?        |
| Security Best Practices        | 0.15   | Are CRUD/FLS checks present? Are hardcoded IDs avoided?                     |

A separate, powerful LLM (potentially the same model in a different context, or a different model entirely) evaluates the agent's code against this rubric and provides a score.

### 5.6 Composite Scoring

The final score for a task can be a weighted combination of the above layers:

```
Final_Score = (
    0.20 * deployment_success +
    0.40 * apex_test_pass_rate +
    0.10 * (1 - min(pmd_penalty, 0.10)) +  # Cap penalty at 10%
    0.15 * metadata_accuracy +
    0.15 * rubric_score
)
```

Weights can be adjusted based on the task's focus (e.g., a purely declarative task might weight `metadata_accuracy` higher).

---

## 6. Implementation Roadmap

### 6.1 Phase 1: Foundation (Months 1-2)

- **Objective**: Establish the core infrastructure.
- **Deliverables**:
  - DevHub setup with Scratch Org pool management.
  - ACI tool wrappers for core `sf` commands.
  - Basic harness for task loading, org provisioning, and evaluation.
  - 5 Tier 1 and 5 Tier 2 benchmark tasks.

### 6.2 Phase 2: Expansion (Months 3-4)

- **Objective**: Increase task coverage and evaluation depth.
- **Deliverables**:
  - Integration of PMD/Code Analyzer into the evaluation pipeline.
  - Metadata diffing capability for Flows and Profiles.
  - 10 Tier 3 tasks (adapted from Apex Specialist, Process Automation Specialist).
  - Baseline runs with 2-3 leading AI agents (e.g., Claude, GPT-4, Gemini).

### 6.3 Phase 3: Maturity (Months 5-6)

- **Objective**: Achieve production-ready benchmark.
- **Deliverables**:
  - LLM-as-a-Judge rubric evaluation.
  - 5 Tier 4 tasks (LWC Specialist, Data Integration Specialist adapted).
  - Public leaderboard and documentation.
  - Research paper submission.

---

## 7. Risks and Mitigations

| Risk                                      | Impact | Mitigation Strategy                                                                 |
|-------------------------------------------|--------|------------------------------------------------------------------------------------|
| Scratch Org provisioning latency          | High   | Use Org Snapshots; implement async queueing for agent runs.                        |
| Salesforce API/CLI breaking changes       | Medium | Pin `sf` CLI version; monitor Salesforce release notes for deprecated commands.    |
| Data provisioning complexity              | Medium | Use SFDMU for complex data; create robust data plans per task.                     |
| LLM-as-a-Judge inconsistency              | Medium | Use structured rubrics; average scores across multiple judge calls.                |
| Benchmark "gaming" by overfitting         | High   | Keep a held-out test set; release only training tasks publicly.                    |
| Cost of Scratch Org consumption           | Medium | Optimize snapshot usage; partner with Salesforce for increased DevHub limits.      |

---

## 8. Conclusion

SF-AgentBench represents a significant advancement in AI benchmarking by targeting the under-evaluated domain of enterprise PaaS development. By grounding the framework in the rigorous, real-world requirements of Salesforce certifications and Superbadges, the benchmark ensures practical relevance. The proposed architecture—leveraging ephemeral Scratch Orgs, a well-designed Agent-Computer Interface, and multi-layered evaluation—provides the foundation for a fair and comprehensive assessment of agentic capabilities.

The development of this benchmark is not merely an academic exercise; it is a critical step toward enabling AI agents to function as reliable partners in enterprise software delivery. By understanding where current models succeed and fail within this complex domain, we can guide future research and development toward more capable, trustworthy, and deployable AI systems.

---

## References

[^1]: Salesforce Metadata API Developer Guide - Deployment Dependencies

[^2]: Salesforce Platform Developer 2 Study Guide | focusonforce.com. https://focusonforce.com/courses/platform-developer-2-study-guide/

[^3]: Apex Trigger Best Practices - Bulkification and Recursion Handling

[^5]: Custom Permissions in Apex | Salesforce Geek. https://salesforcegeek.in/how-to-use-custom-permissions-in-apex/

[^7]: Start Your Salesforce Admin Journey: ADM-201 Study Guide - Test-king.com. https://www.test-king.com/blog/start-your-salesforce-admin-journey-adm-201-study-guide/

[^8]: ValidationRule | Metadata API Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_validationformulas.htm

[^10]: Flow | Metadata API Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_visual_workflow.htm

[^12]: Process Automation Specialist Solution - GitHub. https://github.com/pkbparesh15/Process-Automation-Specialist-Solution

[^14]: Salesforce Platform Developer 2 Study Guide | focusonforce.com. https://focusonforce.com/courses/platform-developer-2-study-guide/

[^17]: Test Your Changes - Salesforce Help. https://help.salesforce.com/s/articleView?id=platform.testing_your_code.htm&language=en_US&type=5

[^20]: Data Integration Specialist Superbadge - GitHub. https://github.com/wallacelee/Data-Integration-Specialist-Superbadge

[^21]: Lightning Web Components Specialist Superbadge - Trailhead. https://trailhead.salesforce.com/users/jimsharp/trailmixes/unlock-and-complete-the-lightning-web-components-specialist-supe

[^22]: SuperBadge LWC - GitHub. https://github.com/CristianoFillho/SuperBadge-LWC

[^23]: SWE-agent Architecture Documentation. https://swe-agent.com/latest/background/architecture/

[^24]: Scratch Orgs | Salesforce DX Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_scratch_orgs.htm

[^25]: Create a Scratch Org Based on a Snapshot | Salesforce DX Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_snapshots_create_scratch_org.htm

[^26]: Build Your Own Scratch Org Definition File | Salesforce DX Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_scratch_orgs_def_file.htm

[^28]: sfdx force:data:tree:import | Salesforce Trailblazer Community. https://trailhead.salesforce.com/trailblazer-community/feed/0D54V00007T40wOSAR

[^29]: Salesforce Data Migration using SFDMU plugin | Medium. https://medium.com/@ayushchauhan1999/salesforce-data-migration-using-sfdmu-plugin-85716b951ca6

[^30]: Supported Scratch Org Editions and Allocations | Salesforce DX Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_scratch_orgs_editions_and_allocations.htm

[^31]: Scratch Org Allocations for Salesforce Partners | First-Generation Managed Packaging Developer Guide. https://developer.salesforce.com/docs/atlas.en-us.pkg1_dev.meta/pkg1_dev/isv_partner_scratch_org_allocations.htm

[^32]: Improve handling of self-referencing lookups - GitHub CLI Discussions. https://github.com/forcedotcom/cli/discussions/2364

[^33]: Superbadge: Apex for Agentforce - Trailhead. https://trailhead.salesforce.com/content/learn/superbadges/superbadge-apex-for-agentforce

[^34]: Superbadge: Flow Fundamentals - Trailhead. https://trailhead.salesforce.com/content/learn/superbadges/superbadge_flow_basics_sbu

[^35]: Apex Specialist Solution - GitHub. https://github.com/pkbparesh15/Apex-Specialist-Solution

[^36]: salesforce-superbadge-apex-specialist - GitHub. https://github.com/giuseppetropea/salesforce-superbadge-apex-specialist

[^37]: SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering - arXiv. https://arxiv.org/pdf/2405.15793

[^38]: Take a Deep Dive into Metadata API Deployments | Salesforce Developers Blog. https://developer.salesforce.com/blogs/2025/09/take-a-deep-dive-into-metadata-api-deployments

[^43]: PMD | Engines | Salesforce Code Analyzer. https://developer.salesforce.com/docs/platform/salesforce-code-analyzer/guide/engine-pmd.html

[^44]: scanner run (Retired) | Salesforce Code Analyzer v4. https://developer.salesforce.com/docs/platform/salesforce-code-analyzer/guide/run.html

[^45]: The science of rubric design | Snorkel AI. https://snorkel.ai/blog/the-science-of-rubric-design/

[^46]: ResearchRubrics: A Benchmark of Prompts and Rubrics For Evaluating Deep Research Agents - arXiv. https://arxiv.org//2511.07685v1

[^47]: sfdx-git-packager - GitHub. https://github.com/callawaycloud/sfdx-git-packager

[^51]: sfdx-git-delta - GitHub. https://github.com/scolladon/sfdx-git-delta
