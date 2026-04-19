import { create } from 'zustand';

export interface Instance {
  id: number;
  name: string;
  description: string;
  document_count: number;
  flashcards_due: number;
  last_score: number | null;
  created_at: string;
  updated_at: string;
  color?: string;
}

interface InstanceStore {
  instances: Instance[];
  activeInstanceId: number | null;
  loading: boolean;
  error: string | null;
  setActiveInstance: (id: number) => void;
  addInstance: (instance: Instance) => void;
  updateInstance: (id: number, updates: Partial<Instance>) => void;
  deleteInstance: (id: number) => void;
  setInstances: (instances: Instance[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useInstanceStore = create<InstanceStore>((set, get) => ({
  instances: [],
  activeInstanceId: localStorage.getItem('activeInstanceId') ? parseInt(localStorage.getItem('activeInstanceId')!) : null,
  loading: false,
  error: null,
  
  setActiveInstance: (id) => {
    localStorage.setItem('activeInstanceId', id.toString());
    set({ activeInstanceId: id });
  },

  addInstance: (instance) => set((s) => ({ instances: [...s.instances, instance] })),

  updateInstance: (id, updates) => set((s) => ({
    instances: s.instances.map(inst => inst.id === id ? { ...inst, ...updates } : inst),
    activeInstanceId: s.activeInstanceId === id && updates.id ? updates.id : s.activeInstanceId
  })),

  deleteInstance: (id) => set((s) => {
    const newInstances = s.instances.filter(inst => inst.id !== id);
    const newActiveId = s.activeInstanceId === id ? (newInstances.length > 0 ? newInstances[0].id : null) : s.activeInstanceId;
    if (newActiveId) {
      localStorage.setItem('activeInstanceId', newActiveId.toString());
    } else {
      localStorage.removeItem('activeInstanceId');
    }
    return { instances: newInstances, activeInstanceId: newActiveId };
  }),

  setInstances: (instances) => set({ instances }),

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error }),
}));

