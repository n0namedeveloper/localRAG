import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

export const Agent: React.FC = () => {
  const [issue, setIssue] = useState('');
  const [repos, setRepos] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('all');
  const [plan, setPlan] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

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

  const handleGeneratePlan = async () => {
    if (!issue.trim()) return;

    setIsGenerating(true);
    setPlan('');

    try {
      const response = await fetch('/api/agent/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: issue, 
          repo_url: selectedRepo 
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
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              if (dataStr.trim()) {
                try {
                  const event = JSON.parse(dataStr);
                  if (event.event === 'token') {
                    setPlan(prev => prev + event.data);
                  } else if (event.event === 'done') {
                    done = true;
                  } else if (event.event === 'error') {
                    setPlan(prev => prev + "\n\n**Error:** " + event.data.error);
                  }
                } catch (e) {
                  console.error("Parse error", e);
                }
              }
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setPlan('Error generating plan.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div style={{ padding: '40px', maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 24px 0' }}>Agentic Mode</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
          Describe an issue or a feature you want to implement. The AI will analyze the codebase and generate a detailed implementation plan.
        </p>
        
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
          </div>
          
          <textarea
            value={issue}
            onChange={(e) => setIssue(e.target.value)}
            placeholder="E.g., Implement dark mode support across all components..."
            className="input-field"
            style={{ padding: '16px', fontSize: 16, minHeight: 120, resize: 'vertical' }}
          />
          
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={handleGeneratePlan}
              disabled={isGenerating || !issue.trim()}
              className="btn-primary"
              style={{ padding: '12px 32px' }}
            >
              {isGenerating ? 'Analyzing & Planning...' : 'Generate Implementation Plan'}
            </button>
          </div>
        </div>
      </div>

      {(plan || isGenerating) && (
        <div className="glass-card fade-in" style={{ padding: 32, borderTop: '4px solid #8b5cf6' }}>
          <div style={{ fontSize: 14, textTransform: 'uppercase', color: '#8b5cf6', fontWeight: 700, marginBottom: 20 }}>
            Implementation Plan
          </div>
          <div className="chat-markdown" style={{ background: 'transparent' }}>
            <ReactMarkdown>{plan || 'Thinking...'}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};
