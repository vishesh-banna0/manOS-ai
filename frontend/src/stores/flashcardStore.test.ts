import { afterEach, expect, it, vi } from 'vitest';
import { useFlashcardStore } from './flashcardStore';
import { generateFlashcards, getFlashcards } from '@/services/api';

vi.mock('@/services/api', () => ({
  generateFlashcards: vi.fn(), getFlashcards: vi.fn(), reviewFlashcard: vi.fn(),
}));

afterEach(() => {
  useFlashcardStore.getState().resetFlashcards();
  vi.clearAllMocks();
});

it('uses the requested deck size and surfaces no-card warnings after refreshing', async () => {
  vi.mocked(generateFlashcards).mockResolvedValue({ cards_created: 0, warnings: ['Provider unavailable'] } as never);
  vi.mocked(getFlashcards).mockResolvedValue([]);
  await useFlashcardStore.getState().generateFlashcards('1', 8);
  expect(generateFlashcards).toHaveBeenCalledWith(1, expect.any(Function), 8);
  expect(useFlashcardStore.getState().error).toBe('Provider unavailable');
  expect(useFlashcardStore.getState().loading).toBe(false);
});

it('prevents repeat generation clicks while an existing run is active', async () => {
  let finish!: (result: never) => void;
  vi.mocked(generateFlashcards).mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  vi.mocked(getFlashcards).mockResolvedValue([]);
  const first = useFlashcardStore.getState().generateFlashcards('1');
  await useFlashcardStore.getState().generateFlashcards('1');
  expect(generateFlashcards).toHaveBeenCalledTimes(1);
  finish({ cards_created: 1, warnings: [] } as never);
  await first;
  expect(useFlashcardStore.getState().generationStatus).toBeNull();
});
