import React, { useEffect, useState } from 'react';

export const Settings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState({
    llm_provider: 'deepseek',
    ollama_base_url: 'http://host.docker.internal:11434',
    ollama_model: 'llama3',
    deepseek_api_key: '',
    deepseek_model: 'deepseek-chat',
  });
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/settings')
      .then(res => res.json())
      .then(data => {
        setConfig(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        setMessage('Settings saved successfully!');
      } else {
        setMessage('Failed to save settings.');
      }
    } catch (err) {
      setMessage('Error saving settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 40, color: 'var(--text-muted)' }}>Loading settings...</div>;
  }

  return (
    <div style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)' }}>Settings</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 32 }}>
        Configure the language model provider for localRAG. You can switch between cloud providers (DeepSeek) and fully private local models (Ollama).
      </p>

      {message && (
        <div style={{ 
          padding: 16, 
          marginBottom: 24, 
          borderRadius: 8, 
          background: message.includes('success') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          color: message.includes('success') ? '#10b981' : '#ef4444',
          border: `1px solid ${message.includes('success') ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`
        }}>
          {message}
        </div>
      )}

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
        <div className="glass-card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>LLM Provider</h2>
          
          <div style={{ display: 'flex', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input 
                type="radio" 
                name="provider" 
                value="deepseek" 
                checked={config.llm_provider === 'deepseek'}
                onChange={(e) => setConfig({ ...config, llm_provider: e.target.value })}
              />
              <span style={{ color: 'var(--text-primary)' }}>DeepSeek (Cloud)</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input 
                type="radio" 
                name="provider" 
                value="ollama" 
                checked={config.llm_provider === 'ollama'}
                onChange={(e) => setConfig({ ...config, llm_provider: e.target.value })}
              />
              <span style={{ color: 'var(--text-primary)' }}>Ollama (Local)</span>
            </label>
          </div>
        </div>

        {config.llm_provider === 'deepseek' && (
          <div className="glass-card fade-in" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>DeepSeek Configuration</h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: 'var(--text-secondary)' }}>API Key (leave blank to use .env)</label>
              <input 
                type="password" 
                className="search-input" 
                value={config.deepseek_api_key}
                onChange={(e) => setConfig({ ...config, deepseek_api_key: e.target.value })}
                placeholder="sk-..."
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Model</label>
              <input 
                type="text" 
                className="search-input" 
                value={config.deepseek_model}
                onChange={(e) => setConfig({ ...config, deepseek_model: e.target.value })}
              />
            </div>
          </div>
        )}

        {config.llm_provider === 'ollama' && (
          <div className="glass-card fade-in" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>Ollama Configuration</h2>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>
              Ensure Ollama is running and accessible. Use <code>http://host.docker.internal:11434</code> if running localRAG in Docker and Ollama on your host.
            </p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Base URL</label>
              <input 
                type="text" 
                className="search-input" 
                value={config.ollama_base_url}
                onChange={(e) => setConfig({ ...config, ollama_base_url: e.target.value })}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Model Name</label>
              <input 
                type="text" 
                className="search-input" 
                value={config.ollama_model}
                onChange={(e) => setConfig({ ...config, ollama_model: e.target.value })}
                placeholder="llama3, qwen2.5-coder, etc."
              />
            </div>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button type="submit" className="btn-primary" disabled={saving} style={{ width: 150, justifyContent: 'center' }}>
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
};
