import { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Upload, FileText, CheckCircle2, X, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { documentsApi, generateFlashcards } from '@/services/api';

interface UploadedFile {
  id: string;
  name: string;
  size: string;
  status: 'uploading' | 'done' | 'error' | 'generating_flashcards';
  progress: number;
  error?: string;
  flashcardsGenerated?: boolean;
}

export default function UploadPage() {
  const { id: instanceId } = useParams();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(async (fileList: FileList) => {
    if (!instanceId) return;

    // Convert FileList to array and create upload entries
    const filesToUpload = Array.from(fileList);
    const newFiles: UploadedFile[] = filesToUpload.map((f, idx) => ({
      id: `${Date.now()}-${idx}`,
      name: f.name,
      size: `${(f.size / 1024).toFixed(1)} KB`,
      status: 'uploading' as const,
      progress: 0,
    }));
    setFiles((prev) => [...prev, ...newFiles]);

    // Upload each file
    filesToUpload.forEach(async (file, index) => {
      const fileEntry = newFiles[index];
      try {
        const response = await documentsApi.upload(instanceId, file);
        const warning = response.data?.warning as string | undefined;
        setFiles((prev) => prev.map((f) => f.id === fileEntry.id ? {
          ...f,
          progress: 100,
          status: 'done',
          error: warning,
        } : f));
      } catch (error) {
        console.error('Upload failed for', file.name, error);
        setFiles((prev) => prev.map((f) => f.id === fileEntry.id ? {
          ...f,
          status: 'error',
          error: error instanceof Error ? error.message : 'Network error - backend may not be running'
        } : f));
      }
    });
  }, [instanceId]);

  const handleGenerateFlashcards = useCallback(async (fileId: string) => {
    if (!instanceId) return;

    try {
      // Update status to show generation in progress
      setFiles((prev) => prev.map((f) =>
        f.id === fileId ? { ...f, status: 'generating_flashcards', progress: 50 } : f
      ));

      // Generate flashcards
      await generateFlashcards(instanceId);

      // Mark as completed
      setFiles((prev) => prev.map((f) =>
        f.id === fileId ? { ...f, status: 'done', progress: 100, flashcardsGenerated: true } : f
      ));
    } catch (error) {
      console.error('Flashcard generation failed:', error);
      setFiles((prev) => prev.map((f) =>
        f.id === fileId ? {
          ...f,
          status: 'error',
          error: error instanceof Error ? error.message : 'Flashcard generation failed'
        } : f
      ));
    }
  }, [instanceId]);

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Upload Documents</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Upload PDFs or text files to generate Q&A pairs</p>
      </div>

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
        <p className="text-xs text-muted-foreground mb-4">PDF, TXT, MD — up to 10MB</p>
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
                    <p className="text-xs text-muted-foreground mt-1">Uploading...</p>
                  </div>
                )}
                {file.status === 'generating_flashcards' && (
                  <div className="w-full bg-muted rounded-full h-1 mt-1.5">
                    <div className="bg-primary h-1 rounded-full transition-all" style={{ width: `${file.progress}%` }} />
                    <p className="text-xs text-muted-foreground mt-1">Generating flashcards...</p>
                  </div>
                )}
                {file.status === 'done' && file.flashcardsGenerated && (
                  <p className="text-xs text-success mt-1">Flashcards generated successfully!</p>
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
                  className="mr-2"
                >
                  Generate Flashcards
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
