import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useFlashcardStore } from '@/stores/flashcardStore';

export default function FlashcardsPage() {
  const params = useParams();
  const instanceId = params.id ?? '';
  const [showAnswer, setShowAnswer] = useState(false);

  const flashcards = useFlashcardStore((state) => state.flashcards);
  const currentIndex = useFlashcardStore((state) => state.currentIndex);
  const loading = useFlashcardStore((state) => state.loading);
  const error = useFlashcardStore((state) => state.error);
  const loadFlashcards = useFlashcardStore((state) => state.loadFlashcards);
  const generateFlashcards = useFlashcardStore((state) => state.generateFlashcards);
  const nextCard = useFlashcardStore((state) => state.nextCard);
  const prevCard = useFlashcardStore((state) => state.prevCard);
  const reviewCard = useFlashcardStore((state) => state.reviewCard);

  useEffect(() => {
    if (instanceId) {
      loadFlashcards(instanceId);
      setShowAnswer(false);
    }
  }, [instanceId, loadFlashcards]);

  const card = flashcards[currentIndex];
  const total = flashcards.length;
  const position = total > 0 ? currentIndex + 1 : 0;

  const handleNext = () => {
    setShowAnswer(false);
    nextCard();
  };

  const handlePrev = () => {
    setShowAnswer(false);
    prevCard();
  };

  const handleReview = async (correct: boolean) => {
    await reviewCard(instanceId, correct);
    setShowAnswer(false);
  };

  const handleGenerate = async () => {
    if (instanceId) {
      await generateFlashcards(instanceId);
      setShowAnswer(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Flashcards</h1>
          <p className="text-sm text-muted-foreground">{position} / {total}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => { loadFlashcards(instanceId); setShowAnswer(false); }}>
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      <div className="w-full bg-muted rounded-full h-1">
        <div
          className="bg-primary h-1 rounded-full transition-all duration-300"
          style={{ width: total ? `${(position / total) * 100}%` : '0%' }}
        />
      </div>

      {loading ? (
        <div className="rounded-2xl border border-border p-8 min-h-[280px] flex items-center justify-center">
          <p className="text-sm text-muted-foreground">Loading flashcards…</p>
        </div>
      ) : total === 0 ? (
        <div className="rounded-2xl border border-border p-8 min-h-[280px] flex flex-col items-center justify-center text-center gap-4">
          <p className="text-lg font-medium text-foreground">No flashcards available. Generate first.</p>
          <Button onClick={handleGenerate}>Generate Flashcards</Button>
        </div>
      ) : (
        <>
          <div
            onClick={() => setShowAnswer((prev) => !prev)}
            className="relative bg-card border border-border rounded-2xl p-8 min-h-[280px] flex items-center justify-center cursor-pointer card-hover select-none"
            style={{ perspective: '1000px' }}
          >
            <div className="text-center">
              <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wider">
                {showAnswer ? 'Answer' : 'Question'}
              </p>
              <p className="text-lg font-medium text-foreground leading-relaxed">
                {showAnswer ? card?.answer : card?.question}
              </p>
              {!showAnswer && (
                <p className="text-xs text-muted-foreground mt-4">Click to reveal answer</p>
              )}
            </div>
          </div>

          {showAnswer && (
            <div className="flex gap-3 animate-fade-in">
              <Button
                variant="outline"
                className="flex-1 border-destructive/30 text-destructive hover:bg-destructive/10"
                onClick={() => handleReview(false)}
              >
                Wrong
              </Button>
              <Button
                variant="outline"
                className="flex-1 border-success/30 text-success hover:bg-success/10"
                onClick={() => handleReview(true)}
              >
                Correct
              </Button>
            </div>
          )}

          <div className="flex justify-between">
            <Button variant="ghost" size="sm" onClick={handlePrev} disabled={currentIndex === 0}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Previous
            </Button>
            <Button variant="ghost" size="sm" onClick={handleNext} disabled={currentIndex >= total - 1}>
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>

          <p className="text-center text-xs text-muted-foreground">Press <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs">Space</kbd> to flip, <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs">→</kbd> next, <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs">←</kbd> previous</p>
        </>
      )}
    </div>
  );
}
