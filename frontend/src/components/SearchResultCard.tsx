import React from 'react';

interface SearchResult {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet: string;
}

export const SearchResultCard: React.FC<{ result: SearchResult }> = ({ result }) => {
  return (
    <div className="glass-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all' }}>
          {result.file_path}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: 4 }}>
          L{result.start_line}-{result.end_line}
        </span>
      </div>
      <pre style={{ 
        margin: 0, 
        padding: '12px', 
        background: 'var(--bg-tertiary)', 
        borderRadius: '8px', 
        overflowX: 'auto',
        fontSize: 13,
        fontFamily: "'JetBrains Mono', monospace",
        color: 'var(--text-secondary)'
      }}>
        <code>{result.snippet}</code>
      </pre>
    </div>
  );
};