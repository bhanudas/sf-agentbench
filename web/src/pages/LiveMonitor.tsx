import { useParams, Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Pause,
  Play,
  Square,
  Terminal,
  Activity,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { useRunWebSocket } from '@/hooks/useWebSocket'
import { getRun } from '@/lib/api'
import { formatDuration, cn } from '@/lib/utils'

interface LogEntry {
  id: number
  timestamp: string
  level: string
  source: string
  message: string
}

export function LiveMonitor() {
  const { runId } = useParams<{ runId: string }>()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [progress, setProgress] = useState<number | null>(null)
  const [currentPhase, setCurrentPhase] = useState<string>('initializing')
  const logsEndRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
    refetchInterval: 5000,
  })

  const { isConnected, lastMessage, sendMessage } = useRunWebSocket(runId!, {
    onMessage: (event) => {
      if (event.type === 'event') {
        const data = event.data as Record<string, unknown>

        if (data.event_type === 'LogEvent') {
          setLogs((prev) => [
            ...prev.slice(-499),
            {
              id: data.id as number,
              timestamp: data.timestamp as string,
              level: (data.level as string) || 'info',
              source: (data.source as string) || 'system',
              message: (data.message as string) || '',
            },
          ])
        }

        if (data.event_type === 'StatusEvent') {
          setCurrentPhase((data.status as string) || currentPhase)
        }

        if (data.event_type === 'ProgressEvent') {
          const current = data.current as number
          const total = data.total as number
          if (total > 0) {
            setProgress((current / total) * 100)
          }
        }
      }
    },
  })

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const handlePause = () => {
    sendMessage({ command: 'pause' })
  }

  const handleResume = () => {
    sendMessage({ command: 'resume' })
  }

  const handleCancel = () => {
    if (confirm('Are you sure you want to cancel this run?')) {
      sendMessage({ command: 'cancel' })
    }
  }

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error':
        return 'text-red-500'
      case 'warning':
        return 'text-yellow-500'
      case 'info':
        return 'text-blue-500'
      case 'debug':
        return 'text-gray-500'
      default:
        return 'text-foreground'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to={`/runs/${runId}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Live Monitor</h1>
            <Badge variant={isConnected ? 'success' : 'destructive'}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {run?.task_name} · {run?.agent_id}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handlePause}>
            <Pause className="h-4 w-4 mr-1" />
            Pause
          </Button>
          <Button variant="outline" size="sm" onClick={handleResume}>
            <Play className="h-4 w-4 mr-1" />
            Resume
          </Button>
          <Button variant="destructive" size="sm" onClick={handleCancel}>
            <Square className="h-4 w-4 mr-1" />
            Cancel
          </Button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="secondary" className="text-lg">
              {run?.status || currentPhase}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Phase
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-medium capitalize">{currentPhase}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Duration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-medium">
              {formatDuration(run?.duration_seconds || 0)}
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
            {progress !== null ? (
              <div className="space-y-2">
                <Progress value={progress} className="h-2" />
                <div className="text-sm text-muted-foreground">
                  {progress.toFixed(0)}%
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground">-</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Log Stream */}
      <Card className="flex flex-col h-[500px]">
        <CardHeader className="flex flex-row items-center justify-between py-3">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4" />
            <CardTitle className="text-sm font-medium">Event Stream</CardTitle>
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
        <CardContent className="flex-1 overflow-auto p-0">
          <div className="font-mono text-xs">
            {logs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                <Activity className="h-6 w-6 mr-2 animate-pulse" />
                Waiting for events...
              </div>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="px-4 py-1 hover:bg-muted/50 border-b border-border/50"
                >
                  <span className="text-muted-foreground">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={cn('mx-2', getLevelColor(log.level))}>
                    [{log.level.toUpperCase()}]
                  </span>
                  <span className="text-muted-foreground">[{log.source}]</span>
                  <span className="ml-2">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
