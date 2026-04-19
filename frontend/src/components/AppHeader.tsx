import { useUIStore } from '@/stores/uiStore';
import { useInstanceStore } from '@/stores/instanceStore';
import { useParams } from 'react-router-dom';
import { Moon, Sun, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function AppHeader() {
  const { theme, toggleTheme, toggleSidebar } = useUIStore();
  const { instances, activeInstanceId } = useInstanceStore();
  const { id } = useParams();
  const routeInstanceId = id ? Number(id) : null;

  const currentInstance = instances.find((i) => i.id === (routeInstanceId ?? activeInstanceId));

  return (
    <header className="h-14 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-4 sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="md:hidden" onClick={toggleSidebar}>
          <Menu className="h-4 w-4" />
        </Button>
        {currentInstance && (
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: currentInstance.color }} />
            <h1 className="text-sm font-semibold text-foreground">{currentInstance.name}</h1>
          </div>
        )}
        {!currentInstance && <h1 className="text-sm font-semibold text-foreground">Manos AI</h1>}
      </div>
      <Button variant="ghost" size="icon" onClick={toggleTheme} className="text-muted-foreground hover:text-foreground">
        {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>
    </header>
  );
}
