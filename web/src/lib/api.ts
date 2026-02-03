// API Client for SF-AgentBench

import type {
  RunListResponse,
  RunDetail,
  RunSummary,
  AgentComparison,
  QARunListResponse,
  QARunDetail,
  QAModelComparison,
  QADomainAnalysis,
  TaskListResponse,
  TaskDetail,
  ModelListResponse,
  AgentListResponse,
  TestBankListResponse,
  Config,
} from '@/types/api'

const API_BASE = '/api'

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'API request failed')
  }

  return response.json()
}

// Runs API

export async function listRuns(params?: {
  task_id?: string
  agent_id?: string
  status?: string
  limit?: number
  offset?: number
}): Promise<RunListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.task_id) searchParams.set('task_id', params.task_id)
  if (params?.agent_id) searchParams.set('agent_id', params.agent_id)
  if (params?.status) searchParams.set('status', params.status)
  if (params?.limit) searchParams.set('limit', params.limit.toString())
  if (params?.offset) searchParams.set('offset', params.offset.toString())

  const query = searchParams.toString()
  return fetchAPI<RunListResponse>(`/runs${query ? `?${query}` : ''}`)
}

export async function getRun(runId: string): Promise<RunDetail> {
  return fetchAPI<RunDetail>(`/runs/${runId}`)
}

export async function getRunSummary(): Promise<RunSummary> {
  return fetchAPI<RunSummary>('/runs/summary')
}

export async function getAgentComparison(): Promise<AgentComparison[]> {
  return fetchAPI<AgentComparison[]>('/runs/comparison')
}

export async function createRun(data: {
  task_id: string
  agent_id: string
  model?: string
  timeout?: number
}): Promise<{ run_id: string }> {
  return fetchAPI('/runs', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteRun(runId: string): Promise<void> {
  await fetchAPI(`/runs/${runId}`, { method: 'DELETE' })
}

export async function cancelRun(runId: string): Promise<void> {
  await fetchAPI(`/runs/${runId}/cancel`, { method: 'POST' })
}

// Q&A API

export async function listQARuns(params?: {
  model_id?: string
  test_bank_id?: string
  limit?: number
}): Promise<QARunListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.model_id) searchParams.set('model_id', params.model_id)
  if (params?.test_bank_id) searchParams.set('test_bank_id', params.test_bank_id)
  if (params?.limit) searchParams.set('limit', params.limit.toString())

  const query = searchParams.toString()
  return fetchAPI<QARunListResponse>(`/qa/runs${query ? `?${query}` : ''}`)
}

export async function getQARun(runId: string): Promise<QARunDetail> {
  return fetchAPI<QARunDetail>(`/qa/runs/${runId}`)
}

export async function getQAComparison(testBankId?: string): Promise<QAModelComparison[]> {
  const query = testBankId ? `?test_bank_id=${testBankId}` : ''
  return fetchAPI<QAModelComparison[]>(`/qa/comparison${query}`)
}

export async function getQADomainAnalysis(params?: {
  model_id?: string
  test_bank_id?: string
}): Promise<QADomainAnalysis[]> {
  const searchParams = new URLSearchParams()
  if (params?.model_id) searchParams.set('model_id', params.model_id)
  if (params?.test_bank_id) searchParams.set('test_bank_id', params.test_bank_id)

  const query = searchParams.toString()
  return fetchAPI<QADomainAnalysis[]>(`/qa/domains${query ? `?${query}` : ''}`)
}

export async function listTestBanks(): Promise<TestBankListResponse> {
  return fetchAPI<TestBankListResponse>('/qa/banks')
}

// Tasks API

export async function listTasks(params?: {
  tier?: string
  category?: string
}): Promise<TaskListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.tier) searchParams.set('tier', params.tier)
  if (params?.category) searchParams.set('category', params.category)

  const query = searchParams.toString()
  return fetchAPI<TaskListResponse>(`/tasks${query ? `?${query}` : ''}`)
}

export async function getTask(taskId: string): Promise<TaskDetail> {
  return fetchAPI<TaskDetail>(`/tasks/${taskId}`)
}

// Models API

export async function listModels(provider?: string): Promise<ModelListResponse> {
  const query = provider ? `?provider=${provider}` : ''
  return fetchAPI<ModelListResponse>(`/models${query}`)
}

// Agents API

export async function listAgents(): Promise<AgentListResponse> {
  return fetchAPI<AgentListResponse>('/agents')
}

// Config API

export async function getConfig(): Promise<Config> {
  return fetchAPI<Config>('/config')
}

// Health API

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return fetchAPI('/health')
}

// Prompt Runner API

import type {
  PromptRun,
  PromptRunDetail,
  PromptRunListResponse,
} from '@/types/api'

export async function createPromptRun(data: {
  prompt: string
  iterations: number
}): Promise<PromptRun> {
  return fetchAPI('/prompt-runs', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function listPromptRuns(params?: {
  limit?: number
  offset?: number
}): Promise<PromptRunListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.limit) searchParams.set('limit', params.limit.toString())
  if (params?.offset) searchParams.set('offset', params.offset.toString())

  const query = searchParams.toString()
  return fetchAPI<PromptRunListResponse>(`/prompt-runs${query ? `?${query}` : ''}`)
}

export async function getPromptRun(runId: string): Promise<PromptRunDetail> {
  return fetchAPI<PromptRunDetail>(`/prompt-runs/${runId}`)
}

export async function cancelPromptRun(runId: string): Promise<void> {
  await fetchAPI(`/prompt-runs/${runId}/cancel`, { method: 'POST' })
}
