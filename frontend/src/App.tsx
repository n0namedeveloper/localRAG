import React from 'react';
import { Dashboard } from './components/Dashboard';
import { Search } from './components/Search';
import { Chat } from './components/Chat';
import { Agent } from './components/Agent';
import { RepoDetail } from './components/RepoDetail';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Logs } from './components/Logs';
import { Layout } from './components/Layout';
import { LogsProvider } from './contexts/LogsContext';

import { Settings } from './components/Settings';

function App() {
  return (
    <Router>
      <LogsProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/search" element={<Search />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/repos/:repoName" element={<RepoDetail />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </LogsProvider>
    </Router>
  );
}

export default App;