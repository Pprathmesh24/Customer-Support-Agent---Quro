'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';
import { StatusBadge } from '@/components/admin/EscalationsTable';
import { MessageList } from '@/components/chat/MessageList';
import type { Message, Source } from '@/types/chat';

interface EscalationDetail {
  id: string;
  conversation_id: string;
  user_id: string;
  title: string;
  status: string;
  linear_ticket_id: string | null;
  linear_ticket_url: string | null;
  created_at: string;
  resolved_at: string | null;
}

interface ConversationHistoryResponse {
  conversation_id: string;
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    sources: Source[];
  }>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
];

export default function EscalationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [escalation, setEscalation] = useState<EscalationDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const load = useCallback(async (): Promise<void> => {
    try {
      const { data: { session } } = await createClient().auth.getSession();
      if (!session) { router.push('/login'); return; }

      const [escRes, histRes] = await Promise.all([
        fetch(`${API_BASE}/admin/escalations/${id}`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        }),
        fetch(`${API_BASE}/admin/escalations/${id}/conversation`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        }),
      ]);

      if (!escRes.ok) return;
      const escData = await escRes.json() as EscalationDetail;
      setEscalation(escData);

      if (histRes.ok) {
        const histData: ConversationHistoryResponse = await histRes.json();
        setMessages(
          histData.messages.map(m => ({
            id: m.id,
            role: m.role,
            content: m.content,
            sources: m.sources,
          })),
        );
      }
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleStatusChange(newStatus: string): Promise<void> {
    if (!escalation || newStatus === escalation.status) return;
    setUpdatingStatus(true);
    try {
      const { data: { session } } = await createClient().auth.getSession();
      if (!session) return;
      const res = await fetch(`${API_BASE}/admin/escalations/${id}`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) { toast.error('Failed to update status'); return; }
      const updated = await res.json() as EscalationDetail;
      setEscalation(updated);
      toast.success(`Status updated to ${newStatus.replace('_', ' ')}`);
    } finally {
      setUpdatingStatus(false);
    }
  }

  return (
    <>
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center gap-2 text-sm">
          <Link href="/admin/escalations" className="text-gray-500 hover:text-gray-700">
            Escalated Tickets
          </Link>
          <span className="text-gray-300">/</span>
          <span className="font-medium text-gray-900">
            {escalation?.title ?? '…'}
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-sm text-gray-400">Loading…</div>
        ) : !escalation ? (
          <div className="flex items-center justify-center py-16 text-sm text-gray-400">Ticket not found.</div>
        ) : (
          <>
            {/* Metadata + status control */}
            <section className="rounded-xl border border-gray-200 bg-white p-5">
              <dl className="mb-5 flex flex-wrap gap-6 text-sm">
                <div>
                  <dt className="mb-1 text-xs font-medium text-gray-500">Escalated</dt>
                  <dd className="text-gray-900">{new Date(escalation.created_at).toLocaleString()}</dd>
                </div>
                {escalation.resolved_at && (
                  <div>
                    <dt className="mb-1 text-xs font-medium text-gray-500">Resolved</dt>
                    <dd className="text-gray-900">{new Date(escalation.resolved_at).toLocaleString()}</dd>
                  </div>
                )}
                <div>
                  <dt className="mb-1 text-xs font-medium text-gray-500">User ID</dt>
                  <dd className="font-mono text-xs text-gray-600">{escalation.user_id}</dd>
                </div>
                {escalation.linear_ticket_url && (
                  <div>
                    <dt className="mb-1 text-xs font-medium text-gray-500">Linear ticket</dt>
                    <dd>
                      <a
                        href={escalation.linear_ticket_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {escalation.linear_ticket_id ?? 'View ticket'}
                      </a>
                    </dd>
                  </div>
                )}
              </dl>

              {/* Status controls */}
              <div>
                <p className="mb-2 text-xs font-medium text-gray-500">Status</p>
                <div className="flex gap-2">
                  {STATUS_OPTIONS.map(opt => {
                    const isActive = escalation.status === opt.value;
                    return (
                      <button
                        key={opt.value}
                        onClick={() => void handleStatusChange(opt.value)}
                        disabled={updatingStatus}
                        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                          isActive
                            ? 'bg-gray-900 text-white'
                            : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* Conversation thread */}
            <section className="rounded-xl border border-gray-200 bg-white px-6 py-6">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-500">
                Conversation
              </h2>
              {messages.length > 0 ? (
                <MessageList messages={messages} />
              ) : (
                <p className="text-sm text-gray-400">No conversation history available.</p>
              )}
            </section>
          </>
        )}
      </div>
    </>
  );
}
