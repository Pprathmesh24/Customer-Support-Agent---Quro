export interface KnowledgeGap {
  question: string;
  count: number;
  last_seen: string;
}

interface Props {
  gaps: KnowledgeGap[];
}

import { EmptyState } from '@/components/ui/EmptyState';

export function KnowledgeGapsTable({ gaps }: Props) {
  if (gaps.length === 0) {
    return (
      <EmptyState
        message="No knowledge gaps recorded yet"
        subtext="Questions the agent could not answer will appear here, sorted by frequency."
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-200 bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Question</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">Times Asked</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">Last Seen</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {gaps.map((gap, i) => (
            <tr key={i} className="transition-colors hover:bg-gray-50">
              <td className="px-4 py-3 text-gray-900">{gap.question}</td>
              <td className="px-4 py-3 text-right tabular-nums font-medium text-gray-700">
                {gap.count}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-gray-400">
                {new Date(gap.last_seen).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
