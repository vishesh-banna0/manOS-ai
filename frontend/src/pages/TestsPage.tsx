import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { testsApi, type TestSession } from '@/services/api';

const SECONDS_PER_QUESTION = 30;

export default function TestsPage() {
  const { id: instanceId } = useParams();

  const [session, setSession] = useState<TestSession | null>(null);
  const [result, setResult] = useState<TestSession | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [current, setCurrent] = useState(0);
  const [timeLeft, setTimeLeft] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const questions = session?.questions ?? [];
  const finished = result !== null;

  const submit = useCallback(async () => {
    if (!session || finished) return;
    setLoading(true);
    setError(null);
    try {
      // Keys are question ids; the backend also accepts positions.
      const payload: Record<string, number> = {};
      Object.entries(answers).forEach(([position, choice]) => {
        const question = session.questions[Number(position)];
        if (question) payload[String(question.id)] = choice;
      });
      setResult(await testsApi.submit(session.id, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit the test.');
    } finally {
      setLoading(false);
    }
  }, [session, answers, finished]);

  // Countdown
  useEffect(() => {
    if (!session || finished) return;
    const timer = setInterval(() => {
      setTimeLeft((seconds) => {
        if (seconds <= 1) {
          clearInterval(timer);
          void submit();
          return 0;
        }
        return seconds - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [session, finished, submit]);

  const start = async () => {
    if (!instanceId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setAnswers({});
    setCurrent(0);
    try {
      const newSession = await testsApi.generate(instanceId, 10);
      setSession(newSession);
      setTimeLeft(newSession.questions.length * SECONDS_PER_QUESTION);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate a test.');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  // ----------------------------------------------------------------- start
  if (!session) {
    return (
      <div className="max-w-lg mx-auto text-center py-16 space-y-4">
        <h1 className="text-xl font-bold text-foreground">Adaptive Test</h1>
        <p className="text-sm text-muted-foreground">
          Questions are drawn from your flashcard bank and weighted toward topics you are
          getting wrong.
        </p>
        <Button onClick={start} size="lg" disabled={loading}>
          {loading ? 'Generating...' : 'Start Test'}
        </Button>
        {error && (
          <div className="flex items-center justify-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" /> {error}
          </div>
        )}
      </div>
    );
  }

  // --------------------------------------------------------------- results
  if (finished && result) {
    return (
      <div className="max-w-lg mx-auto space-y-6 animate-fade-in">
        <div className="text-center py-8">
          <div className="text-5xl font-bold text-foreground mb-2">{result.score ?? 0}%</div>
          <p className="text-muted-foreground">
            {result.correct_count ?? 0} of {result.questions.length} correct
          </p>
          <p className="text-xs text-muted-foreground mt-1">Strategy: {result.strategy}</p>
        </div>

        <div className="space-y-3">
          {result.questions.map((q) => (
            <div key={q.id} className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-start gap-2">
                {q.is_correct ? (
                  <CheckCircle2 className="h-4 w-4 text-success mt-0.5 shrink-0" />
                ) : (
                  <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                )}
                <div>
                  <p className="text-sm font-medium text-foreground">{q.question}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Your answer: {q.selected != null ? q.options[q.selected] : 'Skipped'} •
                    Correct: {q.correct != null ? q.options[q.correct] : '—'}
                  </p>
                  {q.topic && (
                    <span className="inline-block mt-2 px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground">
                      {q.topic}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        <Button
          onClick={() => {
            setSession(null);
            setResult(null);
          }}
          className="w-full"
        >
          Take Another Test
        </Button>
      </div>
    );
  }

  // ------------------------------------------------------------ in progress
  const question = questions[current];
  if (!question) return null;

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Question {current + 1} / {questions.length}
        </p>
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Clock className="h-3.5 w-3.5" /> {formatTime(timeLeft)}
        </div>
      </div>

      <div className="w-full bg-muted rounded-full h-1">
        <div
          className="bg-primary h-1 rounded-full transition-all"
          style={{ width: `${((current + 1) / questions.length) * 100}%` }}
        />
      </div>

      <div className="bg-card border border-border rounded-xl p-6">
        <p className="font-medium text-foreground mb-4">{question.question}</p>
        <div className="space-y-2">
          {question.options.map((option, index) => (
            <button
              key={index}
              onClick={() => setAnswers((a) => ({ ...a, [current]: index }))}
              className={cn(
                'w-full text-left px-4 py-3 rounded-lg border text-sm transition-colors',
                answers[current] === index
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border text-foreground hover:bg-muted',
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-1.5 justify-center">
        {questions.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrent(index)}
            className={cn(
              'w-2.5 h-2.5 rounded-full transition-colors',
              index === current
                ? 'bg-primary'
                : answers[index] !== undefined
                  ? 'bg-primary/40'
                  : 'bg-muted-foreground/30',
            )}
          />
        ))}
      </div>

      {error && (
        <div className="flex items-center justify-center gap-2 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" /> {error}
        </div>
      )}

      <div className="flex justify-between">
        <Button
          variant="ghost"
          onClick={() => setCurrent((c) => Math.max(0, c - 1))}
          disabled={current === 0}
        >
          Previous
        </Button>
        {current === questions.length - 1 ? (
          <Button onClick={submit} disabled={loading}>
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : 'Finish'}
          </Button>
        ) : (
          <Button onClick={() => setCurrent((c) => c + 1)}>Next</Button>
        )}
      </div>
    </div>
  );
}
