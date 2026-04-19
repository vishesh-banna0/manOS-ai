import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

const questions = [
  // Questions will be loaded from the backend
];

export default function TestsPage() {
  const [started, setStarted] = useState(false);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [finished, setFinished] = useState(false);
  const [timeLeft, setTimeLeft] = useState(300);

  useEffect(() => {
    if (!started || finished) return;
    const t = setInterval(() => setTimeLeft((s) => { if (s <= 1) { setFinished(true); return 0; } return s - 1; }), 1000);
    return () => clearInterval(t);
  }, [started, finished]);

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
  const score = Object.entries(answers).filter(([i, a]) => a === questions[Number(i)].correct).length;

  if (!started) {
    return (
      <div className="max-w-lg mx-auto text-center py-16 space-y-4">
        <h1 className="text-xl font-bold text-foreground">Adaptive Test</h1>
        <p className="text-sm text-muted-foreground">{questions.length || 'No'} questions • 5 minutes</p>
        <Button onClick={() => setStarted(true)} size="lg" disabled={questions.length === 0}>Start Test</Button>
        <p className="text-xs text-muted-foreground">
          {questions.length === 0 ? 'Upload documents first to generate questions' : 'Start your first test to assess your knowledge'}
        </p>
      </div>
    );
  }

  if (finished) {
    return (
      <div className="max-w-lg mx-auto space-y-6 animate-fade-in">
        <div className="text-center py-8">
          <div className="text-5xl font-bold text-foreground mb-2">{questions.length > 0 ? Math.round((score / questions.length) * 100) : 0}%</div>
          <p className="text-muted-foreground">{score} of {questions.length} correct</p>
        </div>
        <div className="space-y-3">
          {questions.map((q, i) => (
            <div key={q.id} className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-start gap-2">
                {answers[i] === q.correct ? <CheckCircle2 className="h-4 w-4 text-success mt-0.5 shrink-0" /> : <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />}
                <div>
                  <p className="text-sm font-medium text-foreground">{q.question}</p>
                  <p className="text-xs text-muted-foreground mt-1">Your answer: {q.options[answers[i] ?? -1] || 'Skipped'} • Correct: {q.options[q.correct]}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
        <Button onClick={() => { setStarted(false); setFinished(false); setAnswers({}); setCurrent(0); setTimeLeft(300); }} className="w-full">
          Retake Test
        </Button>
      </div>
    );
  }

  const q = questions[current];
  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Question {current + 1} / {questions.length}</p>
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <Clock className="h-3.5 w-3.5" /> {formatTime(timeLeft)}
        </div>
      </div>

      <div className="w-full bg-muted rounded-full h-1">
        <div className="bg-primary h-1 rounded-full transition-all" style={{ width: `${questions.length > 0 ? ((current + 1) / questions.length) * 100 : 0}%` }} />
      </div>

      <div className="bg-card border border-border rounded-xl p-6">
        <p className="font-medium text-foreground mb-4">{q.question}</p>
        <div className="space-y-2">
          {q.options.map((opt, i) => (
            <button
              key={i}
              onClick={() => setAnswers((a) => ({ ...a, [current]: i }))}
              className={cn(
                'w-full text-left px-4 py-3 rounded-lg border text-sm transition-colors',
                answers[current] === i
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border text-foreground hover:bg-muted'
              )}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {/* Navigation dots */}
      <div className="flex gap-1.5 justify-center">
        {questions.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={cn(
              'w-2.5 h-2.5 rounded-full transition-colors',
              i === current ? 'bg-primary' : answers[i] !== undefined ? 'bg-primary/40' : 'bg-muted-foreground/30'
            )}
          />
        ))}
      </div>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={() => setCurrent((c) => Math.max(0, c - 1))} disabled={current === 0}>Previous</Button>
        {current === questions.length - 1 ? (
          <Button onClick={() => setFinished(true)}>Finish</Button>
        ) : (
          <Button onClick={() => setCurrent((c) => c + 1)}>Next</Button>
        )}
      </div>
    </div>
  );
}
