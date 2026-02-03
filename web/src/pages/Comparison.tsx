import { useQuery } from '@tanstack/react-query'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getAgentComparison, getRunSummary } from '@/lib/api'
import { formatScore, getScoreColor } from '@/lib/utils'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

export function Comparison() {
  const { data: comparison, isLoading } = useQuery({
    queryKey: ['comparison'],
    queryFn: getAgentComparison,
  })

  const { data: summary } = useQuery({
    queryKey: ['summary'],
    queryFn: getRunSummary,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  // Prepare data for radar chart
  const radarData = [
    { metric: 'Deployment', fullMark: 100 },
    { metric: 'Tests', fullMark: 100 },
    { metric: 'Static Analysis', fullMark: 100 },
    { metric: 'Metadata', fullMark: 100 },
    { metric: 'Rubric', fullMark: 100 },
  ].map((item) => {
    const dataPoint: Record<string, unknown> = { ...item }
    comparison?.forEach((agent) => {
      const shortName = agent.agent_id.split('/').pop() || agent.agent_id
      switch (item.metric) {
        case 'Deployment':
          dataPoint[shortName] = agent.avg_deployment * 100
          break
        case 'Tests':
          dataPoint[shortName] = agent.avg_tests * 100
          break
        case 'Static Analysis':
          dataPoint[shortName] = agent.avg_static_analysis * 100
          break
        case 'Metadata':
          dataPoint[shortName] = agent.avg_metadata * 100
          break
        case 'Rubric':
          dataPoint[shortName] = agent.avg_rubric * 100
          break
      }
    })
    return dataPoint
  })

  // Prepare data for bar chart
  const barChartData = comparison?.map((agent) => ({
    name: agent.agent_id.split('/').pop() || agent.agent_id,
    'Average Score': agent.average_score * 100,
    'Best Score': agent.best_score * 100,
  })) || []

  // Get agent short names for radar chart legend
  const agentNames = comparison?.map(
    (agent) => agent.agent_id.split('/').pop() || agent.agent_id
  ) || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Model Comparison</h1>
        <p className="text-muted-foreground">
          Compare performance across different AI agents
        </p>
      </div>

      {comparison && comparison.length > 0 ? (
        <>
          {/* Overview Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Agents Compared
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{comparison.length}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Runs
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{summary?.total_runs || 0}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Best Overall
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-bold">
                  {comparison[0]?.agent_id.split('/').pop() || '-'}
                </div>
                <p className={`text-sm ${getScoreColor(comparison[0]?.average_score || 0)}`}>
                  {formatScore(comparison[0]?.average_score || 0)} avg
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Tasks Covered
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {Object.keys(summary?.runs_by_task || {}).length}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Radar Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Multi-Dimensional Comparison</CardTitle>
                <CardDescription>
                  Performance across all evaluation layers
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="metric" className="text-xs" />
                    <PolarRadiusAxis domain={[0, 100]} />
                    {agentNames.map((name, index) => (
                      <Radar
                        key={name}
                        name={name}
                        dataKey={name}
                        stroke={COLORS[index % COLORS.length]}
                        fill={COLORS[index % COLORS.length]}
                        fillOpacity={0.2}
                      />
                    ))}
                    <Legend />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '0.5rem',
                      }}
                      formatter={(value: number) => `${value.toFixed(1)}%`}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Bar Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Score Comparison</CardTitle>
                <CardDescription>Average and best scores by agent</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={barChartData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="name" className="text-xs" />
                    <YAxis domain={[0, 100]} className="text-xs" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '0.5rem',
                      }}
                      formatter={(value: number) => `${value.toFixed(1)}%`}
                    />
                    <Legend />
                    <Bar
                      dataKey="Average Score"
                      fill="hsl(var(--primary))"
                      radius={[4, 4, 0, 0]}
                    />
                    <Bar
                      dataKey="Best Score"
                      fill="hsl(var(--primary) / 0.5)"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Table */}
          <Card>
            <CardHeader>
              <CardTitle>Detailed Comparison</CardTitle>
              <CardDescription>
                Score breakdown by evaluation layer
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-3">Agent</th>
                      <th className="text-right p-3">Runs</th>
                      <th className="text-right p-3">Avg Score</th>
                      <th className="text-right p-3">Best</th>
                      <th className="text-right p-3">Deploy</th>
                      <th className="text-right p-3">Tests</th>
                      <th className="text-right p-3">Static</th>
                      <th className="text-right p-3">Metadata</th>
                      <th className="text-right p-3">Rubric</th>
                      <th className="text-left p-3">Tasks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.map((agent, index) => (
                      <tr key={agent.agent_id} className="border-b hover:bg-muted/50">
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: COLORS[index % COLORS.length] }}
                            />
                            <span className="font-medium">
                              {agent.agent_id.split('/').pop() || agent.agent_id}
                            </span>
                          </div>
                        </td>
                        <td className="p-3 text-right">{agent.total_runs}</td>
                        <td
                          className={`p-3 text-right font-bold ${getScoreColor(agent.average_score)}`}
                        >
                          {formatScore(agent.average_score)}
                        </td>
                        <td className={`p-3 text-right ${getScoreColor(agent.best_score)}`}>
                          {formatScore(agent.best_score)}
                        </td>
                        <td className={`p-3 text-right ${getScoreColor(agent.avg_deployment)}`}>
                          {formatScore(agent.avg_deployment)}
                        </td>
                        <td className={`p-3 text-right ${getScoreColor(agent.avg_tests)}`}>
                          {formatScore(agent.avg_tests)}
                        </td>
                        <td
                          className={`p-3 text-right ${getScoreColor(agent.avg_static_analysis)}`}
                        >
                          {formatScore(agent.avg_static_analysis)}
                        </td>
                        <td className={`p-3 text-right ${getScoreColor(agent.avg_metadata)}`}>
                          {formatScore(agent.avg_metadata)}
                        </td>
                        <td className={`p-3 text-right ${getScoreColor(agent.avg_rubric)}`}>
                          {formatScore(agent.avg_rubric)}
                        </td>
                        <td className="p-3">
                          <div className="flex flex-wrap gap-1">
                            {agent.tasks_completed.slice(0, 3).map((task) => (
                              <Badge key={task} variant="outline" className="text-xs">
                                {task}
                              </Badge>
                            ))}
                            {agent.tasks_completed.length > 3 && (
                              <Badge variant="outline" className="text-xs">
                                +{agent.tasks_completed.length - 3}
                              </Badge>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64">
            <p className="text-muted-foreground mb-4">
              No comparison data available yet
            </p>
            <p className="text-sm text-muted-foreground">
              Run benchmarks with different agents to see comparisons here
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
