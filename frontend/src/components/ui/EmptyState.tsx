interface Props {
  message: string;
  subtext?: string;
}

export function EmptyState({ message, subtext }: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white py-14 text-center">
      <svg
        className="mb-3 h-8 w-8 text-gray-300"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <p className="text-sm font-medium text-gray-500">{message}</p>
      {subtext && <p className="mt-1 text-xs text-gray-400">{subtext}</p>}
    </div>
  );
}
