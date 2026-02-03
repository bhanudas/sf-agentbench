import { useState, useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Send,
  Terminal,
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RotateCcw,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useWebSocket } from '@/hooks/useWebSocket'
import { createPromptRun } from '@/lib/api'
import { formatDuration, cn } from '@/lib/utils'
import type { PromptRun, PromptLogEvent } from '@/types/api'

interface LogEntry {
  timestamp: string
  level: string
  message: string
  iteration: number | null
}

export function PromptRunner() {
  const [prompt, setPrompt] = useState('')
  const [iterations, setIterations] = useState<string>('1')
  const [currentRun, setCurrentRun] = useState<PromptRun | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isComplete, setIsComplete] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // WebSocket connection for streaming logs
  const wsUrl = currentRun
    ? `ws://${window.location.host}/api/prompt-runs/ws/${currentRun.run_id}`
    : ''

  const { isConnected, lastMessage } = useWebSocket(wsUrl, {
    onMessage: (event) => {
      if (event.type === 'log') {
        const data = event.data as PromptLogEvent
        setLogs((prev) => [
          ...prev,
          {
            timestamp: data.timestamp as string,
            level: data.level as string,
            message: data.message as string,
            iteration: data.iteration as number | null,
          },
        ])
      } else if (event.type === 'status') {
        const data = event.data as { current_iteration: number; status: string }
        if (currentRun) {
          setCurrentRun({
            ...currentRun,
            current_iteration: data.current_iteration,
            status: data.status as PromptRun['status'],
          })
        }
      } else if (event.type === 'complete') {
        const data = event.data as { status: string; duration_seconds: number; error: string | null }
        if (currentRun) {
          setCurrentRun({
            ...currentRun,
            status: data.status as PromptRun['status'],
            duration_seconds: data.duration_seconds,
            error: data.error,
          })
        }
        setIsComplete(true)
      }
    },
  })

  // Create prompt run mutation
  const createMutation = useMutation({
    mutationFn: createPromptRun,
    onSuccess: (data) => {
      setCurrentRun(data)
      setLogs([])
      setIsComplete(false)
    },
  })

  // Auto-scroll to bottom of logs
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const handleSubmit = () => {
    if (!prompt.trim() || prompt.length < 10) {
      return
    }

    createMutation.mutate({
      prompt: prompt.trim(),
      iterations: parseInt(iterations),
    })
  }

  const handleReset = () => {
    setCurrentRun(null)
    setLogs([])
    setIsComplete(false)
    setPrompt('')
    textareaRef.current?.focus()
  }

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR':
        return 'text-red-500'
      case 'WARNING':
        return 'text-yellow-500'
      case 'INFO':
        return 'text-blue-500'
      case 'OUTPUT':
        return 'text-green-500'
      case 'DEBUG':
        return 'text-gray-500'
      default:
        return 'text-foreground'
    }
  }

  const getStatusBadge = () => {
    if (!currentRun) return null

    switch (currentRun.status) {
      case 'pending':
        return <Badge variant="secondary">Pending</Badge>
      case 'running':
        return (
          <Badge variant="default" className="animate-pulse">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Running
          </Badge>
        )
      case 'completed':
        return (
          <Badge variant="success">
            <CheckCircle className="h-3 w-3 mr-1" />
            Completed
          </Badge>
        )
      case 'failed':
        return (
          <Badge variant="destructive">
            <XCircle className="h-3 w-3 mr-1" />
            Failed
          </Badge>
        )
      case 'cancelled':
        return <Badge variant="outline">Cancelled</Badge>
      default:
        return <Badge variant="secondary">{currentRun.status}</Badge>
    }
  }

  const progress = currentRun
    ? (currentRun.current_iteration / currentRun.iterations) * 100
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Prompt Runner</h1>
        <p className="text-muted-foreground">
          Submit a Salesforce development challenge and watch Claude Code solve it
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Prompt Input Form */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Challenge Prompt</CardTitle>
            <CardDescription>
              Describe a Salesforce development task for Claude Code to solve
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <textarea
                ref={textareaRef}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Example: Create an Apex trigger on the Contact object that prevents duplicate contacts based on email address. The trigger should check both insert and update operations, and provide a clear error message when a duplicate is detected."
                className={cn(
                  'w-full min-h-[200px] p-4 rounded-lg border resize-none',
                  'bg-background text-foreground placeholder:text-muted-foreground',
                  'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
                  currentRun && 'opacity-50 cursor-not-allowed'
                )}
                disabled={!!currentRun}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{prompt.length} characters</span>
                <span>Minimum 10 characters required</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Configuration Panel */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Iterations</label>
                <Select
                  value={iterations}
                  onValueChange={setIterations}
                  disabled={!!currentRun}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 iteration</SelectItem>
                    <SelectItem value="5">5 iterations</SelectItem>
                    <SelectItem value="10">10 iterations</SelectItem>
                    <SelectItem value="25">25 iterations</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  More iterations allow for refinement and testing different approaches
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Agent</label>
                <div className="p-3 rounded-lg border bg-muted/50">
                  <p className="font-medium">Claude Code</p>
                  <p className="text-xs text-muted-foreground">
                    Anthropic's Claude with agentic coding capabilities
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action Button */}
          {!currentRun ? (
            <Button
              className="w-full h-12 text-lg gap-2"
              disabled={!prompt.trim() || prompt.length < 10 || createMutation.isPending}
              onClick={handleSubmit}
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Send className="h-5 w-5" />
                  Run Challenge
                </>
              )}
            </Button>
          ) : (
            <Button
              className="w-full h-12 text-lg gap-2"
              variant="outline"
              disabled={!isComplete}
              onClick={handleReset}
            >
              <RotateCcw className="h-5 w-5" />
              New Challenge
            </Button>
          )}

          {createMutation.isError && (
            <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              {createMutation.error.message}
            </div>
          )}
        </div>
      </div>

      {/* Run Status & Logs */}
      {currentRun && (
        <>
          {/* Status Cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Status
                </CardTitle>
              </CardHeader>
              <CardContent>{getStatusBadge()}</CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Iteration
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-medium">
                  {currentRun.current_iteration} / {currentRun.iterations}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Duration
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-lg font-medium">
                    {formatDuration(currentRun.duration_seconds)}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Progress
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <Progress value={progress} className="h-2" />
                  <div className="text-sm text-muted-foreground">
                    {progress.toFixed(0)}%
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Log Stream */}
          <Card className="flex flex-col h-[500px]">
            <CardHeader className="flex flex-row items-center justify-between py-3">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4" />
                <CardTitle className="text-sm font-medium">Live Output</CardTitle>
                <Badge variant={isConnected ? 'success' : 'outline'} className="text-xs">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {logs.length} events
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant={autoScroll ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setAutoScroll(!autoScroll)}
                >
                  Auto-scroll {autoScroll ? 'ON' : 'OFF'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setLogs([])}>
                  Clear
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto p-0 bg-black/90">
              <div className="font-mono text-xs text-white">
                {logs.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    <Activity className="h-6 w-6 mr-2 animate-pulse" />
                    Waiting for output...
                  </div>
                ) : (
                  logs.map((log, idx) => (
                    <div
                      key={idx}
                      className="px-4 py-1 hover:bg-white/5 border-b border-white/10"
                    >
                      <span className="text-gray-500">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      {log.iteration !== null && (
                        <span className="text-purple-400 mx-1">[{log.iteration}]</span>
                      )}
                      <span className={cn('mx-1', getLevelColor(log.level))}>
                        [{log.level}]
                      </span>
                      <span className="text-gray-200">{log.message}</span>
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </CardContent>
          </Card>

          {/* Error Display */}
          {currentRun.error && (
            <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
              <h3 className="font-medium text-destructive mb-2">Error</h3>
              <p className="text-sm text-destructive/80">{currentRun.error}</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
