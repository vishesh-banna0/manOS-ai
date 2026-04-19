import { useInstanceStore, Instance } from '@/stores/instanceStore';
import { useNavigate } from 'react-router-dom';
import { Plus, BookOpen, BarChart3, ArrowRight, Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState, useEffect } from 'react';
import { instancesApi } from '@/services/api';

export default function HomePage() {
  const { instances, setInstances, addInstance, setActiveInstance, updateInstance, deleteInstance, loading, setLoading, error, setError } = useInstanceStore();
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editingInstance, setEditingInstance] = useState<Instance | null>(null);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  // Fetch instances on mount
  useEffect(() => {
    fetchInstances();
  }, []);

  const fetchInstances = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await instancesApi.getAll();
      setInstances(response.data);
    } catch (err) {
      setError('Failed to load instances');
      console.error('Failed to fetch instances:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    
    setLoading(true);
    try {
      const response = await instancesApi.create({
        name: name.trim(),
        description: desc.trim()
      });
      
      addInstance(response.data);
      setName('');
      setDesc('');
      setShowCreate(false);
    } catch (err) {
      setError('Failed to create instance');
      console.error('Failed to create instance:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (instance: Instance) => {
    setEditingInstance(instance);
    setName(instance.name);
    setDesc(instance.description);
    setShowEdit(true);
  };

  const handleUpdate = async () => {
    if (!editingInstance || !name.trim()) return;

    setLoading(true);
    try {
      await instancesApi.update(editingInstance.id, {
        name: name.trim(),
        description: desc.trim()
      });

      updateInstance(editingInstance.id, {
        name: name.trim(),
        description: desc.trim()
      });

      setName('');
      setDesc('');
      setShowEdit(false);
      setEditingInstance(null);
    } catch (err) {
      setError('Failed to update instance');
      console.error('Failed to update instance:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (instance: Instance) => {
    if (!confirm(`Are you sure you want to delete "${instance.name}"? This action cannot be undone.`)) {
      return;
    }

    setLoading(true);
    try {
      await instancesApi.delete(instance.id);
      deleteInstance(instance.id);
    } catch (err) {
      setError('Failed to delete instance');
      console.error('Failed to delete instance:', err);
    } finally {
      setLoading(false);
    }
  };

  const openInstance = (inst: Instance) => {
    setActiveInstance(inst.id);
    navigate(`/instances/${inst.id}`);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Your Instances</h1>
          <p className="text-muted-foreground text-sm mt-1">Select a workspace or create a new one</p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2" disabled={loading}>
          <Plus className="h-4 w-4" /> New Instance
        </Button>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {showCreate && (
        <div className="bg-card border border-border rounded-xl p-6 animate-scale-in space-y-4">
          <h2 className="font-semibold text-foreground">Create Instance</h2>
          <input
            value={name} onChange={(e) => setName(e.target.value)} placeholder="Instance name"
            className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            disabled={loading}
          />
          <textarea
            value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Description (optional)"
            className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            rows={2}
            disabled={loading}
          />
          <div className="flex gap-2">
            <Button onClick={handleCreate} disabled={loading}>
              {loading ? 'Creating...' : 'Create'}
            </Button>
            <Button variant="ghost" onClick={() => setShowCreate(false)} disabled={loading}>Cancel</Button>
          </div>
        </div>
      )}

      {showEdit && editingInstance && (
        <div className="bg-card border border-border rounded-xl p-6 animate-scale-in space-y-4">
          <h2 className="font-semibold text-foreground">Edit Instance</h2>
          <input
            value={name} onChange={(e) => setName(e.target.value)} placeholder="Instance name"
            className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            disabled={loading}
          />
          <textarea
            value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Description (optional)"
            className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            rows={2}
            disabled={loading}
          />
          <div className="flex gap-2">
            <Button onClick={handleUpdate} disabled={loading}>
              {loading ? 'Updating...' : 'Update'}
            </Button>
            <Button variant="ghost" onClick={() => { setShowEdit(false); setEditingInstance(null); setName(''); setDesc(''); }} disabled={loading}>Cancel</Button>
          </div>
        </div>
      )}

      {loading && instances.length === 0 ? (
        <div className="text-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading instances...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {instances.map((inst) => (
            <div
              key={inst.id}
              className="group bg-card border border-border rounded-xl p-5 text-left card-hover relative"
            >
              <div className="flex items-start justify-between mb-3">
                <span className="w-3 h-3 rounded-full mt-1" style={{ background: inst.color || '#8884d8' }} />
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => { e.stopPropagation(); handleEdit(inst); }}
                    className="h-6 w-6 p-0"
                  >
                    <Edit className="h-3 w-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => { e.stopPropagation(); handleDelete(inst); }}
                    className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
              <button onClick={() => openInstance(inst)} className="w-full text-left">
                <h3 className="font-semibold text-foreground mb-1">{inst.name}</h3>
                <p className="text-xs text-muted-foreground mb-4 line-clamp-2">{inst.description}</p>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><BookOpen className="h-3 w-3" />{inst.document_count} docs</span>
                  <span className="flex items-center gap-1"><BarChart3 className="h-3 w-3" />{inst.last_score !== null ? `${inst.last_score}%` : 'No tests'}</span>
                </div>
              </button>
            </div>
          ))}
        </div>
      )}

      {!loading && instances.length === 0 && (
        <div className="text-center py-16">
          <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-foreground mb-2">No instances yet</h2>
          <p className="text-muted-foreground text-sm mb-4">Create your first learning workspace to get started</p>
          <Button onClick={() => setShowCreate(true)}>Create Instance</Button>
        </div>
      )}
    </div>
  );
}
