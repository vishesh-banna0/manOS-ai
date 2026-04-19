import { Link, useParams } from 'react-router-dom';
import { useInstanceStore } from '@/stores/instanceStore';
import { AlertTriangle, ArrowRight, BarChart3, BookOpen, ClipboardList, Upload } from 'lucide-react';

export default function DashboardPage() {
  const { id } = useParams();
  const instanceId = Number(id);
  const instance = useInstanceStore((state) => state.instances.find((item) => item.id === instanceId));

  if (!instance) {
    return <div className="text-center text-muted-foreground py-16">Instance not found</div>;
  }

  const cards = [
    {
      label: 'Flashcards Due',
      value: instance.flashcards_due,
      icon: BookOpen,
      color: 'text-primary',
      link: `/instances/${id}/flashcards`,
    },
    {
      label: 'Last Test Score',
      value: instance.last_score !== null ? `${instance.last_score}%` : '-',
      icon: ClipboardList,
      color: 'text-accent',
      link: `/instances/${id}/tests`,
    },
    {
      label: 'Documents',
      value: instance.document_count,
      icon: Upload,
      color: 'text-warning',
      link: `/instances/${id}/upload`,
    },
  ];

  const weakAreas: string[] = [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">{instance.name}</h1>
        <p className="text-sm text-muted-foreground mt-0.5">{instance.description}</p>
      </div>

      {instance.flashcards_due > 0 && (
        <Link
          to={`/instances/${id}/flashcards`}
          className="flex items-center justify-between bg-primary/10 border border-primary/20 rounded-xl p-4 group card-hover"
        >
          <div>
            <p className="font-semibold text-foreground">Continue Learning</p>
            <p className="text-sm text-muted-foreground">{instance.flashcards_due} flashcards due for review</p>
          </div>
          <ArrowRight className="h-5 w-5 text-primary group-hover:translate-x-1 transition-transform" />
        </Link>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {cards.map((card) => (
          <Link key={card.label} to={card.link} className="bg-card border border-border rounded-xl p-5 card-hover">
            <card.icon className={`h-5 w-5 ${card.color} mb-3`} />
            <p className="text-2xl font-bold text-foreground">{card.value}</p>
            <p className="text-xs text-muted-foreground mt-1">{card.label}</p>
          </Link>
        ))}
      </div>

      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <h2 className="font-semibold text-foreground text-sm">Areas to Improve</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {weakAreas.map((area) => (
            <span key={area} className="px-3 py-1 rounded-full bg-warning/10 text-warning text-xs font-medium">
              {area}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Link to={`/instances/${id}/upload`} className="flex items-center gap-3 bg-card border border-border rounded-xl p-4 card-hover">
          <Upload className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Upload Document</span>
        </Link>
        <Link to={`/instances/${id}/analytics`} className="flex items-center gap-3 bg-card border border-border rounded-xl p-4 card-hover">
          <BarChart3 className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">View Analytics</span>
        </Link>
      </div>
    </div>
  );
}
