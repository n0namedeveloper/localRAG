import React, { useEffect, useState, useRef } from 'react';
import { Loader } from './Loader';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
}

interface RepoInfo {
  repo_name: string;
}

export const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/api/repo/list')
      .then(res => res.json())
      .then(data => {
        if (data.repos) {
          setRepos(data.repos);
          if (data.repos.length > 0) setSelectedRepo(data.repos[0].repo_name);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedRepo) {
      const saved = localStorage.getItem(`chat_${selectedRepo}`);
      if (saved) {
        try {
          setMessages(JSON.parse(saved));
        } catch (e) {
          setMessages([]);
        }
      } else {
        setMessages([]);
      }
    }
  }, [selectedRepo]);

  useEffect(() => {
    if (selectedRepo && messages.length > 0) {
      localStorage.setItem(`chat_${selectedRepo}`, JSON.stringify(messages));
    } else if (selectedRepo && messages.length === 0) {
      localStorage.removeItem(`chat_${selectedRepo}`);
    }
  }, [messages, selectedRepo]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSend = async () => {
    if (!input.trim() || !selectedRepo) return;

    const userText = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userText }]);
    
    // Add empty assistant message placeholder
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
    setIsStreaming(true);

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userText, repo_url: selectedRepo, max_chunks: 15, stream: true }),
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
                    setMessages(prev => {
                      const newArr = [...prev];
                      newArr[newArr.length - 1].content += event.data;
                      return newArr;
                    });
                  } else if (event.event === 'sources') {
                    setMessages(prev => {
                      const newArr = [...prev];
                      newArr[newArr.length - 1].sources = event.data;
                      return newArr;
                    });
                  } else if (event.event === 'done') {
                    done = true;
                  } else if (event.event === 'error') {
                     setMessages(prev => {
                      const newArr = [...prev];
                      newArr[newArr.length - 1].content += "\n\n**Error:** " + event.data.error;
                      return newArr;
                    });
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
      setMessages(prev => {
        const newArr = [...prev];
        newArr[newArr.length - 1].content = "Error connecting to chat API.";
        return newArr;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '20px 40px', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: 20, alignItems: 'center' }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>Code Chat</h1>
        <select 
          className="input-field" 
          style={{ width: 250, padding: '8px 12px' }}
          value={selectedRepo}
          onChange={e => setSelectedRepo(e.target.value)}
        >
          {repos.length === 0 ? <option value="">No repos available</option> : null}
          {repos.map(r => (
            <option key={r.repo_name} value={r.repo_name}>{r.repo_name}</option>
          ))}
        </select>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '40px', display: 'flex', flexDirection: 'column', gap: '32px' }}>
        {messages.length === 0 ? (
          <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>💭</div>
            <h2 style={{ fontSize: 18, color: 'var(--text-primary)' }}>Ask a question about your code</h2>
            <p>Example: "How does the authentication work in this repo?"</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} style={{ 
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              width: msg.role === 'assistant' ? '100%' : 'auto'
            }}>
              {msg.role === 'user' ? (
                <div style={{ background: 'var(--accent-primary)', padding: '12px 20px', borderRadius: '16px 16px 4px 16px', fontSize: 15 }}>
                  {msg.content}
                </div>
              ) : (
                <div className="chat-markdown" style={{ background: 'transparent' }}>
                  <ReactMarkdown
                    components={{
                      code({node, inline, className, children, ...props}: any) {
                        const match = /language-(\w+)/.exec(className || '')
                        return !inline && match ? (
                          <SyntaxHighlighter
                            style={vscDarkPlus as any}
                            language={match[1]}
                            PreTag="div"
                            {...props}
                          >{String(children).replace(/\n$/, '')}</SyntaxHighlighter>
                        ) : (
                          <code className={className} {...props}>{children}</code>
                        )
                      }
                    }}
                  >
                    {msg.content || (isStreaming && i === messages.length - 1 ? '...' : '')}
                  </ReactMarkdown>
                  
                  {msg.sources && msg.sources.length > 0 && (
                    <div style={{ marginTop: 24, padding: '16px', background: 'var(--bg-card)', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                      <div style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>Sources</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {msg.sources.map((s, idx) => (
                          <div key={idx} style={{ fontSize: 13, display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ color: 'var(--text-primary)' }}>{s.file_path}</span>
                            <span style={{ color: 'var(--text-muted)' }}>Lines {s.start_line}-{s.end_line}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '24px 40px', background: 'var(--bg-secondary)', borderTop: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', gap: 12, maxWidth: 1000, margin: '0 auto' }}>
          <input
            className="input-field"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Ask about your code..."
            style={{ padding: '14px 20px', borderRadius: 24 }}
            disabled={isStreaming}
          />
          <button 
            className="btn-primary" 
            onClick={handleSend} 
            disabled={isStreaming || !input.trim() || !selectedRepo}
            style={{ borderRadius: 24, padding: '0 24px' }}
          >
            {isStreaming ? 'Thinking...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};