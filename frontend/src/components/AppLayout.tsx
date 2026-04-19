import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { AppSidebar } from '@/components/AppSidebar';
import { AppHeader } from '@/components/AppHeader';
import { instancesApi } from '@/services/api';
import { useInstanceStore } from '@/stores/instanceStore';

export function AppLayout() {
  const setInstances = useInstanceStore((state) => state.setInstances);
  const setError = useInstanceStore((state) => state.setError);

  useEffect(() => {
    const loadInstances = async () => {
      try {
        const response = await instancesApi.getAll();
        setInstances(response.data);
        setError(null);
      } catch (error) {
        console.error('Failed to load instances:', error);
        setError('Failed to load instances');
      }
    };

    loadInstances();
  }, [setError, setInstances]);

  return (
    <div className="flex min-h-screen w-full bg-background">
      <AppSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <AppHeader />
        <main className="flex-1 p-6 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
