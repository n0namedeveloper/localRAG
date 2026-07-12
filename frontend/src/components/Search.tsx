import React, { useState, useEffect } from 'react';
import { SearchResultCard } from './SearchResultCard';
import ReactMarkdown from 'react-markdown';

interface SearchResult {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
}

export const Search: React.FC = () => {
  const [query, setQuery] = useState('');
  const [exactMatch, setExactMatch] = useState(false);
  const [repos, setRepos] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('all');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [summary, setSummary] = useState('');
  const [isSummarizing, setIsSummarizing] = useState(false);

  useEffect(() => {
    fetch('/api/repo/list')
      .then(res => res.json())
      .then(data => {
        if (data.repos) {
          setRepos(data.repos);
        }
      })
      .catch(console.error);
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setSummary('');
    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          repo_url: selectedRepo, 
          top_k: 20,
          exact_match: exactMatch
        }),
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

  const handleSummarize = async () => {
    if (!query.trim() || results.length === 0) return;
    setIsSummarizing(true);
    setSummary('');

    try {
      const response = await fetch('/api/search/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          repo_url: selectedRepo, 
          top_k: 5,
          exact_match: exactMatch
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let done = false;
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          setSummary(prev => prev + chunk);
        }
      }
    } catch (err) {
      console.error(err);
      setSummary('Error generating summary.');
    } finally {
      setIsSummarizing(false);
    }
  };

  return (
    <div style={{ padding: '40px', maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 24px 0' }}>Search codebase</h1>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <select 
              className="input-field" 
              style={{ width: 250, padding: '12px 16px' }}
              value={selectedRepo}
              onChange={e => setSelectedRepo(e.target.value)}
            >
              <option value="all">All Repositories</option>
              {repos.map(r => (
                <option key={r.repo_name} value={r.repo_name}>{r.repo_name}</option>
              ))}
            </select>
            
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search code..."
              className="input-field"
              style={{ padding: '12px 16px', fontSize: 16, flex: 1 }}
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

          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', color: 'var(--text-secondary)' }}>
              <input 
                type="radio" 
                name="searchType" 
                checked={!exactMatch} 
                onChange={() => setExactMatch(false)} 
              />
              Semantic Search
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', color: 'var(--text-secondary)' }}>
              <input 
                type="radio" 
                name="searchType" 
                checked={exactMatch} 
                onChange={() => setExactMatch(true)} 
              />
              Exact Symbol Match
            </label>
          </div>
        </div>
      </div>

      {(summary || isSummarizing) && (
        <div className="glass-card fade-in" style={{ padding: 24, borderLeft: '4px solid var(--accent-primary)' }}>
          <div style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--accent-primary)', fontWeight: 700, marginBottom: 12 }}>
            AI Summary
          </div>
          <div className="chat-markdown" style={{ background: 'transparent' }}>
            <ReactMarkdown>{summary || 'Generating AI overview...'}</ReactMarkdown>
          </div>
        </div>
      )}

      {results.length > 0 && !summary && !isSummarizing && (
        <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
          <button onClick={handleSummarize} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            ✨ Generate AI Overview
          </button>
        </div>
      )}

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
      ) : query && !isLoading && (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
          No results found.
        </div>
      )}
    </div>
  );
};