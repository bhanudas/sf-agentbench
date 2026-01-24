import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CheckCircle,
  XCircle,
  Clock,
  ChevronRight,
  Filter,
  Search,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { listRuns, listTasks, listAgents } from '@/lib/api'
import { formatScore, formatDate, formatDuration, getScoreColor, getTierColor } from '@/lib/utils'

export function RunBrowser() {
  const [filters, setFilters] = useState({
    task_id: '',
    agent_id: '',
    status: '',
  })

  const { data: runsData, isLoading } = useQuery({
    queryKey: ['runs', filters],
    queryFn: () => listRuns({
      task_id: filters.task_id || undefined,
      agent_id: filters.agent_id || undefined,
      status: filters.status || undefined,
      limit: 100,
    }),
  })

  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => listTasks(),
  })

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: listAgents,
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'running':
        return <Clock className="h-4 w-4 text-blue-500 animate-pulse" />
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />
    }
  }

  const clearFilters = () => {
    setFilters({ task_id: '', agent_id: '', status: '' })
  }

  const hasFilters = filters.task_id || filters.agent_id || filters.status

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Run Browser</h1>
          <p className="text-muted-foreground">
            Browse and inspect benchmark run results
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </CardTitle>
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear All
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="w-48">
              <Select
                value={filters.task_id || "__all__"}
                onValueChange={(value) => setFilters((f) => ({ ...f, task_id: value === "__all__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All Tasks" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Tasks</SelectItem>
                  {tasksData?.tasks.map((task) => (
                    <SelectItem key={task.id} value={task.id}>
                      {task.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-48">
              <Select
                value={filters.agent_id || "__all__"}
                onValueChange={(value) => setFilters((f) => ({ ...f, agent_id: value === "__all__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All Agents" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Agents</SelectItem>
                  {agentsData?.agents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-48">
              <Select
                value={filters.status || "__all__"}
                onValueChange={(value) => setFilters((f) => ({ ...f, status: value === "__all__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Statuses</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="running">Running</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : runsData?.runs && runsData.runs.length > 0 ? (
            <div className="divide-y">
              {runsData.runs.map((run) => (
                <Link
                  key={run.run_id}
                  to={`/runs/${run.run_id}`}
                  className="flex items-center justify-between p-4 hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {getStatusIcon(run.status)}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{run.task_name}</span>
                        <Badge variant="outline" className="text-xs">
                          {run.run_id}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{run.agent_id}</span>
                        <span>·</span>
                        <span>{formatDuration(run.duration_seconds)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Score Breakdown */}
                    <div className="hidden md:flex items-center gap-4 text-xs">
                      <div className="text-center">
                        <div className={getScoreColor(run.scores.deployment)}>
                          {formatScore(run.scores.deployment)}
                        </div>
                        <div className="text-muted-foreground">Deploy</div>
                      </div>
                      <div className="text-center">
                        <div className={getScoreColor(run.scores.tests)}>
                          {formatScore(run.scores.tests)}
                        </div>
                        <div className="text-muted-foreground">Tests</div>
                      </div>
                      <div className="text-center">
                        <div className={getScoreColor(run.scores.rubric)}>
                          {formatScore(run.scores.rubric)}
                        </div>
                        <div className="text-muted-foreground">Rubric</div>
                      </div>
                    </div>

                    {/* Final Score */}
                    <div className="text-right">
                      <div className={`text-lg font-bold ${getScoreColor(run.scores.final)}`}>
                        {formatScore(run.scores.final)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatDate(run.started_at)}
                      </div>
                    </div>

                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
              <Search className="h-12 w-12 mb-4" />
              <p>No runs found</p>
              {hasFilters && (
                <Button variant="link" onClick={clearFilters}>
                  Clear filters
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination info */}
      {runsData && (
        <div className="text-sm text-muted-foreground text-center">
          Showing {runsData.runs.length} of {runsData.total} runs
        </div>
      )}
    </div>
  )
}
