import type { Source } from '@/types/chat';

interface Props {
  source: Source;
}

export function SourceCitation({ source }: Props) {
  const label = source.page_number
    ? `${source.doc_name} · p. ${source.page_number}`
    : source.doc_name;

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600 ring-1 ring-inset ring-gray-200">
      <svg className="h-3 w-3 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      {label}
    </span>
  );
}
