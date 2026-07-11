import React from 'react';
import { useNavigate } from 'react-router-dom';

interface RepoStats {
  name: string;
  status: string;
  files: number;
  symbols: number;
  nodes: number;
  edges: number;
}

export const RepoCard: React.FC<{ stats: RepoStats }> = ({ stats }) => {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/repos/${encodeURIComponent(stats.name)}`)}
      className="p-4 border rounded-lg hover:shadow-lg transition-all cursor-pointer bg-white"
    >
      <h3 className="text-lg font-semibold text-gray-800">{stats.name}</h3>
      <div className="grid grid-cols-2 gap-2 mt-2">
        <div>
          <p className="text-sm text-gray-500">Status</p>
          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
            stats.status === 'ready' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
          }`}>
            {stats.status}
          </span>
        </div>
        <div>
          <p className="text-sm text-gray-500">Files</p>
          <p className="text-sm font-semibold text-gray-900">{stats.files}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Symbols</p>
          <p className="text-sm font-semibold text-gray-900">{stats.symbols}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Graph</p>
          <p className="text-sm font-semibold text-gray-900">{stats.nodes}N / {stats.edges}E</p>
        </div>
      </div>
    </div>
  );
};