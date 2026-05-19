'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { KnowledgeGapsTable } from '@/components/admin/KnowledgeGapsTable';
import type { KnowledgeGap } from '@/components/admin/KnowledgeGapsTable';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export default function KnowledgeGapsPage() {
  const router = useRouter();
  const [gaps, setGaps] = useState<KnowledgeGap[]>([]);

  const load = useCallback(async (): Promise<void> => {
    const { data: { session } } = await createClient().auth.getSession();
    if (!session) { router.push('/login'); return; }

    const res = await fetch(`${API_BASE}/admin/knowledge-gaps`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    if (!res.ok) return;
    const data = await res.json() as { items: KnowledgeGap[] };
    setGaps(data.items);
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="font-semibold text-gray-900">Knowledge Gaps</h1>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-8">
        <KnowledgeGapsTable gaps={gaps} />
      </div>
    </>
  );
}
