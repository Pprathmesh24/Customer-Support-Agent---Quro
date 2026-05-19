'use client';

import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';
import { DocumentUploader } from '@/components/admin/DocumentUploader';
import { EmptyState } from '@/components/ui/EmptyState';

interface Document {
  id: string;
  name: string;
  category: string | null;
  chunk_count: number | null;
  created_at: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadDocuments = useCallback(async (): Promise<void> => {
    const { data } = await createClient()
      .from('documents')
      .select('id, name, category, chunk_count, created_at')
      .order('created_at', { ascending: false });
    setDocuments((data ?? []) as Document[]);
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  async function handleDelete(id: string): Promise<void> {
    setDeletingId(id);
    const { error } = await createClient().from('documents').delete().eq('id', id);
    setDeletingId(null);
    if (error) {
      toast.error('Failed to delete document');
    } else {
      toast.success('Document deleted');
      void loadDocuments();
    }
  }

  return (
    <>
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-base font-semibold text-gray-900">Documents</h1>
      </header>

      <div className="mx-auto max-w-3xl space-y-8 px-6 py-8">
        {/* Upload section */}
        <section className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">Upload document</h2>
          <DocumentUploader onUploadComplete={loadDocuments} />
        </section>

        {/* Document list */}
        <section>
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Uploaded documents</h2>
          {documents.length === 0 ? (
            <EmptyState
              message="No documents uploaded yet"
              subtext="Upload a PDF, DOCX, or TXT file above to get started."
            />
          ) : (
            <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-200 bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Category</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">Chunks</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">Uploaded</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {documents.map(doc => (
                    <tr key={doc.id} className="transition-colors hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{doc.name}</td>
                      <td className="px-4 py-3 text-gray-500">{doc.category ?? '—'}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-gray-500">
                        {doc.chunk_count ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-400">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => void handleDelete(doc.id)}
                          disabled={deletingId === doc.id}
                          className="text-xs text-red-500 transition-colors hover:text-red-700 disabled:opacity-40"
                        >
                          {deletingId === doc.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
