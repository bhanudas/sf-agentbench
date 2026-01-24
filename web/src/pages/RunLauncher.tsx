import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  PlayCircle,
  CheckCircle,
  AlertCircle,
  Layers,
  Bot,
  Settings,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { listTasks, listAgents, createRun } from '@/lib/api'
import { getTierColor, cn } from '@/lib/utils'

export function RunLauncher() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedTask, setSelectedTask] = useState<string>('')
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [timeout, setTimeout] = useState<number>(1800)

  const { data: tasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => listTasks(),
  })

  const { data: agentsData, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: listAgents,
  })

  const createRunMutation = useMutation({
    mutationFn: createRun,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
      navigate(`/runs/${data.run_id}/live`)
    },
  })

  const selectedTaskData = tasksData?.tasks.find((t) => t.id === selectedTask)
  const selectedAgentData = agentsData?.agents.find((a) => a.id === selectedAgent)

  const canLaunch = selectedTask && selectedAgent

  const handleLaunch = () => {
    if (!canLaunch) return

    createRunMutation.mutate({
      task_id: selectedTask,
      agent_id: selectedAgent,
      model: selectedModel || undefined,
      timeout,
    })
  }

  // Group tasks by tier
  const tasksByTier = tasksData?.tasks.reduce(
    (acc, task) => {
      const tier = task.tier
      if (!acc[tier]) acc[tier] = []
      acc[tier].push(task)
      return acc
    },
    {} as Record<string, typeof tasksData.tasks>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Launch Benchmark</h1>
        <p className="text-muted-foreground">
          Select a task and agent to start a new benchmark run
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Task Selection */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5" />
              <CardTitle>Select Task</CardTitle>
            </div>
            <CardDescription>Choose a benchmark task to run</CardDescription>
          </CardHeader>
          <CardContent>
            {tasksLoading ? (
              <div className="flex items-center justify-center h-40">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
              </div>
            ) : tasksByTier ? (
              <div className="space-y-6">
                {Object.entries(tasksByTier)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([tier, tasks]) => (
                    <div key={tier}>
                      <h3 className="font-medium mb-2 flex items-center gap-2">
                        <Badge className={getTierColor(tier)}>{tier}</Badge>
                        <span className="text-sm text-muted-foreground">
                          {tasks.length} tasks
                        </span>
                      </h3>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {tasks.map((task) => (
                          <button
                            key={task.id}
                            onClick={() => setSelectedTask(task.id)}
                            className={cn(
                              'flex items-start gap-3 p-3 rounded-lg border text-left transition-colors',
                              selectedTask === task.id
                                ? 'border-primary bg-primary/5'
                                : 'hover:border-muted-foreground/50'
                            )}
                          >
                            <div
                              className={cn(
                                'mt-0.5 h-4 w-4 rounded-full border-2',
                                selectedTask === task.id
                                  ? 'border-primary bg-primary'
                                  : 'border-muted-foreground/30'
                              )}
                            >
                              {selectedTask === task.id && (
                                <CheckCircle className="h-3 w-3 text-primary-foreground" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">{task.name}</p>
                              <p className="text-xs text-muted-foreground line-clamp-2">
                                {task.description || 'No description'}
                              </p>
                              <div className="flex gap-1 mt-1">
                                {task.categories.slice(0, 3).map((cat) => (
                                  <Badge
                                    key={cat}
                                    variant="outline"
                                    className="text-xs px-1"
                                  >
                                    {cat}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <AlertCircle className="h-8 w-8 mx-auto mb-2" />
                <p>No tasks found</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Configuration Panel */}
        <div className="space-y-6">
          {/* Agent Selection */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                <CardTitle>Select Agent</CardTitle>
              </div>
              <CardDescription>Choose an AI agent</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {agentsLoading ? (
                <div className="flex items-center justify-center h-20">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
                </div>
              ) : (
                <div className="space-y-2">
                  {agentsData?.agents.map((agent) => (
                    <button
                      key={agent.id}
                      onClick={() => {
                        setSelectedAgent(agent.id)
                        setSelectedModel(agent.default_model)
                      }}
                      disabled={!agent.is_installed}
                      className={cn(
                        'w-full flex items-center justify-between p-3 rounded-lg border text-left transition-colors',
                        !agent.is_installed && 'opacity-50 cursor-not-allowed',
                        selectedAgent === agent.id
                          ? 'border-primary bg-primary/5'
                          : 'hover:border-muted-foreground/50'
                      )}
                    >
                      <div>
                        <p className="font-medium">{agent.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {agent.default_model}
                        </p>
                      </div>
                      {agent.is_installed ? (
                        <Badge variant="success" className="text-xs">
                          Ready
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">
                          Not Installed
                        </Badge>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Configuration */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                <CardTitle>Configuration</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Model Override</label>
                <Select value={selectedModel || "__default__"} onValueChange={(v) => setSelectedModel(v === "__default__" ? "" : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Use agent default" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__default__">Use agent default</SelectItem>
                    <SelectItem value="gemini-2.0-flash">Gemini 2.0 Flash</SelectItem>
                    <SelectItem value="claude-sonnet-4-20250514">Claude Sonnet 4</SelectItem>
                    <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Timeout (seconds)</label>
                <Select
                  value={timeout.toString()}
                  onValueChange={(v) => setTimeout(parseInt(v))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="300">5 minutes</SelectItem>
                    <SelectItem value="600">10 minutes</SelectItem>
                    <SelectItem value="1200">20 minutes</SelectItem>
                    <SelectItem value="1800">30 minutes</SelectItem>
                    <SelectItem value="3600">1 hour</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Launch Button */}
          <Button
            className="w-full h-12 text-lg gap-2"
            disabled={!canLaunch || createRunMutation.isPending}
            onClick={handleLaunch}
          >
            {createRunMutation.isPending ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-foreground" />
                Starting...
              </>
            ) : (
              <>
                <PlayCircle className="h-5 w-5" />
                Launch Benchmark
              </>
            )}
          </Button>

          {/* Summary */}
          {canLaunch && (
            <Card className="bg-muted/50">
              <CardContent className="pt-4 text-sm">
                <p>
                  <strong>Task:</strong> {selectedTaskData?.name}
                </p>
                <p>
                  <strong>Agent:</strong> {selectedAgentData?.name}
                </p>
                <p>
                  <strong>Model:</strong>{' '}
                  {selectedModel || selectedAgentData?.default_model || 'default'}
                </p>
                <p>
                  <strong>Timeout:</strong> {timeout / 60} minutes
                </p>
              </CardContent>
            </Card>
          )}

          {createRunMutation.isError && (
            <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              {createRunMutation.error.message}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
