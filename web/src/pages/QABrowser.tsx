import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CheckCircle,
  XCircle,
  ChevronRight,
  Filter,
  MessageSquare,
  BarChart3,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { listQARuns, getQAComparison, getQADomainAnalysis, listTestBanks } from '@/lib/api'
import { formatDate, formatDuration, getScoreColor } from '@/lib/utils'

export function QABrowser() {
  const [filters, setFilters] = useState({
    model_id: '',
    test_bank_id: '',
  })

  const { data: runsData, isLoading } = useQuery({
    queryKey: ['qa-runs', filters],
    queryFn: () => listQARuns({
      model_id: filters.model_id || undefined,
      test_bank_id: filters.test_bank_id || undefined,
      limit: 100,
    }),
  })

  const { data: comparison } = useQuery({
    queryKey: ['qa-comparison', filters.test_bank_id],
    queryFn: () => getQAComparison(filters.test_bank_id || undefined),
  })

  const { data: domainAnalysis } = useQuery({
    queryKey: ['qa-domains', filters],
    queryFn: () => getQADomainAnalysis({
      model_id: filters.model_id || undefined,
      test_bank_id: filters.test_bank_id || undefined,
    }),
  })

  const { data: testBanks } = useQuery({
    queryKey: ['test-banks'],
    queryFn: listTestBanks,
  })

  const comparisonChartData = comparison?.map((m) => ({
    name: m.model_id.split('/').pop() || m.model_id,
    accuracy: m.avg_accuracy,
    runs: m.run_count,
  })) || []

  const clearFilters = () => {
    setFilters({ model_id: '', test_bank_id: '' })
  }

  const hasFilters = filters.model_id || filters.test_bank_id

  // Get unique models from runs
  const uniqueModels = [...new Set(runsData?.runs.map((r) => r.model_id) || [])]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Q&A Tests</h1>
        <p className="text-muted-foreground">
          Browse Q&A benchmark results and model comparisons
        </p>
      </div>

      <Tabs defaultValue="runs">
        <TabsList>
          <TabsTrigger value="runs" className="gap-2">
            <MessageSquare className="h-4 w-4" />
            Runs
          </TabsTrigger>
          <TabsTrigger value="comparison" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Comparison
          </TabsTrigger>
        </TabsList>

        <TabsContent value="runs" className="space-y-6 mt-6">
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
                    value={filters.model_id || "__all__"}
                    onValueChange={(value) =>
                      setFilters((f) => ({ ...f, model_id: value === "__all__" ? "" : value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All Models" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">All Models</SelectItem>
                      {uniqueModels.map((model) => (
                        <SelectItem key={model} value={model}>
                          {model}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="w-48">
                  <Select
                    value={filters.test_bank_id || "__all__"}
                    onValueChange={(value) =>
                      setFilters((f) => ({ ...f, test_bank_id: value === "__all__" ? "" : value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All Test Banks" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">All Test Banks</SelectItem>
                      {testBanks?.banks.map((bank) => (
                        <SelectItem key={bank.id} value={bank.id}>
                          {bank.name}
                        </SelectItem>
                      ))}
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
                      to={`/qa/${run.run_id}`}
                      className="flex items-center justify-between p-4 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        {run.status === 'completed' ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-500" />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{run.model_id}</span>
                            <Badge variant="outline" className="text-xs">
                              {run.run_id}
                            </Badge>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {run.test_bank_name || run.test_bank_id}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <div className="font-mono">
                            {run.correct_answers}/{run.total_questions}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatDuration(run.duration_seconds)}
                          </div>
                        </div>

                        <div
                          className={`text-lg font-bold ${getScoreColor(run.accuracy / 100)}`}
                        >
                          {run.accuracy.toFixed(1)}%
                        </div>

                        <div className="text-sm text-muted-foreground">
                          {formatDate(run.started_at)}
                        </div>

                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                  <MessageSquare className="h-12 w-12 mb-4" />
                  <p>No Q&A runs found</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="comparison" className="space-y-6 mt-6">
          {/* Model Comparison Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Model Comparison</CardTitle>
              <CardDescription>Average accuracy by model</CardDescription>
            </CardHeader>
            <CardContent>
              {comparisonChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={comparisonChartData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="name" className="text-xs" />
                    <YAxis domain={[0, 100]} className="text-xs" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '0.5rem',
                      }}
                      formatter={(value: number) => [`${value.toFixed(1)}%`, 'Accuracy']}
                    />
                    <Bar
                      dataKey="accuracy"
                      fill="hsl(var(--primary))"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                  No comparison data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Model Stats Table */}
          <Card>
            <CardHeader>
              <CardTitle>Model Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              {comparison && comparison.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Model</th>
                        <th className="text-right p-2">Runs</th>
                        <th className="text-right p-2">Avg Accuracy</th>
                        <th className="text-right p-2">Best</th>
                        <th className="text-right p-2">Questions</th>
                        <th className="text-right p-2">Correct</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.map((m) => (
                        <tr key={m.model_id} className="border-b">
                          <td className="p-2 font-medium">{m.model_id}</td>
                          <td className="p-2 text-right">{m.run_count}</td>
                          <td
                            className={`p-2 text-right ${getScoreColor(m.avg_accuracy / 100)}`}
                          >
                            {m.avg_accuracy.toFixed(1)}%
                          </td>
                          <td className="p-2 text-right">{m.best_accuracy.toFixed(1)}%</td>
                          <td className="p-2 text-right">{m.total_questions}</td>
                          <td className="p-2 text-right">{m.total_correct}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-muted-foreground">No comparison data available</p>
              )}
            </CardContent>
          </Card>

          {/* Domain Analysis */}
          {domainAnalysis && domainAnalysis.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Performance by Domain</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Domain</th>
                        <th className="text-left p-2">Model</th>
                        <th className="text-right p-2">Questions</th>
                        <th className="text-right p-2">Correct</th>
                        <th className="text-right p-2">Accuracy</th>
                        <th className="text-right p-2">Avg Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {domainAnalysis.map((d, i) => (
                        <tr key={`${d.domain}-${d.model_id}-${i}`} className="border-b">
                          <td className="p-2 font-medium">{d.domain}</td>
                          <td className="p-2 text-muted-foreground">{d.model_id}</td>
                          <td className="p-2 text-right">{d.total_questions}</td>
                          <td className="p-2 text-right">{d.correct_answers}</td>
                          <td
                            className={`p-2 text-right ${getScoreColor(d.accuracy / 100)}`}
                          >
                            {d.accuracy.toFixed(1)}%
                          </td>
                          <td className="p-2 text-right">
                            {d.avg_response_time.toFixed(1)}s
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
