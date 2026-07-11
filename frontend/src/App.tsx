import React from 'react';
import { Dashboard } from './components/Dashboard';
import { Search } from './components/Search';
import { Chat } from './components/Chat';
import { RepoDetail } from './components/RepoDetail';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Logs } from './components/Logs';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/repos/:repoName" element={<RepoDetail />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;