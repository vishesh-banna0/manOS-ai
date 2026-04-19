import { create } from 'zustand';
import { generateFlashcards as apiGenerateFlashcards, getFlashcards as apiGetFlashcards, reviewFlashcard as apiReviewFlashcard } from '@/services/api';

export interface FlashcardItem {
  id: number;
  question: string;
  answer: string;
  [key: string]: unknown;
}

interface FlashcardStore {
  flashcards: FlashcardItem[];
  currentIndex: number;
  loading: boolean;
  error: string | null;
  loadFlashcards: (instanceId: string) => Promise<void>;
  nextCard: () => void;
  prevCard: () => void;
  reviewCard: (instanceId: string, correct: boolean) => Promise<void>;
  generateFlashcards: (instanceId: string) => Promise<void>;
  resetFlashcards: () => void;
}

export const useFlashcardStore = create<FlashcardStore>((set, get) => ({
  flashcards: [],
  currentIndex: 0,
  loading: false,
  error: null,

  loadFlashcards: async (instanceId) => {
    set({ loading: true, error: null });
    try {
      const flashcards = await apiGetFlashcards(Number(instanceId));
      set({
        flashcards: Array.isArray(flashcards) ? flashcards : [],
        currentIndex: 0,
      });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Unable to load flashcards. Please try again.';
      set({ error: errorMessage });
    } finally {
      set({ loading: false });
    }
  },

  generateFlashcards: async (instanceId) => {
    set({ loading: true, error: null });
    try {
      await apiGenerateFlashcards(Number(instanceId));
      await get().loadFlashcards(instanceId);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Unable to generate flashcards. Please try again.';
      set({ error: errorMessage });
    } finally {
      set({ loading: false });
    }
  },

  nextCard: () => {
    set((state) => {
      const nextIndex = state.currentIndex + 1;
      return nextIndex < state.flashcards.length ? { currentIndex: nextIndex } : state;
    });
  },

  prevCard: () => {
    set((state) => ({ currentIndex: Math.max(0, state.currentIndex - 1) }));
  },

  reviewCard: async (instanceId, correct) => {
    const state = get();
    const card = state.flashcards[state.currentIndex];
    if (!card) return;

    set({ loading: true, error: null });
    try {
      await apiReviewFlashcard(card.id, correct);

      const remaining = state.flashcards.filter((_, index) => index !== state.currentIndex);
      const nextIndex = Math.min(state.currentIndex, remaining.length - 1);

      set({
        flashcards: remaining,
        currentIndex: nextIndex >= 0 ? nextIndex : 0,
      });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Unable to submit review. Please try again.';
      set({ error: errorMessage });
    } finally {
      set({ loading: false });
    }
  },

  resetFlashcards: () => set({ flashcards: [], currentIndex: 0, loading: false, error: null }),
}));

export default useFlashcardStore;
