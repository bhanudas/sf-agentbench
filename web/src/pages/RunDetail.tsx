import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Clock,
  Monitor,
  FileCode,
  AlertTriangle,
} from 'lucide-react'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getRun } from '@/lib/api'
import { formatScore, formatDate, formatDuration, getScoreColor } from '@/lib/utils'

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>()

  const { data: run, isLoading, error } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
        <p className="text-lg font-medium">Run not found</p>
        <Link to="/runs">
          <Button variant="link">Back to runs</Button>
        </Link>
      </div>
    )
  }

  const radarData = [
    { subject: 'Deployment', score: run.scores.deployment * 100, fullMark: 100 },
    { subject: 'Tests', score: run.scores.tests * 100, fullMark: 100 },
    { subject: 'Static Analysis', score: run.scores.static_analysis * 100, fullMark: 100 },
    { subject: 'Metadata', score: run.scores.metadata * 100, fullMark: 100 },
    { subject: 'Rubric', score: run.scores.rubric * 100, fullMark: 100 },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/runs">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{run.task_name}</h1>
            <Badge
              variant={
                run.status === 'completed'
                  ? 'success'
                  : run.status === 'failed'
                    ? 'destructive'
                    : 'secondary'
              }
            >
              {run.status === 'completed' && <CheckCircle className="h-3 w-3 mr-1" />}
              {run.status === 'failed' && <XCircle className="h-3 w-3 mr-1" />}
              {run.status === 'running' && <Clock className="h-3 w-3 mr-1 animate-pulse" />}
              {run.status}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {run.agent_id} · Run ID: {run.run_id}
          </p>
        </div>
        {run.status === 'running' && (
          <Link to={`/runs/${runId}/live`}>
            <Button variant="outline" className="gap-2">
              <Monitor className="h-4 w-4" />
              Live Monitor
            </Button>
          </Link>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Final Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold ${getScoreColor(run.scores.final)}`}>
              {formatScore(run.scores.final)}
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
            <div className="text-3xl font-bold">{formatDuration(run.duration_seconds)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Started
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-medium">{formatDate(run.started_at)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Scratch Org
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm font-mono truncate">
              {run.scratch_org_username || '-'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Score Breakdown */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Score Breakdown</CardTitle>
            <CardDescription>5-layer evaluation results</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" className="text-xs" />
                  <PolarRadiusAxis domain={[0, 100]} />
                  <Radar
                    name="Score"
                    dataKey="score"
                    stroke="hsl(var(--primary))"
                    fill="hsl(var(--primary))"
                    fillOpacity={0.3}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-3">
              {[
                { label: 'Deployment', score: run.scores.deployment, weight: '20%' },
                { label: 'Tests', score: run.scores.tests, weight: '40%' },
                { label: 'Static Analysis', score: run.scores.static_analysis, weight: '10%' },
                { label: 'Metadata', score: run.scores.metadata, weight: '15%' },
                { label: 'Rubric', score: run.scores.rubric, weight: '15%' },
              ].map((item) => (
                <div key={item.label} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span>{item.label}</span>
                    <span className={getScoreColor(item.score)}>
                      {formatScore(item.score)}
                    </span>
                  </div>
                  <Progress value={item.score * 100} className="h-2" />
                  <div className="text-xs text-muted-foreground">Weight: {item.weight}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Details Tabs */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="evaluation">
              <TabsList>
                <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
                <TabsTrigger value="output">Agent Output</TabsTrigger>
                <TabsTrigger value="raw">Raw JSON</TabsTrigger>
              </TabsList>

              <TabsContent value="evaluation" className="mt-4">
                {run.evaluation ? (
                  <div className="space-y-4">
                    {/* Deployment Result */}
                    {run.evaluation.deployment && (
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Deployment</h4>
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Status: </span>
                            <Badge
                              variant={
                                run.evaluation.deployment.status === 'success'
                                  ? 'success'
                                  : 'destructive'
                              }
                            >
                              {run.evaluation.deployment.status}
                            </Badge>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Deployed: </span>
                            {run.evaluation.deployment.deployed_count}
                          </div>
                          <div>
                            <span className="text-muted-foreground">Failed: </span>
                            {run.evaluation.deployment.failed_count}
                          </div>
                        </div>
                        {run.evaluation.deployment.errors?.length > 0 && (
                          <div className="mt-2">
                            <p className="text-sm text-destructive">
                              {run.evaluation.deployment.errors.length} deployment errors
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Test Result */}
                    {run.evaluation.apex_tests && (
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Apex Tests</h4>
                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Total: </span>
                            {run.evaluation.apex_tests.total_tests}
                          </div>
                          <div>
                            <span className="text-green-600">Passed: </span>
                            {run.evaluation.apex_tests.passed}
                          </div>
                          <div>
                            <span className="text-red-600">Failed: </span>
                            {run.evaluation.apex_tests.failed}
                          </div>
                          <div>
                            <span className="text-muted-foreground">Coverage: </span>
                            {run.evaluation.apex_tests.code_coverage?.toFixed(1)}%
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Static Analysis */}
                    {run.evaluation.static_analysis && (
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Static Analysis</h4>
                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Total: </span>
                            {run.evaluation.static_analysis.total_violations}
                          </div>
                          <div>
                            <span className="text-red-600">Critical: </span>
                            {run.evaluation.static_analysis.critical_count}
                          </div>
                          <div>
                            <span className="text-orange-600">High: </span>
                            {run.evaluation.static_analysis.high_count}
                          </div>
                          <div>
                            <span className="text-yellow-600">Medium: </span>
                            {run.evaluation.static_analysis.medium_count}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Rubric */}
                    {run.evaluation.rubric && (
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Rubric Evaluation</h4>
                        <p className="text-sm text-muted-foreground mb-2">
                          {run.evaluation.rubric.feedback}
                        </p>
                        {run.evaluation.rubric.criteria?.map((criterion, i) => (
                          <div key={i} className="flex justify-between text-sm py-1 border-t">
                            <span>{criterion.name}</span>
                            <span className={getScoreColor(criterion.score)}>
                              {formatScore(criterion.score)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">No evaluation data available</p>
                )}
              </TabsContent>

              <TabsContent value="output" className="mt-4">
                <pre className="bg-muted p-4 rounded-lg overflow-auto max-h-[500px] text-sm font-mono">
                  {run.agent_output || 'No agent output captured'}
                </pre>
              </TabsContent>

              <TabsContent value="raw" className="mt-4">
                <pre className="bg-muted p-4 rounded-lg overflow-auto max-h-[500px] text-sm font-mono">
                  {JSON.stringify(run, null, 2)}
                </pre>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
