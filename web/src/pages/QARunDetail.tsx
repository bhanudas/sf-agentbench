import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { getQARun } from '@/lib/api'
import { formatDate, formatDuration, getScoreColor, cn } from '@/lib/utils'

export function QARunDetail() {
  const { runId } = useParams<{ runId: string }>()

  const { data: run, isLoading, error } = useQuery({
    queryKey: ['qa-run', runId],
    queryFn: () => getQARun(runId!),
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
        <p className="text-lg font-medium">Q&A Run not found</p>
        <Link to="/qa">
          <Button variant="link">Back to Q&A tests</Button>
        </Link>
      </div>
    )
  }

  // Group questions by correctness
  const correctQuestions = run.questions?.filter((q) => q.is_correct) || []
  const incorrectQuestions = run.questions?.filter((q) => !q.is_correct) || []

  // Group by domain
  const domainStats = run.questions?.reduce(
    (acc, q) => {
      if (!acc[q.domain]) {
        acc[q.domain] = { correct: 0, total: 0 }
      }
      acc[q.domain].total++
      if (q.is_correct) acc[q.domain].correct++
      return acc
    },
    {} as Record<string, { correct: number; total: number }>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/qa">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{run.model_id}</h1>
            <Badge
              variant={run.status === 'completed' ? 'success' : 'destructive'}
            >
              {run.status === 'completed' && <CheckCircle className="h-3 w-3 mr-1" />}
              {run.status === 'failed' && <XCircle className="h-3 w-3 mr-1" />}
              {run.status}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {run.test_bank_name || run.test_bank_id} · Run ID: {run.run_id}
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Accuracy
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold ${getScoreColor(run.accuracy / 100)}`}>
              {run.accuracy.toFixed(1)}%
            </div>
            <Progress value={run.accuracy} className="h-2 mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {run.correct_answers}/{run.total_questions}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {run.total_questions - run.correct_answers} incorrect
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Duration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {formatDuration(run.duration_seconds)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {(run.duration_seconds / run.total_questions).toFixed(1)}s per question
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Date
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-medium">{formatDate(run.started_at)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Domain Breakdown */}
      {domainStats && Object.keys(domainStats).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Performance by Domain</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(domainStats).map(([domain, stats]) => {
                const accuracy = (stats.correct / stats.total) * 100
                return (
                  <div key={domain} className="border rounded-lg p-3">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium">{domain}</span>
                      <span className={getScoreColor(accuracy / 100)}>
                        {accuracy.toFixed(0)}%
                      </span>
                    </div>
                    <Progress value={accuracy} className="h-1.5" />
                    <p className="text-xs text-muted-foreground mt-1">
                      {stats.correct}/{stats.total} correct
                    </p>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Questions List */}
      <Card>
        <CardHeader>
          <CardTitle>Questions ({run.questions?.length || 0})</CardTitle>
          <CardDescription>
            <span className="text-green-600">{correctQuestions.length} correct</span>
            {' · '}
            <span className="text-red-600">{incorrectQuestions.length} incorrect</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          {run.questions && run.questions.length > 0 ? (
            <div className="space-y-4">
              {run.questions.map((question, index) => (
                <div
                  key={question.question_id}
                  className={cn(
                    'border rounded-lg p-4',
                    question.is_correct
                      ? 'border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20'
                      : 'border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20'
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {question.is_correct ? (
                        <CheckCircle className="h-5 w-5 text-green-600" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-medium">
                          Question {index + 1}
                        </span>
                        <Badge variant="outline" className="text-xs">
                          {question.domain}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {question.difficulty}
                        </Badge>
                        <span className="text-xs text-muted-foreground ml-auto">
                          <Clock className="h-3 w-3 inline mr-1" />
                          {question.response_time.toFixed(1)}s
                        </span>
                      </div>

                      <p className="text-sm mb-3">{question.question_text}</p>

                      <div className="grid gap-2 text-sm">
                        <div className="flex gap-2">
                          <span className="text-muted-foreground w-20">Expected:</span>
                          <span className="font-medium text-green-600">
                            {question.correct_answer}
                          </span>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-muted-foreground w-20">Answer:</span>
                          <span
                            className={cn(
                              'font-medium',
                              question.is_correct ? 'text-green-600' : 'text-red-600'
                            )}
                          >
                            {question.extracted_answer || '(no answer)'}
                          </span>
                        </div>
                        {!question.is_correct && question.model_response && (
                          <div className="mt-2 p-2 bg-muted/50 rounded text-xs">
                            <span className="text-muted-foreground">Model response: </span>
                            <span className="break-words">
                              {question.model_response.slice(0, 200)}
                              {question.model_response.length > 200 && '...'}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-center py-8">
              No question data available
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
