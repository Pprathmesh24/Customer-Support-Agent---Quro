'use client';

import { useEffect, useRef, useState } from 'react';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function MessageInput({ onSend, disabled = false }: Props) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  function handleSend(): void {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex items-end gap-3 rounded-2xl border border-gray-300 bg-white px-4 py-3 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500">
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
        className="max-h-40 flex-1 resize-none bg-transparent text-sm text-gray-900 placeholder-gray-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19V5m-7 7l7-7 7 7" />
        </svg>
      </button>
    </div>
  );
}
