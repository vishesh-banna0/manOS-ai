import { create } from 'zustand';

type Theme = 'light' | 'dark';

interface UIStore {
  sidebarOpen: boolean;
  theme: Theme;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

const getInitialTheme = (): Theme => {
  const stored = localStorage.getItem('manos-theme') as Theme | null;
  return stored || 'dark';
};

export const useUIStore = create<UIStore>((set) => {
  const initial = getInitialTheme();
  document.documentElement.classList.toggle('dark', initial === 'dark');
  return {
    sidebarOpen: true,
    theme: initial,
    toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    setSidebarOpen: (open) => set({ sidebarOpen: open }),
    toggleTheme: () => set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('manos-theme', next);
      document.documentElement.classList.toggle('dark', next === 'dark');
      return { theme: next };
    }),
    setTheme: (t) => {
      localStorage.setItem('manos-theme', t);
      document.documentElement.classList.toggle('dark', t === 'dark');
      set({ theme: t });
    },
  };
});
