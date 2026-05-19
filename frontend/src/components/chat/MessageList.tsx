'use client';

import { useEffect, useRef } from 'react';
import type { Message } from '@/types/chat';
import { SourceCitation } from './SourceCitation';

interface Props {
  messages: Message[];
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400" />
    </div>
  );
}

export function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col gap-4">
      {messages.map(msg =>
        msg.role === 'user' ? (
          <div key={msg.id} className="flex justify-end">
            <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-sm text-white">
              {msg.content}
            </div>
          </div>
        ) : (
          <div key={msg.id} className="flex justify-start">
            <div className="max-w-[80%] space-y-2">
              <div className="rounded-2xl rounded-tl-sm border border-gray-200 bg-white text-sm text-gray-800">
                {msg.isLoading ? (
                  <ThinkingIndicator />
                ) : (
                  <p className="whitespace-pre-wrap px-4 py-2.5">{msg.content}</p>
                )}
              </div>
              {!msg.isLoading && msg.sources && msg.sources.length > 0 && (
                <div className="flex flex-wrap gap-1.5 px-1">
                  {msg.sources.map((source, i) => (
                    <SourceCitation key={i} source={source} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ),
      )}
      <div ref={bottomRef} />
    </div>
  );
}
