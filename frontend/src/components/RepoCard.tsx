import React from 'react';
import { useNavigate } from 'react-router-dom';

interface RepoStats {
  repo_name: string;
  status: string;
  files_parsed: number;
  symbols_count: number;
  graph_nodes: number;
  graph_edges: number;
}

export const RepoCard: React.FC<{ stats: RepoStats }> = ({ stats }) => {
  const navigate = useNavigate();
  const isReady = stats.status === 'ready';

  return (
    <div
      onClick={() => navigate(`/repos/${encodeURIComponent(stats.repo_name)}`)}
      className="glass-card"
      style={{ padding: '24px', cursor: 'pointer', position: 'relative', overflow: 'hidden' }}
    >
      {stats.status === 'indexing' && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 3, 
          background: 'var(--accent-gradient)', opacity: 0.8
        }} />
      )}
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all', paddingRight: 16 }}>
          {stats.repo_name}
        </h3>
        <div className={`stat-badge ${stats.status === 'indexing' ? 'pulse-dot' : ''}`} style={{
          background: isReady ? 'rgba(34, 197, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
          color: isReady ? 'var(--status-ready)' : 'var(--status-indexing)',
          border: `1px solid ${isReady ? 'rgba(34, 197, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
          {stats.status}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Files</div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{stats.files_parsed}</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Symbols</div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{stats.symbols_count}</div>
        </div>
        <div style={{ gridColumn: 'span 2' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Graph</div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{stats.graph_nodes} Nodes / {stats.graph_edges} Edges</div>
        </div>
      </div>
    </div>
  );
};