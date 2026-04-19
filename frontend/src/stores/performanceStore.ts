import { create } from 'zustand';

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
}

export const usePerformanceStore = create<PerformanceStore>(() => ({
  accuracyData: [],
  topicData: [],
  weakAreas: [],
}));
