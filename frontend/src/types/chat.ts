export interface Source {
  doc_name: string;
  page_number: number | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  isLoading?: boolean;
}
