import React, { useState } from 'react';
import { SearchResultCard } from './SearchResultCard';

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

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, repo_url: '', top_k: 20 }),
      });
      const data: any[] = await response.json();

      const rawResults = data.map((result: any) => ({
        file_path: result.metadata?.file_path ?? '',
        start_line: result.metadata?.start_line ?? 0,
        end_line: result.metadata?.end_line ?? 0,
        snippet: result.metadata?.signature || result.metadata?.symbol_name || '',
      }));

      const uniqueResults = rawResults.filter((v, i, a) => 
        a.findIndex(t => (t.file_path === v.file_path && t.start_line === v.start_line)) === i
      );

      setResults(uniqueResults);
    } catch (err) {
      console.error('Search error:', err);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '40px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 40 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 24px 0' }}>Search codebase</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search code..."
            className="input-field"
            style={{ padding: '12px 16px', fontSize: 16 }}
          />
          <button
            onClick={handleSearch}
            disabled={isLoading || !query.trim()}
            className="btn-primary"
            style={{ padding: '0 32px' }}
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
          Searching vector database...
        </div>
      ) : results.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: 20 }}>
          {results.map((result, index) => (
            <SearchResultCard key={index} result={result} />
          ))}
        </div>
      ) : query && (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
          No results found.
        </div>
      )}
    </div>
  );
};