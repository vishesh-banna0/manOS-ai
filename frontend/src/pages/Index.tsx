import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { BookOpen, ArrowRight } from 'lucide-react';

export default function Index() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted/20">
      <div className="text-center space-y-6 max-w-md mx-auto px-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-foreground">Welcome to Manos AI</h1>
          <p className="text-muted-foreground">
            Your intelligent learning companion for mastering any subject through AI-powered flashcards and adaptive testing.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          <Button
            onClick={() => navigate('/')}
            className="gap-2"
            size="lg"
          >
            <BookOpen className="h-5 w-5" />
            Get Started
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
