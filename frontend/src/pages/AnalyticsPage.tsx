import { usePerformanceStore } from '@/stores/performanceStore';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, AlertTriangle, Target, Award } from 'lucide-react';

export default function AnalyticsPage() {
  const { accuracyData, topicData, weakAreas } = usePerformanceStore();

  const avgAccuracy = Math.round(accuracyData.reduce((s, d) => s + d.accuracy, 0) / accuracyData.length);
  const bestTopic = [...topicData].sort((a, b) => b.accuracy - a.accuracy)[0];
  const totalQuestions = topicData.reduce((s, d) => s + d.totalQuestions, 0);

  const stats = [
    { label: 'Avg Accuracy', value: `${avgAccuracy}%`, icon: Target, color: 'text-primary' },
    { label: 'Best Topic', value: bestTopic?.topic || '—', icon: Award, color: 'text-accent' },
    { label: 'Total Questions', value: totalQuestions, icon: TrendingUp, color: 'text-success' },
    { label: 'Weak Areas', value: weakAreas.length, icon: AlertTriangle, color: 'text-warning' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-foreground">Analytics</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-4">
            <s.icon className={`h-4 w-4 ${s.color} mb-2`} />
            <p className="text-lg font-bold text-foreground">{s.value}</p>
            <p className="text-xs text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>

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

      {/* Weak Areas */}
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
    </div>
  );
}
