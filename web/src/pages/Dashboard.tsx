import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  TrendingUp,
  PlayCircle,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getRunSummary, getAgentComparison, listRuns } from '@/lib/api'
import { formatScore, formatDate, getStatusColor, getScoreColor } from '@/lib/utils'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

export function Dashboard() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['summary'],
    queryFn: getRunSummary,
  })

  const { data: comparison } = useQuery({
    queryKey: ['comparison'],
    queryFn: getAgentComparison,
  })

  const { data: recentRuns } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: () => listRuns({ limit: 5 }),
  })

  const agentChartData = comparison?.map((agent) => ({
    name: agent.agent_id.split('/').pop() || agent.agent_id,
    score: agent.average_score * 100,
    runs: agent.total_runs,
  })) || []

  const statusData = summary ? [
    { name: 'Completed', value: summary.completed_runs, color: '#10b981' },
    { name: 'Failed', value: summary.failed_runs, color: '#ef4444' },
    { name: 'Pending', value: summary.total_runs - summary.completed_runs - summary.failed_runs, color: '#f59e0b' },
  ].filter(d => d.value > 0) : []

  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your benchmark runs and model performance
          </p>
        </div>
        <Link to="/launch">
          <Button className="gap-2">
            <PlayCircle className="h-4 w-4" />
            Launch Benchmark
          </Button>
        </Link>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.total_runs || 0}</div>
            <p className="text-xs text-muted-foreground">
              {summary?.last_run ? `Last run ${formatDate(summary.last_run)}` : 'No runs yet'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary && summary.total_runs > 0
                ? `${((summary.completed_runs / summary.total_runs) * 100).toFixed(1)}%`
                : '-'}
            </div>
            <p className="text-xs text-muted-foreground">
              {summary?.completed_runs || 0} completed, {summary?.failed_runs || 0} failed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Average Score</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getScoreColor(summary?.average_score || 0)}`}>
              {formatScore(summary?.average_score || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Best: {formatScore(summary?.best_score || 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Agents</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Object.keys(summary?.runs_by_agent || {}).length}
            </div>
            <p className="text-xs text-muted-foreground">
              {Object.keys(summary?.runs_by_task || {}).length} tasks benchmarked
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Agent Performance Chart */}
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Agent Performance</CardTitle>
            <CardDescription>Average score by agent</CardDescription>
          </CardHeader>
          <CardContent className="pl-2">
            {agentChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={agentChartData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="name" className="text-xs" />
                  <YAxis domain={[0, 100]} className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '0.5rem',
                    }}
                    formatter={(value: number) => [`${value.toFixed(1)}%`, 'Score']}
                  />
                  <Bar dataKey="score" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                No agent data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* Run Status Pie Chart */}
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Run Status</CardTitle>
            <CardDescription>Distribution of run outcomes</CardDescription>
          </CardHeader>
          <CardContent>
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                No runs yet
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Runs Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recent Runs</CardTitle>
            <CardDescription>Latest benchmark results</CardDescription>
          </div>
          <Link to="/runs">
            <Button variant="outline" size="sm">
              View All
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {recentRuns?.runs && recentRuns.runs.length > 0 ? (
            <div className="space-y-4">
              {recentRuns.runs.map((run) => (
                <Link
                  key={run.run_id}
                  to={`/runs/${run.run_id}`}
                  className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div>
                      {run.status === 'completed' ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : run.status === 'failed' ? (
                        <XCircle className="h-5 w-5 text-red-500" />
                      ) : (
                        <Clock className="h-5 w-5 text-yellow-500" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium">{run.task_name}</p>
                      <p className="text-sm text-muted-foreground">{run.agent_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <Badge variant={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'destructive' : 'secondary'}>
                      {run.status}
                    </Badge>
                    <span className={`font-mono font-bold ${getScoreColor(run.scores.final)}`}>
                      {formatScore(run.scores.final)}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {formatDate(run.started_at)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>No runs yet. Launch your first benchmark!</p>
              <Link to="/launch">
                <Button className="mt-4" variant="outline">
                  Launch Benchmark
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
