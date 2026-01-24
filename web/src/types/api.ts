// API Types for SF-AgentBench

export interface RunScores {
  deployment: number
  tests: number
  static_analysis: number
  metadata: number
  rubric: number
  final: number
}

export interface Run {
  run_id: string
  task_id: string
  task_name: string
  agent_id: string
  started_at: string
  completed_at: string | null
  duration_seconds: number
  scores: RunScores
  status: 'pending' | 'running' | 'completed' | 'failed'
  error: string | null
  scratch_org_username: string | null
}

export interface RunDetail extends Run {
  agent_output: string
  evaluation: EvaluationResult | null
}

export interface EvaluationResult {
  deployment: DeploymentResult | null
  deployment_score: number
  apex_tests: ApexTestResult | null
  test_score: number
  static_analysis: StaticAnalysisResult | null
  static_analysis_score: number
  metadata_diff: MetadataDiffResult | null
  metadata_score: number
  rubric: RubricResult | null
  rubric_score: number
  final_score: number
}

export interface DeploymentResult {
  status: 'success' | 'failure' | 'partial'
  deployed_count: number
  failed_count: number
  errors: DeploymentError[]
  duration_seconds: number
}

export interface DeploymentError {
  component_type: string
  component_name: string
  line: number | null
  column: number | null
  message: string
  error_code: string | null
}

export interface ApexTestResult {
  total_tests: number
  passed: number
  failed: number
  skipped: number
  pass_rate: number
  code_coverage: number
  test_results: TestMethodResult[]
  duration_seconds: number
}

export interface TestMethodResult {
  class_name: string
  method_name: string
  status: 'pass' | 'fail' | 'skip'
  message: string | null
  stack_trace: string | null
  duration_ms: number
}

export interface StaticAnalysisResult {
  total_violations: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  violations: PMDViolation[]
  penalty_score: number
}

export interface PMDViolation {
  rule: string
  severity: string
  file: string
  line: number
  column: number | null
  message: string
}

export interface MetadataDiffResult {
  is_match: boolean
  accuracy_score: number
  missing_components: string[]
  extra_components: string[]
  differences: Record<string, unknown>
}

export interface RubricResult {
  overall_score: number
  criteria: RubricCriterion[]
  feedback: string
}

export interface RubricCriterion {
  name: string
  weight: number
  score: number
  reasoning: string
}

export interface RunListResponse {
  runs: Run[]
  total: number
  limit: number
  offset: number
}

export interface RunSummary {
  total_runs: number
  completed_runs: number
  failed_runs: number
  best_score: number
  worst_score: number
  average_score: number
  runs_by_agent: Record<string, number>
  avg_score_by_agent: Record<string, number>
  runs_by_task: Record<string, number>
  avg_score_by_task: Record<string, number>
  first_run: string | null
  last_run: string | null
}

export interface AgentComparison {
  agent_id: string
  total_runs: number
  completed_runs: number
  average_score: number
  best_score: number
  avg_deployment: number
  avg_tests: number
  avg_static_analysis: number
  avg_metadata: number
  avg_rubric: number
  tasks_completed: string[]
}

// Q&A Types

export interface QAQuestion {
  question_id: string
  domain: string
  difficulty: string
  question_text: string
  correct_answer: string
  model_response: string
  extracted_answer: string
  is_correct: boolean
  response_time: number
  timestamp: string
}

export interface QARun {
  run_id: string
  model_id: string
  cli_id: string
  test_bank_id: string
  test_bank_name: string | null
  started_at: string
  completed_at: string | null
  total_questions: number
  correct_answers: number
  accuracy: number
  duration_seconds: number
  status: string
}

export interface QARunDetail extends QARun {
  questions: QAQuestion[]
}

export interface QARunListResponse {
  runs: QARun[]
  total: number
}

export interface QAModelComparison {
  model_id: string
  run_count: number
  avg_accuracy: number
  best_accuracy: number
  avg_duration: number
  total_questions: number
  total_correct: number
}

export interface QADomainAnalysis {
  domain: string
  model_id: string
  total_questions: number
  correct_answers: number
  accuracy: number
  avg_response_time: number
}

// Task Types

export interface Task {
  id: string
  name: string
  description: string
  tier: string
  categories: string[]
  time_limit_minutes: number
}

export interface TaskDetail extends Task {
  readme: string
  evaluation_tests: string[]
  requires_data: boolean
}

export interface TaskListResponse {
  tasks: Task[]
  total: number
}

// Model Types

export interface AIModel {
  id: string
  name: string
  provider: string
  api_key_env: string | null
  context_window: number
  is_available: boolean
}

export interface ModelListResponse {
  models: AIModel[]
  total: number
}

// Agent Types

export interface CLIAgent {
  id: string
  name: string
  default_model: string
  is_installed: boolean
  command: string
}

export interface AgentListResponse {
  agents: CLIAgent[]
  total: number
}

// Test Bank Types

export interface TestBank {
  id: string
  name: string
  description: string
  question_count: number
  domains: string[]
}

export interface TestBankListResponse {
  banks: TestBank[]
  total: number
}

// Config Types

export interface Config {
  devhub_username: string | null
  tasks_dir: string
  results_dir: string
  evaluation_weights: Record<string, number>
  default_model: string | null
}

// WebSocket Event Types

export interface WSEvent {
  type: string
  data: Record<string, unknown>
}

export interface WSLogEvent {
  level: string
  source: string
  message: string
  work_unit_id: string | null
  details: Record<string, unknown>
}

export interface WSStatusEvent {
  work_unit_id: string
  status: string
  progress: number | null
  metrics: Record<string, unknown>
}

export interface WSProgressEvent {
  work_unit_id: string
  current: number
  total: number
  message: string
}
