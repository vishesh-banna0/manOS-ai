import { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Upload, FileText, CheckCircle2, X, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DeckSizeSelect } from '@/components/DeckSizeSelect';
import { documentsApi, generateFlashcards } from '@/services/api';

interface UploadedFile {
  id: string;
  name: string;
  size: string;
  status: 'uploading' | 'done' | 'error' | 'generating_flashcards';
  /** null while the total is unknown, which renders an indeterminate bar. */
  progress: number | null;
  error?: string;
  flashcardsGenerated?: boolean;
  documentId?: number;
  // Live agent progress
  stage?: string;
  cardsCreated?: number;
  elapsed?: number;
  topicsDone?: number;
  topicsTotal?: number;
}

const formatElapsed = (seconds: number) => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

// Keep in sync with MAX_UPLOAD_MB in backend/src/core/config.py
const MAX_UPLOAD_MB = 100;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.markdown', '.rst'];

const formatSize = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${(bytes / 1024).toFixed(1)} KB`;

/** Returns a user-facing reason the file cannot be uploaded, or undefined. */
const rejectionReason = (file: File): string | undefined => {
  if (file.size === 0) {
    return 'This file is empty (0 bytes). Check that it downloaded fully — if it is stored in OneDrive, open it once to sync it locally, then try again.';
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File is ${formatSize(file.size)} — the limit is ${MAX_UPLOAD_MB} MB.`;
  }
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return `Unsupported file type "${extension || 'unknown'}". Supported: ${ALLOWED_EXTENSIONS.join(', ')}.`;
  }
  return undefined;
};

export default function UploadPage() {
  const { id: instanceId } = useParams();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [maxTopics, setMaxTopics] = useState(4);
  const generating = files.some((file) => file.status === 'generating_flashcards');

  const handleFiles = useCallback(async (fileList: FileList) => {
    if (!instanceId) return;

    // Convert FileList to array and create upload entries
    const filesToUpload = Array.from(fileList);
    const newFiles: UploadedFile[] = filesToUpload.map((f, idx) => ({
      id: `${Date.now()}-${idx}`,
      name: f.name,
      size: formatSize(f.size),
      // Catch unusable files here so the user is not left waiting on a round
      // trip that can only fail. An empty file is usually an interrupted
      // download or a cloud placeholder that never synced.
      status: rejectionReason(f) ? ('error' as const) : ('uploading' as const),
      progress: 0,
      error: rejectionReason(f),
    }));
    setFiles((prev) => [...prev, ...newFiles]);

    // Index one file at a time so large PDFs do not compete for the local
    // embedding model and saturate the backend's worker threads.
    for (const [index, file] of filesToUpload.entries()) {
      const fileEntry = newFiles[index];
      if (fileEntry.error) continue;
      try {
        const response = await documentsApi.upload(instanceId, file);
        const warning = response.data?.warning as string | undefined;
        setFiles((prev) => prev.map((f) => f.id === fileEntry.id ? {
          ...f,
          progress: 100,
          status: 'done',
          error: warning,
          documentId: response.data.document.id,
        } : f));
      } catch (error) {
        console.error('Upload failed for', file.name, error);
        setFiles((prev) => prev.map((f) => f.id === fileEntry.id ? {
          ...f,
          status: 'error',
          error: error instanceof Error ? error.message : 'Network error - backend may not be running'
        } : f));
      }
    }
  }, [instanceId]);

  const handleGenerateFlashcards = useCallback(async (fileId: string) => {
    const file = files.find((entry) => entry.id === fileId);
    if (!instanceId || !file?.documentId || generating) return;

    const patch = (fields: Partial<UploadedFile>) =>
      setFiles((prev) => prev.map((f) => (f.id === fileId ? { ...f, ...fields } : f)));

    try {
      patch({
        status: 'generating_flashcards',
        progress: 0,
        stage: 'Starting the authoring agent...',
        cardsCreated: 0,
        elapsed: 0,
        error: undefined,
      });

      const result = await generateFlashcards(instanceId, (job) => {
        patch({
          // Before the planner returns there is no total, so show an
          // indeterminate bar rather than a misleading 0%.
          progress: job.progress != null ? Math.round(job.progress * 100) : null,
          stage: job.message || job.stage,
          cardsCreated: job.counters.cards_created ?? 0,
          elapsed: job.elapsed_seconds,
          topicsDone: job.current,
          topicsTotal: job.total,
        });
      }, maxTopics, file.documentId);

      patch({
        status: 'done',
        progress: 100,
        flashcardsGenerated: result.cards_created > 0,
        cardsCreated: result.cards_created,
        stage: undefined,
        error: result.warnings?.join(' ') || (result.cards_created === 0
          ? 'No new cards were created. The topics may already be covered; try a larger deck or check the AI connection.'
          : undefined),
      });
    } catch (error) {
      console.error('Flashcard generation failed:', error);
      patch({
        status: 'done',
        error: error instanceof Error ? error.message : 'Flashcard generation failed',
        stage: undefined,
      });
    }
  }, [instanceId, files, generating, maxTopics]);

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Upload Documents</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Upload PDFs or text files to create flashcards from each document.</p>
      </div>

      <DeckSizeSelect value={maxTopics} onChange={setMaxTopics} disabled={generating} />

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
          dragOver ? 'border-primary bg-primary/5' : 'border-border'
        }`}
      >
        <Upload className="h-10 w-10 text-muted-foreground mx-auto mb-4" />
        <p className="font-medium text-foreground mb-1">Drop files here or click to browse</p>
        <p className="text-xs text-muted-foreground mb-4">
          PDF, TXT, MD — up to {MAX_UPLOAD_MB}MB. PDFs must have a text layer (scans need OCR).
        </p>
        <Button variant="outline" onClick={() => {
          const input = document.createElement('input');
          input.type = 'file'; input.multiple = true; input.accept = '.pdf,.txt,.md';
          input.onchange = () => input.files && handleFiles(input.files);
          input.click();
        }}>
          Choose Files
        </Button>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((file) => (
            <div key={file.id} className="bg-card border border-border rounded-lg p-3 flex items-center gap-3">
              <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
                <p className="text-xs text-muted-foreground">{file.size}</p>
                {file.status === 'uploading' && (
                  <div className="w-full bg-muted rounded-full h-1 mt-1.5">
                    <div className="bg-primary h-1 rounded-full transition-all" style={{ width: `${file.progress}%` }} />
                    <p className="text-xs text-muted-foreground mt-1">Waiting, uploading or indexing…</p>
                  </div>
                )}
                {file.status === 'generating_flashcards' && (
                  <div className="mt-2 space-y-1.5">
                    <div className="w-full bg-muted rounded-full h-1 overflow-hidden">
                      {file.progress != null ? (
                        <div
                          className="bg-primary h-1 rounded-full transition-all duration-500"
                          style={{ width: `${file.progress}%` }}
                        />
                      ) : (
                        // Total unknown until the planner returns - an
                        // indeterminate bar is honest, 0% is not.
                        <div className="bg-primary/70 h-1 rounded-full w-1/3 animate-pulse" />
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 text-xs text-primary">
                      <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                      <span className="truncate">{file.stage || 'Working...'}</span>
                    </div>

                    <p className="text-xs text-muted-foreground">
                      {file.topicsTotal
                        ? `Topic ${file.topicsDone ?? 0}/${file.topicsTotal} · `
                        : ''}
                      {file.cardsCreated ?? 0} cards saved
                      {file.elapsed != null ? ` · ${formatElapsed(file.elapsed)} elapsed` : ''}
                    </p>

                    <p className="text-[11px] text-muted-foreground/70">
                      Cards are checked against your document and saved as
                      each topic finishes — you can leave this page.
                    </p>
                  </div>
                )}
                {file.status === 'done' && file.flashcardsGenerated && (
                  <p className="text-xs text-success mt-1">
                    {file.cardsCreated ?? 0} flashcards generated
                    {file.elapsed ? ` in ${formatElapsed(file.elapsed)}` : ''}
                  </p>
                )}
                {file.status === 'error' && file.error && (
                  <p className="text-xs text-destructive mt-1">{file.error}</p>
                )}
                {file.status === 'done' && file.error && (
                  <p className="text-xs text-warning mt-1">{file.error}</p>
                )}
              </div>
              {file.status === 'done' && !file.flashcardsGenerated && (
                <Button
                  size="sm"
                  onClick={() => handleGenerateFlashcards(file.id)}
                  disabled={generating || !file.documentId}
                  className="mr-2"
                >
                  {file.error ? 'Retry Generation' : 'Generate Flashcards'}
                </Button>
              )}
              {file.status === 'done' && file.flashcardsGenerated && (
                <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
              )}
              {file.status === 'error' && <AlertCircle className="h-4 w-4 text-destructive shrink-0" />}
              <button onClick={() => removeFile(file.id)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {files.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">Upload your first document to start learning</p>
        </div>
      )}
    </div>
  );
}
