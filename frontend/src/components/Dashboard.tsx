import React, { useState, useEffect } from 'react';
import { RepoCard } from './RepoCard';
import { useNavigate } from 'react-router-dom';
import { Loader } from './Loader';

interface Repo {
  name: string;
  status: string;
  files: number;
  symbols: number;
  nodes: number;
  edges: number;
}

export const Dashboard: React.FC = () => {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetch('/api/repo/list')
      .then(res => res.json())
      .then((data: { repos: string[] }) => {
        const repoPromises = data.repos.map(name =>
          fetch(`/api/repo/stats/${encodeURIComponent(name)}`)
            .then(res => res.ok ? res.json() : null)
            .catch(() => null)
        );
        return Promise.all(repoPromises);
      })
      .then((statsArray) => {
        const validRepos = statsArray.filter((s): s is Repo => s !== null);
        setRepos(validRepos);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleAddRepo = () => {
    // Show simple clone form - in production would be modal
    const url = prompt('Enter GitHub repository URL:');
    if (url) {
      fetch('/api/repo/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: url })
      })
      .then(() => window.location.reload())
      .catch(err => setError(err.message));
    }
  };

  if (loading) return <Loader />;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">localRAG Dashboard</h1>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/search')}
              className="px-4 py-2 text-gray-700 hover:text-gray-900"
            >
              🔍 Search
            </button>
            <button
              onClick={() => navigate('/chat')}
              className="px-4 py-2 text-gray-700 hover:text-gray-900"
            >
              💬 Chat
            </button>
            <button
              onClick={() => navigate('/logs')}
              className="px-4 py-2 text-gray-700 hover:text-gray-900"
            >
              📋 Logs
            </button>
            <button
              onClick={handleAddRepo}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              + Add Repository
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6">
        {repos.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No repositories indexed yet.</p>
            <button
              onClick={handleAddRepo}
              className="mt-4 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Clone & Index Your First Repo
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {repos.map((repo) => (
              <RepoCard key={repo.name} stats={repo} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};