import React from 'react';

interface SearchResult {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
}

export const SearchResultCard: React.FC<{ result: SearchResult }> = ({ result }) => {
  return (
    <div className="p-4 border rounded-lg hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-center mb-2">
        <span className="font-medium text-gray-800">{result.file_path}</span>
        <span className="text-sm text-gray-500">
          Lines {result.start_line}-{result.end_line}
        </span>
      </div>
      <pre className="p-2 bg-gray-800 text-gray-100 rounded">
        <code>{result.snippet}</code>
      </pre>
    </div>
  );
};