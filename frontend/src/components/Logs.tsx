import React, { useEffect, useRef } from 'react';
import { useLogs } from '../contexts/LogsContext';

export const Logs: React.FC = () => {
  const { logs } = useLogs();
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div style={{ padding: '40px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>System Logs</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>Real-time stream from ingestion pipeline</p>
      </div>
      
      <div className="glass-card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ 
          background: 'var(--bg-secondary)', 
          padding: '12px 20px', 
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Terminal</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ 
              width: 8, height: 8, borderRadius: '50%', 
              background: 'var(--status-ready)' 
            }} />
            <span style={{ color: 'var(--status-ready)' }}>
              Live Stream
            </span>
          </div>
        </div>
        
        <div style={{ 
          flex: 1, 
          overflow: 'auto', 
          background: 'var(--bg-primary)', 
          padding: '20px', 
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 13
        }}>
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Waiting for activity...</div>
          ) : (
            logs.map((log, i) => {
              const dateObj = new Date(log.timestamp);
              const timeStr = isNaN(dateObj.getTime()) ? (log.timestamp || '') : dateObj.toLocaleTimeString();
              const isErr = log.level === 'ERROR';
              const isWarn = log.level === 'WARNING';
              
              return (
                <div key={i} style={{ 
                  display: 'flex', 
                  gap: 16, 
                  marginBottom: 8, 
                  paddingBottom: 8, 
                  borderBottom: '1px solid var(--border-color)' 
                }}>
                  <span style={{ color: 'var(--text-muted)', width: 80, flexShrink: 0 }}>{timeStr}</span>
                  <span style={{ 
                    width: 60, flexShrink: 0, fontWeight: 600,
                    color: isErr ? 'var(--status-error)' : isWarn ? 'var(--status-indexing)' : 'var(--accent-primary)'
                  }}>
                    {log.level}
                  </span>
                  <span style={{ color: 'var(--text-primary)', flex: 1, wordBreak: 'break-all' }}>{log.message}</span>
                  {log.logger && (
                    <span style={{ color: 'var(--text-muted)', fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.logger}
                    </span>
                  )}
                </div>
              );
            })
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
};