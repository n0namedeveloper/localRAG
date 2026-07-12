import React, { useEffect, useState } from 'react';
import { RepoCard } from './RepoCard';
import { Loader } from './Loader';
import { useNavigate } from 'react-router-dom';

interface RepoStats {
  repo_name: string;
  status: string;
  files_parsed: number;
  symbols_count: number;
  graph_nodes: number;
  graph_edges: number;
}

export const Dashboard: React.FC = () => {
  const [repos, setRepos] = useState<RepoStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [repoUrl, setRepoUrl] = useState('');
  const [adding, setAdding] = useState(false);
  const navigate = useNavigate();

  const fetchRepos = async () => {
    try {
      const res = await fetch('/api/repo/list');
      if (res.ok) {
        const data = await res.json();
        setRepos(data.repos || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRepos();
    const interval = setInterval(fetchRepos, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleAddRepo = async () => {
    if (!repoUrl.trim()) return;
    setAdding(true);
    try {
      const res = await fetch('/api/repo/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl, force_reindex: true }),
      });
      if (res.ok) {
        setRepoUrl('');
        setShowModal(false);
        fetchRepos();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setAdding(false);
    }
  };

  const totalFiles = repos.reduce((acc, r) => acc + r.files_parsed, 0);
  const totalSymbols = repos.reduce((acc, r) => acc + r.symbols_count, 0);

  return (
    <div style={{ padding: '40px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Overview</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>Manage and monitor your indexed repositories</p>
        </div>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          + Add Repository
        </button>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '40px' }}>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 8 }}>Total Repositories</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)' }}>{repos.length}</div>
        </div>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 8 }}>Total Files</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)' }}>{totalFiles}</div>
        </div>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 8 }}>Total Symbols</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)' }}>{totalSymbols}</div>
        </div>
      </div>

      {/* Repositories */}
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: '20px' }}>Your Repositories</h2>
      
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Loader /></div>
      ) : repos.length === 0 ? (
        <div className="glass-card" style={{ padding: '40px', textAlign: 'center', borderStyle: 'dashed' }}>
          <div style={{ fontSize: 32, marginBottom: 16 }}>📂</div>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>No repositories indexed yet</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 24 }}>Add a GitHub repository to start using Code Intelligence</p>
          <button className="btn-primary" onClick={() => setShowModal(true)}>Add your first repo</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {repos.map((repo, i) => (
            <RepoCard key={i} stats={repo} />
          ))}
        </div>
      )}

      {/* Add Repo Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100
        }}>
          <div className="glass-card fade-in" style={{ padding: '32px', width: '100%', maxWidth: '440px', background: 'var(--bg-card)' }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Add Repository</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 24 }}>Enter a public GitHub repository URL.</p>
            
            <input 
              type="text" 
              className="input-field" 
              placeholder="https://github.com/user/repo"
              value={repoUrl}
              onChange={e => setRepoUrl(e.target.value)}
              autoFocus
              onKeyDown={e => e.key === 'Enter' && handleAddRepo()}
            />
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
              <button className="btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={handleAddRepo} disabled={adding || !repoUrl.trim()}>
                {adding ? 'Adding...' : 'Start Indexing'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};