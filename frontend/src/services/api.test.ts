import { afterEach, describe, expect, it, vi } from 'vitest';
import { AxiosError } from 'axios';
import api, { generateFlashcards } from './api';

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('flashcard jobs', () => {
  it('scopes generation to the chosen document and retries a transient poll failure', async () => {
    vi.useFakeTimers();
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { job_id: 'job1' } });
    const get = vi.spyOn(api, 'get')
      .mockRejectedValueOnce(new AxiosError('temporary network failure'))
      .mockResolvedValueOnce({ data: { status: 'completed', result: { cards_created: 3 } } });
    const completed = generateFlashcards(1, undefined, 4, 21);
    await vi.runAllTimersAsync();
    expect(await completed).toEqual({ cards_created: 3 });
    expect(post).toHaveBeenCalledWith('/flashcards/generate/1', null, {
      params: { max_topics: 4, document_id: 21 },
    });
    expect(post).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledTimes(2);
  });

  it('reports expired jobs without retrying or silently starting another generation', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: { job_id: 'expired' } });
    const get = vi.spyOn(api, 'get').mockRejectedValue({
      isAxiosError: true, response: { status: 404, data: { detail: 'Unknown job id' } },
    });
    await expect(generateFlashcards(1)).rejects.toThrow('Unknown job id');
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('does not turn a missing result into a successful zero-card run', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: { job_id: 'job1' } });
    vi.spyOn(api, 'get').mockResolvedValue({ data: { status: 'completed', result: null } });
    await expect(generateFlashcards(1)).rejects.toThrow('without a result');
  });
});
