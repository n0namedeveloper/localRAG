import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchResultCard } from './SearchResultCard';

interface SearchParams {
  query: string;
  repo_url?: string;
  language?: string;
  symbol_type?: string;
}

interface SearchResult {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
}

export const Search: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        query,
        repo_url: '',
      });
      
      const response = await fetch(`/api/search?${params}`);
      const data = await response.json();
      
      setResults(data.results.map((result: any) => ({
        file_path: result.metadata.file_path,
        start_line: result.metadata.start_line,
        end_line: result.metadata.end_line,
        snippet: result.metadata.signature || result.text,
      })));
    } catch (err) {
      console.error('Search error:', err);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-4">Search</h1>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search code..."
            className="flex-1 p-2 border rounded-lg"
          />
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center p-8">
          Loading results...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {results.map((result, index) => (
            <SearchResultCard key={index} result={result} />
          ))}
        </div>
      )}
    </div>
  );
};