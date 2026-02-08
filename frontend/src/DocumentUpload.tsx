/**
 * Document Upload Component for RAG Knowledge Base
 * Handles file upload, progress tracking, and document management
 */

import { useState, useRef } from 'react';

interface Document {
  id: string;
  filename: string;
  format: string;
  status: 'pending' | 'processing' | 'indexed' | 'failed';
  word_count: number | null;
  chunk_count: number | null;
  uploaded_at: string | null;
  indexed_at: string | null;
  error: string | null;
}

interface DocumentUploadProps {
  sessionId: string;
  onUploadComplete?: (doc: Document) => void;
  onError?: (error: string) => void;
}

export default function DocumentUpload({ sessionId, onUploadComplete, onError }: DocumentUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<string>('');
  const [currentDoc, setCurrentDoc] = useState<Document | null>(null);
  const [chunkSize, setChunkSize] = useState(500);
  const [chunkOverlap, setChunkOverlap] = useState(50);
  const [showSettings, setShowSettings] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const validExtensions = ['.pdf', '.txt', '.md'];
    const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!validExtensions.includes(extension)) {
      onError?.('Unsupported file format. Please upload PDF, TXT, or MD files.');
      return;
    }

    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      onError?.('File too large. Maximum size is 10MB.');
      return;
    }

    setSelectedFile(file);
    setProgress('');
  };

  const handleUpload = async () => {
    if (!selectedFile || !sessionId) return;

    setUploading(true);
    setProgress('Preparing upload...');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('session_id', sessionId);
      formData.append('chunk_size', chunkSize.toString());
      formData.append('chunk_overlap', chunkOverlap.toString());

      setProgress('Uploading file...');

      const response = await fetch(`${apiUrl}/api/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || 'Upload failed');
      }

      // Success
      const doc: Document = {
        id: result.document_id,
        filename: result.filename,
        format: selectedFile.name.split('.').pop() || 'unknown',
        status: result.status,
        word_count: result.word_count,
        chunk_count: result.chunk_count,
        uploaded_at: new Date().toISOString(),
        indexed_at: new Date().toISOString(),
        error: null,
      };

      setCurrentDoc(doc);
      setProgress('');
      setSelectedFile(null);
      onUploadComplete?.(doc);

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Upload error:', error);
      const errorMsg = error instanceof Error ? error.message : 'Upload failed';
      setProgress('');
      onError?.(errorMsg);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!currentDoc) return;

    try {
      const response = await fetch(`${apiUrl}/api/documents/${currentDoc.id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Delete failed');
      }

      setCurrentDoc(null);
    } catch (error) {
      console.error('Delete error:', error);
      onError?.(error instanceof Error ? error.message : 'Delete failed');
    }
  };

  const handleReplace = () => {
    setCurrentDoc(null);
    fileInputRef.current?.click();
  };

  return (
    <div className="document-upload">
      <h3>📚 Knowledge Base (Optional)</h3>
      
      {/* Current Document Status */}
      {currentDoc ? (
        <div className="document-status">
          <div className="doc-info">
            <span className="doc-icon">
              {currentDoc.status === 'indexed' ? '✅' : currentDoc.status === 'failed' ? '❌' : '⏳'}
            </span>
            <div className="doc-details">
              <div className="doc-name">{currentDoc.filename}</div>
              <div className="doc-meta">
                {currentDoc.chunk_count} chunks • {currentDoc.word_count?.toLocaleString()} words
                {currentDoc.indexed_at && (
                  <> • Indexed {new Date(currentDoc.indexed_at).toLocaleTimeString()}</>
                )}
              </div>
            </div>
          </div>
          <div className="doc-actions">
            <button onClick={handleReplace} className="btn-secondary">
              🔄 Replace
            </button>
            <button onClick={handleDelete} className="btn-danger">
              🗑️ Delete
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Upload Section */}
          {!selectedFile && !uploading && (
            <div className="upload-section">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt,.md"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              <button onClick={() => fileInputRef.current?.click()} className="btn-upload">
                📤 Upload Document
              </button>
              <div className="upload-hint">
                Supported: PDF, TXT, MD (max 10MB)
              </div>
            </div>
          )}

          {/* File Selected */}
          {selectedFile && !uploading && (
            <div className="file-selected">
              <div className="file-info">
                <span className="file-icon">📄</span>
                <span className="file-name">{selectedFile.name}</span>
                <span className="file-size">
                  ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
              </div>
              
              {/* Settings */}
              <button 
                onClick={() => setShowSettings(!showSettings)}
                className="btn-text"
              >
                ⚙️ {showSettings ? 'Hide' : 'Show'} Settings
              </button>

              {showSettings && (
                <div className="chunk-settings">
                  <div className="setting-row">
                    <label>Chunk Size (tokens):</label>
                    <input
                      type="number"
                      min={100}
                      max={2000}
                      value={chunkSize}
                      onChange={(e) => setChunkSize(Number(e.target.value))}
                    />
                    <span className="setting-hint">Default: 500</span>
                  </div>
                  <div className="setting-row">
                    <label>Chunk Overlap (tokens):</label>
                    <input
                      type="number"
                      min={0}
                      max={500}
                      value={chunkOverlap}
                      onChange={(e) => setChunkOverlap(Number(e.target.value))}
                    />
                    <span className="setting-hint">Default: 50</span>
                  </div>
                </div>
              )}

              <div className="upload-actions">
                <button onClick={handleUpload} className="btn-primary">
                  ✅ Upload & Process
                </button>
                <button 
                  onClick={() => {
                    setSelectedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }} 
                  className="btn-secondary"
                >
                  ✖️ Cancel
                </button>
              </div>
            </div>
          )}

          {/* Upload Progress */}
          {uploading && (
            <div className="upload-progress">
              <div className="spinner"></div>
              <div className="progress-text">{progress}</div>
              <div className="progress-hint">
                This may take 20-30 seconds for large documents...
              </div>
            </div>
          )}
        </>
      )}

      <style>{`
        .document-upload {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 20px;
        }

        @media (max-width: 768px) {
          .document-upload {
            padding: 0;
            margin-bottom: 0;
            background: transparent;
            border: none;
          }
        }

        .document-upload h3 {
          margin: 0 0 15px 0;
          font-size: 16px;
          color: #111827;
        }

        @media (max-width: 768px) {
          .document-upload h3 {
            font-size: 18px;
          }
        }

        .document-status {
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: #ecfdf5;
          border: 1px solid #10b981;
          border-radius: 8px;
          padding: 12px;
          flex-wrap: wrap;
          gap: 12px;
        }

        @media (max-width: 768px) {
          .document-status {
            flex-direction: column;
            align-items: flex-start;
          }
        }

        .doc-info {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 1;
          min-width: 200px;
        }

        .doc-icon {
          font-size: 24px;
        }

        .doc-details {
          flex: 1;
        }

        .doc-name {
          font-weight: 600;
          color: #111827;
          margin-bottom: 4px;
        }

        .doc-meta {
          font-size: 12px;
          color: #6b7280;
        }

        .doc-actions {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        @media (max-width: 768px) {
          .doc-actions {
            width: 100%;
          }
          
          .doc-actions button {
            flex: 1;
            min-height: 44px;
          }
        }

        .upload-section {
          text-align: center;
          padding: 20px;
          min-height: 44px;
        }

        @media (max-width: 768px) {
          .btn-upload {
            width: 100%;
            padding: 16px 24px;
            font-size: 16px;
            min-height: 56px;
          }
        }

        .btn-upload {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border: none;
          border-radius: 8px;
          padding: 12px 24px;
          color: white;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: transform 0.2s;
        }

        .btn-upload:hover {
          transform: scale(1.05);
        }

        .upload-hint {
          margin-top: 8px;
          font-size: 12px;
          color: #6b7280;
        }

        .file-selected {
          background: #f9fafb;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 15px;
        }

        .file-info {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          color: #111827;
        }

        .file-icon {
          font-size: 20px;
        }

        .file-name {
          flex: 1;
          font-weight: 500;
        }

        .file-size {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.6);
        }

        .chunk-settings {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 6px;
          padding: 12px;
          margin: 12px 0;
        }

        .setting-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 8px;
        }

        .setting-row:last-child {
          margin-bottom: 0;
        }

        .setting-row label {
          flex: 1;
          font-size: 13px;
          color: rgba(255, 255, 255, 0.8);
          flex-wrap: wrap;
        }

        @media (max-width: 768px) {
          .upload-actions {
            flex-direction: column;
          }
          
          .upload-actions button {
            width: 100%;
            min-height: 48px;
          }
        }

        .setting-row input {
          width: 80px;
          padding: 6px;
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 4px;
          color: #fff;
          font-size: 13px;
          min-height: 40px;
        }

        @media (max-width: 768px) {
          .btn-primary, .btn-secondary, .btn-danger {
            font-size: 15px;
            min-height: 48px;
            padding: 12px 20px;
          }
        }

        .setting-hint {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.4);
          width: 80px;
        }

        .upload-actions {
          display: flex;
          gap: 8px;
          margin-top: 12px;
        }

        .btn-primary, .btn-secondary, .btn-danger, .btn-text {
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          border: none;
          transition: opacity 0.2s;
        }

        .btn-primary {
          background: #10b981;
          color: white;
          flex: 1;
        }

        .btn-secondary#f3f4f6;
          color: #374151;
        }

        .btn-danger {
          background: #ef4444;
          color: white;
        }

        .btn-text {
          background: transparent;
          color: #6b7280
          color: rgba(255, 255, 255, 0.7);
          text-decoration: underline;
          padding: 4px 8px;
        }

        .btn-primary:hover, .btn-secondary:hover, .btn-danger:hover, .btn-text:hover {
          opacity: 0.8;
        }

        .upload-progress {
          text-align: center;
          padding: 30px;
        }

        .spinner {
          border: 3px solid rgba(255, 255, 255, 0.1);
          border-top: 3px solid #667eea;
          border-radius: 50%;
          width: 40px;
          height: 40px;
          animation: spin 1s linear infinite;
          margin: 0 auto 15px;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        .progress-text {
          font-siz111827;
          margin-bottom: 8px;
          font-weight: 500;
        }

        .progress-hint {
          font-size: 12px;
          color: #6b7280
          color: rgba(255, 255, 255, 0.5);
        }
      `}</style>
    </div>
  );
}
