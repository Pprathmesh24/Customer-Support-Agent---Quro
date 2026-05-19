'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { EscalationsTable, type Escalation } from '@/components/admin/EscalationsTable';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export default function EscalationsPage() {
  const router = useRouter();
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);

  const loadEscalations = useCallback(async (): Promise<void> => {
    try {
      const { data: { session } } = await createClient().auth.getSession();
      if (!session) { router.push('/login'); return; }
      const res = await fetch(`${API_BASE}/admin/escalations`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        const data = await res.json() as { items: Escalation[] };
        setEscalations(data.items);
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void loadEscalations();
  }, [loadEscalations]);

  return (
    <>
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-base font-semibold text-gray-900">Escalated Tickets</h1>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-sm text-gray-400">Loading…</div>
        ) : (
          <EscalationsTable escalations={escalations} />
        )}
      </div>
    </>
  );
}
