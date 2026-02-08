import { useState, useRef } from 'react';
import type { Document } from '@/types';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Upload, FileText, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';

interface DocumentSidebarProps {
  documents: Document[];
  activeDocumentId: string | null;
  sessionId: string;
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'reconnecting';
  apiUrl: string;
  onDocumentUploaded: (doc: Document) => void;
  onDocumentSelect: (id: string) => void;
  onConnect: () => void;
  onError: (message: string) => void;
}

export default function DocumentSidebar({
  documents,
  activeDocumentId,
  sessionId,
  connectionStatus,
  apiUrl,
  onDocumentUploaded,
  onDocumentSelect,
  onError,
}: DocumentSidebarProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [uploadPercent, setUploadPercent] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Wait for WebSocket connection and session_id
  const waitForConnection = (): Promise<void> => {
    return new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        if (sessionId) {
          clearInterval(checkInterval);
          resolve();
        }
      }, 100); // Check every 100ms
      
      // Timeout after 10 seconds
      setTimeout(() => {
        clearInterval(checkInterval);
        if (!sessionId) {
          onError('Connection timeout. Please try again.');
        }
        resolve();
      }, 10000);
    });
  };

  const handleFileSelect = async (file: File) => {
    // Wait for connection if still connecting
    if (connectionStatus === 'connecting') {
      setUploadProgress('Waiting for connection...');
      setUploadPercent(0);
      await waitForConnection();
    }
    
    if (!sessionId) {
      setUploadProgress('');
      setUploadPercent(0);
      onError('Connection failed. Please refresh the page.');
      return;
    }
    
    // Validate file type
    const validExtensions = ['.pdf', '.txt', '.md'];
    const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!validExtensions.includes(extension)) {
      onError('Unsupported file format. Please upload PDF, TXT, or MD files.');
      return;
    }

    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      onError('File too large. Maximum size is 10MB.');
      return;
    }

    setUploading(true);
    setUploadProgress('Uploading file...');
    setUploadPercent(0);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', sessionId);
      formData.append('chunk_size', '500');
      formData.append('chunk_overlap', '50');

      // Use XMLHttpRequest for real upload progress tracking
      const result = await new Promise<any>((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            // Upload phase is 0-20% of total progress
            const uploadPct = Math.round((e.loaded / e.total) * 20);
            setUploadPercent(uploadPct);
            setUploadProgress('Uploading file...');
          }
        });

        xhr.upload.addEventListener('loadend', () => {
          // Upload complete, now backend is processing
          setUploadPercent(20);
          setUploadProgress('Parsing document...');

          // Simulate incremental progress during backend processing
          const stages = [
            { label: 'Parsing document...', target: 35, delay: 800 },
            { label: 'Chunking text...', target: 50, delay: 1500 },
            { label: 'Generating embeddings...', target: 70, delay: 3000 },
            { label: 'Indexing to vector store...', target: 85, delay: 5000 },
          ];

          stages.forEach(({ label, target, delay }) => {
            setTimeout(() => {
              // Only update if still uploading (response hasn't arrived yet)
              setUploadPercent((prev) => {
                if (prev < 90) {
                  setUploadProgress(label);
                  return Math.max(prev, target);
                }
                return prev;
              });
            }, delay);
          });
        });

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            try {
              const errData = JSON.parse(xhr.responseText);
              reject(new Error(errData.detail || 'Upload failed'));
            } catch {
              reject(new Error('Upload failed'));
            }
          }
        });

        xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
        xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));

        xhr.open('POST', `${apiUrl}/api/documents/upload`);
        xhr.send(formData);
      });

      // Backend processing complete
      setUploadPercent(95);
      setUploadProgress('Finalizing...');
      await new Promise(resolve => setTimeout(resolve, 300));

      // Success
      const doc: Document = {
        id: result.document_id,
        filename: result.filename,
        format: file.name.split('.').pop() || 'unknown',
        status: result.status,
        word_count: result.word_count,
        chunk_count: result.chunk_count,
        uploaded_at: new Date().toISOString(),
        indexed_at: new Date().toISOString(),
        error: null,
      };

      setUploadPercent(100);
      setUploadProgress('✓ Document ready!');
      setTimeout(() => {
        setUploadProgress('');
        setUploadPercent(0);
        setUploading(false);
        onDocumentUploaded(doc);
      }, 800);

    } catch (err) {
      console.error('Upload error:', err);
      setUploadProgress('');
      setUploadPercent(0);
      setUploading(false);
      onError(`Upload failed: ${(err as Error).message}`);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const getStatusBadge = (status: Document['status']) => {
    switch (status) {
      case 'indexed':
        return <Badge variant="success" className="gap-1"><CheckCircle2 className="w-3 h-3" /> Indexed</Badge>;
      case 'processing':
        return <Badge variant="warning" className="gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Processing</Badge>;
      case 'failed':
        return <Badge variant="destructive" className="gap-1"><AlertCircle className="w-3 h-3" /> Failed</Badge>;
      default:
        return <Badge variant="secondary">Pending</Badge>;
    }
  };

  return (
    <aside className="w-full md:w-80 min-w-0 md:border-r border-border flex flex-col bg-card overflow-hidden">
      {/* Header */}
      <div className="p-4 md:p-4 border-b border-border">
        <h2 className="text-lg md:text-lg font-semibold">Documents</h2>
        <p className="text-xs md:text-xs text-muted-foreground mt-1">
          {connectionStatus === 'connecting' 
            ? 'Connecting...' 
            : 'Upload a document to start chatting'}
        </p>
      </div>

      {/* Document List */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {documents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No documents uploaded yet</p>
            </div>
          ) : (
            documents.map((doc) => (
              <Card
                key={doc.id}
                className={`p-3 cursor-pointer transition-all hover:shadow-md overflow-hidden ${
                  doc.id === activeDocumentId
                    ? 'ring-2 ring-primary shadow-lg'
                    : ''
                }`}
                onClick={() => onDocumentSelect(doc.id)}
              >
                <div className="flex items-start justify-between gap-2 min-w-0">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <p className="text-sm font-medium truncate" title={doc.filename}>{doc.filename}</p>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      {getStatusBadge(doc.status)}
                      {doc.chunk_count && (
                        <span className="text-xs text-muted-foreground">
                          {doc.chunk_count} chunks
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      </ScrollArea>

      <Separator />

      {/* Upload Zone */}
      <div className="p-4 md:p-4">
        {uploading ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm md:text-sm">
              <Loader2 className="w-4 h-4 md:w-4 md:h-4 animate-spin" />
              <span>{uploadProgress}</span>
            </div>
            <Progress value={uploadPercent} />
            <p className="text-xs md:text-xs text-muted-foreground text-right">{uploadPercent}%</p>
          </div>
        ) : (
          <div
            className={`border-2 border-dashed rounded-lg p-6 md:p-6 text-center transition-colors ${
              isDragging
                ? 'border-primary bg-primary/10'
                : 'border-border hover:border-primary/50'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Upload className="w-10 h-10 md:w-8 md:h-8 mx-auto mb-2 md:mb-2 text-muted-foreground" />
            <p className="text-base md:text-sm font-medium mb-1 md:mb-1">Drop file here</p>
            <p className="text-sm md:text-xs text-muted-foreground mb-3 md:mb-3">
              PDF, TXT, or MD (max 10MB)
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              onChange={handleFileInputChange}
              className="hidden"
            />
            <Button
              size="lg"
              onClick={() => fileInputRef.current?.click()}
              className="w-full h-12 md:h-auto text-base md:text-sm"
              disabled={connectionStatus !== 'connected'}
            >
              {connectionStatus === 'connecting' ? 'Connecting...' : 'Upload Document'}
            </Button>
          </div>
        )}
      </div>
    </aside>
  );
}
