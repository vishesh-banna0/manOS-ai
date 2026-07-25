import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { usePerformanceStore } from '@/stores/performanceStore';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, AlertTriangle, Target, Award, Layers, RefreshCw } from 'lucide-react';

export default function AnalyticsPage() {
  const { id: instanceId } = useParams();
  const { accuracyData, topicData, weakAreas, analytics, loading, error, loadAnalytics } =
    usePerformanceStore();

  useEffect(() => {
    if (instanceId) loadAnalytics(instanceId);
  }, [instanceId, loadAnalytics]);

  if (loading && !analytics) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center text-muted-foreground">
        <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-3" />
        <p className="text-sm">Loading analytics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center space-y-2">
        <AlertTriangle className="h-6 w-6 text-destructive mx-auto" />
        <p className="text-sm text-destructive">{error}</p>
        <p className="text-xs text-muted-foreground">Is the backend running on port 8000?</p>
      </div>
    );
  }

  const summary = analytics?.summary;
  const hasReviews = (summary?.total_reviews ?? 0) > 0;

  const bestTopic = [...topicData].sort((a, b) => b.accuracy - a.accuracy)[0];
  const avgAccuracy = summary?.avg_accuracy != null ? Math.round(summary.avg_accuracy * 100) : null;

  const stats = [
    {
      label: 'Avg Accuracy',
      value: avgAccuracy != null ? `${avgAccuracy}%` : '—',
      icon: Target,
      color: 'text-primary',
    },
    { label: 'Best Topic', value: bestTopic?.topic || '—', icon: Award, color: 'text-accent' },
    { label: 'Total Reviews', value: summary?.total_reviews ?? 0, icon: TrendingUp, color: 'text-success' },
    { label: 'Weak Areas', value: weakAreas.length, icon: AlertTriangle, color: 'text-warning' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">Analytics</h1>
        <button
          onClick={() => instanceId && loadAnalytics(instanceId)}
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1.5"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-4">
            <s.icon className={`h-4 w-4 ${s.color} mb-2`} />
            <p className="text-lg font-bold text-foreground truncate">{s.value}</p>
            <p className="text-xs text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>

      {!hasReviews && (
        <div className="bg-muted/40 border border-border rounded-xl p-5 text-center">
          <p className="text-sm text-foreground font-medium">No review history yet</p>
          <p className="text-xs text-muted-foreground mt-1">
            Review some flashcards — accuracy, topic breakdown and weak areas are all
            computed from your actual review log.
          </p>
        </div>
      )}

      {hasReviews && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Accuracy Over Time */}
          <div className="bg-card border border-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Accuracy Over Time</h2>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={accuracyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Line type="monotone" dataKey="accuracy" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3, fill: 'hsl(var(--primary))' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Topic Breakdown */}
          <div className="bg-card border border-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Topic Breakdown</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={topicData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="topic" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Bar dataKey="accuracy" fill="hsl(var(--accent))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Upcoming review load */}
      {analytics?.schedule?.upcoming?.some((d) => d.due > 0) && (
        <div className="bg-card border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Upcoming Review Load</h2>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={analytics.schedule.upcoming}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
              <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
              />
              <Bar dataKey="due" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground mt-3">
            Avg interval {analytics.schedule.avg_interval_days}d · avg ease{' '}
            {analytics.schedule.avg_ease_factor}
          </p>
        </div>
      )}

      {/* Deck coverage */}
      {analytics?.coverage && analytics.coverage.chunks_total > 0 && (
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Layers className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold text-foreground">Source Coverage</h2>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className="bg-primary h-2 rounded-full"
              style={{ width: `${Math.round(analytics.coverage.coverage_ratio * 100)}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {analytics.coverage.chunks_covered} of {analytics.coverage.chunks_total} source
            sections are covered by flashcards (
            {Math.round(analytics.coverage.coverage_ratio * 100)}%)
          </p>
        </div>
      )}

      {/* Weak Areas */}
      {weakAreas.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-warning" />
            <h2 className="text-sm font-semibold text-foreground">Areas to Improve</h2>
          </div>
          <div className="space-y-2">
            {topicData.filter((t) => weakAreas.includes(t.topic)).map((t) => (
              <div key={t.topic} className="flex items-center justify-between">
                <span className="text-sm text-foreground">{t.topic}</span>
                <div className="flex items-center gap-3">
                  <div className="w-24 bg-muted rounded-full h-1.5">
                    <div className="bg-warning h-1.5 rounded-full" style={{ width: `${t.accuracy}%` }} />
                  </div>
                  <span className="text-xs text-muted-foreground w-8">{t.accuracy}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
