import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

// Agent runs make several local LLM calls and legitimately take minutes.
const AGENT_TIMEOUT_MS = 15 * 60 * 1000;

const handleApiError = (error: unknown) => {
  const maybeAxios = error as { response?: { data?: { detail?: string } }; message?: string };
  return (
    maybeAxios?.response?.data?.detail || maybeAxios?.message || 'Unexpected API error'
  );
};

export const instancesApi = {
  getAll: () => api.get('/instances'),
  get: (id: string | number) => api.get(`/instances/${id}`),
  create: (data: { name: string; description: string }) => api.post('/instances', data),
  update: (id: string | number, data: { name?: string; description?: string }) => api.put(`/instances/${id}`, data),
  delete: (id: string | number) => api.delete(`/instances/${id}`),
};

export const documentsApi = {
  upload: async (instanceId: string | number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    try {
      return await api.post(`/documents/upload/${instanceId}`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
  list: (instanceId: string | number) => api.get(`/documents/${instanceId}`),
  remove: (documentId: string | number) => api.delete(`/documents/${documentId}`),
};

export interface FlashcardAgentResult {
  cards_created: number;
  topics_planned: number;
  drafts: number;
  accepted: number;
  rejected: number;
  duplicates: number;
  repair_rounds: number;
  warnings: string[];
  message?: string;
}

export interface JobStatus {
  job_id: string;
  kind: string;
  status: 'running' | 'completed' | 'failed';
  stage: string;
  message: string;
  current: number;
  total: number;
  progress: number | null;
  counters: Record<string, number>;
  elapsed_seconds: number;
  result: FlashcardAgentResult | null;
  error: string | null;
}

/** Starts the authoring agent. Returns a job id to poll - the run takes minutes. */
export const startFlashcardGeneration = async (
  instanceId: number | string,
  maxTopics?: number,
): Promise<{ job_id: string }> => {
  try {
    const response = await api.post(`/flashcards/generate/${instanceId}`, null, {
      params: maxTopics ? { max_topics: maxTopics } : undefined,
    });
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error));
  }
};

export const getJob = async (jobId: string): Promise<JobStatus> => {
  try {
    const response = await api.get(`/jobs/${jobId}`);
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error));
  }
};

/**
 * Start generation and poll until it finishes, reporting progress as it goes.
 */
export const generateFlashcards = async (
  instanceId: number | string,
  onProgress?: (status: JobStatus) => void,
  maxTopics?: number,
): Promise<FlashcardAgentResult> => {
  const { job_id } = await startFlashcardGeneration(instanceId, maxTopics);

  // eslint-disable-next-line no-constant-condition
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 1500));

    const status = await getJob(job_id);
    onProgress?.(status);

    if (status.status === 'completed') {
      return status.result ?? ({ cards_created: 0 } as FlashcardAgentResult);
    }
    if (status.status === 'failed') {
      throw new Error(status.error || 'Flashcard generation failed.');
    }
  }
};

export const getFlashcards = async (instanceId: number | string) => {
  try {
    const response = await api.get(`/flashcards/${instanceId}`);
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error));
  }
};

export const reviewFlashcard = async (
  flashcardId: number | string,
  correct: boolean,
  responseMs?: number,
) => {
  try {
    // The endpoint takes a JSON body (it used to take query params).
    const response = await api.post('/flashcards/review', {
      flashcard_id: Number(flashcardId),
      correct,
      response_ms: responseMs,
    });
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error));
  }
};

export interface TestQuestion {
  id: number;
  position: number;
  question: string;
  options: string[];
  topic?: string | null;
  difficulty?: string | null;
  correct?: number;
  selected?: number | null;
  is_correct?: boolean | null;
}

export interface TestSession {
  id: number;
  instance_id: number;
  question_count: number;
  strategy: string;
  score: number | null;
  correct_count: number | null;
  questions: TestQuestion[];
}

export const testsApi = {
  generate: async (instanceId: string | number, count = 10): Promise<TestSession> => {
    try {
      const response = await api.post(`/instances/${instanceId}/tests`, { count });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
  submit: async (
    testId: number | string,
    answers: Record<string, number>,
  ): Promise<TestSession> => {
    try {
      const response = await api.post(`/tests/${testId}/submit`, { answers });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
  list: (instanceId: string | number) => api.get(`/instances/${instanceId}/tests`),
};

export interface AnalyticsResponse {
  instance_id: number;
  window_days: number;
  summary: {
    total_cards: number;
    due_now: number;
    mature_cards: number;
    total_reviews: number;
    correct_reviews: number;
    avg_accuracy: number | null;
    retention_rate: number | null;
  };
  accuracy_over_time: { date: string; reviews: number; accuracy: number }[];
  topic_performance: { topic: string; totalQuestions: number; correct: number; accuracy: number }[];
  weak_areas: string[];
  difficulty_breakdown: { difficulty: string; reviews: number; accuracy: number }[];
  schedule: {
    upcoming: { date: string; due: number }[];
    avg_interval_days: number;
    avg_ease_factor: number;
  };
  tests: { test_id: number; score: number; questions: number; completed_at: string | null }[];
  coverage: { chunks_total: number; chunks_covered: number; coverage_ratio: number };
}

export const analyticsApi = {
  get: async (instanceId: string | number, days = 30): Promise<AnalyticsResponse> => {
    try {
      const response = await api.get(`/instances/${instanceId}/analytics`, { params: { days } });
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
};

export interface SearchResult {
  chunk_id: number;
  title: string | null;
  document_name: string | null;
  page_start: number | null;
  page_end: number | null;
  score: number;
  snippet: string;
  text: string;
}

export const searchApi = {
  search: async (instanceId: string | number, query: string, k = 5) => {
    try {
      const response = await api.get(`/search/${instanceId}`, { params: { q: query, k } });
      return response.data as { query: string; count: number; results: SearchResult[] };
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
  answer: async (instanceId: string | number, question: string) => {
    try {
      const response = await api.post(
        `/search/${instanceId}/answer`,
        { question },
        { timeout: AGENT_TIMEOUT_MS },
      );
      return response.data as { question: string; answer: string | null; sources: SearchResult[]; warning?: string };
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
};

export interface Recommendation {
  title: string;
  detail: string;
  category: string;
  priority: number;
}

export const agentsApi = {
  revisionPlan: async (instanceId: string | number, applyActions = true) => {
    try {
      const response = await api.post(
        `/agents/revision-plan/${instanceId}`,
        { apply_actions: applyActions },
        { timeout: AGENT_TIMEOUT_MS },
      );
      return response.data;
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
  recommendations: async (instanceId: string | number, limit = 5) => {
    try {
      const response = await api.get(`/agents/recommendations/${instanceId}`, {
        params: { limit },
        timeout: AGENT_TIMEOUT_MS,
      });
      return response.data as { recommendations: Recommendation[]; warnings: string[] };
    } catch (error) {
      throw new Error(handleApiError(error));
    }
  },
};

export const ingestionApi = {
  status: (instanceId: string | number) => api.get(`/ingestion/status/${instanceId}`),
  health: () => api.get('/ingestion/status'),
  reindex: (instanceId: string | number) => api.post(`/ingestion/reindex/${instanceId}`),
};

export default api;
