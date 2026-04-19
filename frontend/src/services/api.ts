import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

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
};

export const generateFlashcards = async (instanceId: number | string) => {
  try {
    const response = await api.post(`/flashcards/generate/${instanceId}`);
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error));
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

export const reviewFlashcard = async (flashcardId: number | string, correct: boolean) => {
  try {
    const response = await api.post('/flashcards/review', null, {
      params: {
        flashcard_id: flashcardId,
        correct,
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(handleApiError(error));
  }
};

export const testsApi = {
  generate: (instanceId: string | number, count: number) => api.post(`/instances/${instanceId}/tests`, { count }),
  submit: (testId: string, answers: Record<string, string>) => api.post(`/tests/${testId}/submit`, { answers }),
};

export const analyticsApi = {
  get: (instanceId: string | number) => api.get(`/instances/${instanceId}/analytics`),
};

export default api;
