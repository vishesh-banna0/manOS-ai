import { create } from 'zustand';
import { analyticsApi, type AnalyticsResponse } from '@/services/api';

export interface TopicPerformance {
  topic: string;
  accuracy: number;
  totalQuestions: number;
}

export interface AccuracyPoint {
  date: string;
  accuracy: number;
}

interface PerformanceStore {
  accuracyData: AccuracyPoint[];
  topicData: TopicPerformance[];
  weakAreas: string[];
  analytics: AnalyticsResponse | null;
  loading: boolean;
  error: string | null;
  loadAnalytics: (instanceId: string | number, days?: number) => Promise<void>;
  reset: () => void;
}

const emptyState = {
  accuracyData: [] as AccuracyPoint[],
  topicData: [] as TopicPerformance[],
  weakAreas: [] as string[],
  analytics: null,
  loading: false,
  error: null,
};

export const usePerformanceStore = create<PerformanceStore>((set) => ({
  ...emptyState,

  loadAnalytics: async (instanceId, days = 30) => {
    set({ loading: true, error: null });
    try {
      const analytics = await analyticsApi.get(instanceId, days);
      set({
        analytics,
        accuracyData: analytics.accuracy_over_time.map((point) => ({
          date: point.date,
          accuracy: point.accuracy,
        })),
        topicData: analytics.topic_performance.map((topic) => ({
          topic: topic.topic,
          accuracy: topic.accuracy,
          totalQuestions: topic.totalQuestions,
        })),
        weakAreas: analytics.weak_areas,
      });
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : 'Unable to load analytics.' });
    } finally {
      set({ loading: false });
    }
  },

  reset: () => set({ ...emptyState }),
}));

export default usePerformanceStore;
