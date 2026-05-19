import Link from 'next/link';
import { EmptyState } from '@/components/ui/EmptyState';

export interface Escalation {
  id: string;
  title: string;
  status: string;
  linear_ticket_url: string | null;
  created_at: string;
}

interface Props {
  escalations: Escalation[];
}

export function StatusBadge({ status }: { status: string }) {
  const styles =
    status === 'open'
      ? 'bg-yellow-50 text-yellow-700 ring-yellow-200'
      : status === 'resolved'
        ? 'bg-green-50 text-green-700 ring-green-200'
        : 'bg-gray-100 text-gray-600 ring-gray-200';

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${styles}`}
    >
      {status}
    </span>
  );
}

export function EscalationsTable({ escalations }: Props) {
  if (escalations.length === 0) {
    return (
      <EmptyState
        message="No escalated tickets yet"
        subtext="Tickets appear here when the agent cannot answer a customer question."
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-200 bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Title</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Linear</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">Escalated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {escalations.map(esc => (
            <tr key={esc.id} className="transition-colors hover:bg-gray-50">
              <td className="px-4 py-3">
                <Link
                  href={`/admin/escalations/${esc.id}`}
                  className="font-medium text-gray-900 hover:text-blue-600"
                >
                  {esc.title}
                </Link>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={esc.status} />
              </td>
              <td className="px-4 py-3">
                {esc.linear_ticket_url ? (
                  <a
                    href={esc.linear_ticket_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    View ticket
                  </a>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-gray-400">
                {new Date(esc.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
