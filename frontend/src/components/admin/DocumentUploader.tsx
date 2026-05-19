'use client';

import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';

interface Props {
  onUploadComplete: () => void;
}

type UploadStatus = 'idle' | 'uploading';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function DocumentUploader({ onUploadComplete }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFileSelect(selected: File): void {
    setFile(selected);
    setStatus('idle');
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
  }

  async function handleUpload(): Promise<void> {
    if (!file || status === 'uploading') return;

    setStatus('uploading');

    try {
      const { data: { session } } = await createClient().auth.getSession();
      if (!session) throw new Error('Not authenticated');

      const form = new FormData();
      form.append('file', file);
      if (category.trim()) form.append('category', category.trim());

      const res = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: form,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }

      const data = (await res.json()) as { chunk_count: number };
      toast.success(`Ingested — ${data.chunk_count} chunks created`);
      setFile(null);
      setCategory('');
      if (inputRef.current) inputRef.current.value = '';
      onUploadComplete();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setStatus('idle');
    }
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 transition-colors ${
          isDragging
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={e => {
            const f = e.target.files?.[0];
            if (f) handleFileSelect(f);
          }}
        />
        <svg className="mb-3 h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        {file ? (
          <p className="text-sm font-medium text-gray-700">{file.name}</p>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-700">Drop a file here or click to browse</p>
            <p className="mt-1 text-xs text-gray-400">PDF, DOCX, or TXT · max 50 MB</p>
          </>
        )}
      </div>

      {/* Category */}
      <input
        type="text"
        value={category}
        onChange={e => setCategory(e.target.value)}
        placeholder="Category (optional — e.g. billing, onboarding)"
        className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />

      {/* Upload button */}
      <button
        onClick={() => void handleUpload()}
        disabled={!file || status === 'uploading'}
        className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {status === 'uploading' ? 'Ingesting…' : 'Upload & Ingest'}
      </button>

    </div>
  );
}
