'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';
import { MessageList } from '@/components/chat/MessageList';
import { MessageInput } from '@/components/chat/MessageInput';
import type { Message, Source } from '@/types/chat';

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
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

interface ChatApiResponse {
  answer: string;
  sources: Source[];
  cached: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export default function ChatPage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const tempIdRef = useRef(0);

  async function getToken(): Promise<string> {
    const { data: { session } } = await createClient().auth.getSession();
    if (!session) {
      router.push('/login');
      throw new Error('unauthenticated');
    }
    return session.access_token;
  }

  async function selectConversation(id: string): Promise<void> {
    setActiveConvId(id);
    const token = await getToken();
    const res = await fetch(`${API_BASE}/conversations/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const data: ConversationHistoryResponse = await res.json();
    setMessages(
      data.messages.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        sources: m.sources,
      })),
    );
  }

  async function createNewConversation(): Promise<void> {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.push('/login'); return; }
    const { data } = await supabase
      .from('conversations')
      .insert({ user_id: session.user.id, title: 'New conversation' })
      .select('id, title, updated_at')
      .single();
    if (!data) return;
    const conv = data as Conversation;
    setConversations(prev => [conv, ...prev]);
    setActiveConvId(conv.id);
    setMessages([]);
  }

  async function handleSend(text: string): Promise<void> {
    if (!activeConvId || isLoading) return;

    const isFirstMessage = messages.length === 0;
    const userMsgId = `tmp-u-${tempIdRef.current++}`;
    const loadingId = `tmp-a-${tempIdRef.current++}`;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: text },
      { id: loadingId, role: 'assistant', content: '', isLoading: true },
    ]);
    setIsLoading(true);

    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text, conversation_id: activeConvId }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data: ChatApiResponse = await res.json();

      setMessages(prev =>
        prev.map(m =>
          m.id === loadingId
            ? { id: loadingId, role: 'assistant' as const, content: data.answer, sources: data.sources }
            : m,
        ),
      );

      // Use first user message as conversation title
      if (isFirstMessage) {
        const title = text.length > 50 ? `${text.slice(0, 47)}…` : text;
        const supabase = createClient();
        await supabase.from('conversations').update({ title }).eq('id', activeConvId);
        setConversations(prev =>
          prev.map(c => (c.id === activeConvId ? { ...c, title } : c)),
        );
      }
    } catch {
      setMessages(prev => prev.filter(m => m.id !== loadingId));
      toast.error('Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSignOut(): Promise<void> {
    await createClient().auth.signOut();
    router.push('/login');
  }

  useEffect(() => {
    async function init(): Promise<void> {
      const supabase = createClient();

      const { data: { user } } = await supabase.auth.getUser();
      setUserEmail(user?.email ?? null);

      const { data: convData } = await supabase
        .from('conversations')
        .select('id, title, updated_at')
        .order('updated_at', { ascending: false });
      const convs = (convData ?? []) as Conversation[];
      setConversations(convs);

      if (convs.length > 0) {
        const firstId = convs[0].id;
        setActiveConvId(firstId);
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push('/login'); return; }
        const res = await fetch(`${API_BASE}/conversations/${firstId}`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (res.ok) {
          const histData: ConversationHistoryResponse = await res.json();
          setMessages(
            histData.messages.map(m => ({
              id: m.id,
              role: m.role,
              content: m.content,
              sources: m.sources,
            })),
          );
        }
      } else {
        // Auto-create the first conversation so the user can start chatting immediately
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) { router.push('/login'); return; }
        const { data: newConv } = await supabase
          .from('conversations')
          .insert({ user_id: session.user.id, title: 'New conversation' })
          .select('id, title, updated_at')
          .single();
        if (newConv) {
          const conv = newConv as Conversation;
          setConversations([conv]);
          setActiveConvId(conv.id);
        }
      }
    }

    void init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const activeTitle = conversations.find(c => c.id === activeConvId)?.title ?? 'New conversation';

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-gray-50">
        <div className="border-b border-gray-200 px-4 py-4">
          <span className="text-base font-semibold text-gray-900">Quro</span>
        </div>

        <div className="px-3 pt-3">
          <button
            onClick={() => void createNewConversation()}
            className="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 py-2 text-sm text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New conversation
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
          {conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => void selectConversation(conv.id)}
              className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                conv.id === activeConvId
                  ? 'bg-blue-50 font-medium text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {conv.title}
            </button>
          ))}
        </nav>

        <div className="border-t border-gray-200 px-4 py-3">
          <p className="mb-2 truncate text-xs text-gray-500">{userEmail ?? '…'}</p>
          <button
            onClick={handleSignOut}
            className="text-xs text-gray-400 transition-colors hover:text-gray-600"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main chat area ───────────────────────────────────────── */}
      <main className="flex flex-1 flex-col overflow-hidden">
        <header className="border-b border-gray-200 px-6 py-4">
          <h1 className="text-sm font-medium text-gray-900">{activeTitle}</h1>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <MessageList messages={messages} />
        </div>

        <div className="border-t border-gray-200 px-6 py-4">
          <MessageInput onSend={handleSend} disabled={isLoading} />
        </div>
      </main>
    </div>
  );
}
