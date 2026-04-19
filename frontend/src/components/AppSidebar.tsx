import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useInstanceStore } from '@/stores/instanceStore';
import { useUIStore } from '@/stores/uiStore';
import {
  LayoutDashboard, Upload, BookOpen, ClipboardList, BarChart3,
  ChevronLeft, ChevronRight, Brain, Home,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '' },
  { label: 'Upload', icon: Upload, path: '/upload' },
  { label: 'Flashcards', icon: BookOpen, path: '/flashcards' },
  { label: 'Tests', icon: ClipboardList, path: '/tests' },
  { label: 'Analytics', icon: BarChart3, path: '/analytics' },
];

export function AppSidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { instances, activeInstanceId, setActiveInstance } = useInstanceStore();
  const location = useLocation();
  const navigate = useNavigate();
  const { id } = useParams();

  return (
    <aside
      className={cn(
        'h-screen sticky top-0 flex flex-col border-r border-border bg-sidebar transition-all duration-300 z-30',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
{/* Logo */}
<div className="flex items-center gap-2 px-4 h-14 border-b border-border shrink-0">
  <img
    src="/favicon.ico"
    alt="Manos AI Logo"
    className="h-12 w-12 shrink-0"
  />
  {sidebarOpen && (
    <span className="font-bold text-lg text-foreground tracking-tight">
      Manos AI
    </span>
  )}
</div>

      {/* Home link */}
      <Link
        to="/"
        className={cn(
          'flex items-center gap-3 px-4 py-2.5 mx-2 mt-3 rounded-lg text-sm transition-colors',
          'text-sidebar-foreground hover:bg-sidebar-accent',
          !id && 'bg-sidebar-accent text-foreground font-medium'
        )}
      >
        <Home className="h-4 w-4 shrink-0" />
        {sidebarOpen && <span>All Instances</span>}
      </Link>

      {/* Instance selector */}
      {sidebarOpen && (
        <div className="px-4 mt-4 mb-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Instances</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {instances.map((inst) => (
              <button
                key={inst.id}
                onClick={() => {
                  setActiveInstance(inst.id);
                  navigate(`/instances/${inst.id}`);
                }}
                className={cn(
                  'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors text-left',
                  inst.id === activeInstanceId
                    ? 'bg-primary/10 text-primary font-medium'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent'
                )}
              >
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: inst.color }} />
                <span className="truncate">{inst.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Nav */}
      {id && (
        <nav className="flex-1 px-2 mt-4 space-y-0.5">
          {sidebarOpen && (
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 mb-2">Navigate</p>
          )}
          {navItems.map((item) => {
            const fullPath = `/instances/${id}${item.path}`;
            const isActive = location.pathname === fullPath;
            return (
              <Link
                key={item.label}
                to={fullPath}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground font-medium'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent'
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      )}

      <div className="mt-auto border-t border-border p-2">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center p-2 rounded-lg text-muted-foreground hover:bg-sidebar-accent transition-colors"
        >
          {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
