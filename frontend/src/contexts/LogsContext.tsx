import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

export interface Log {
  timestamp: string;
  level: string;
  message: string;
  repo_name?: string;
  stage?: string;
  logger?: string;
}

interface LogsContextType {
  logs: Log[];
  clearLogs: () => void;
}

const LogsContext = createContext<LogsContextType | undefined>(undefined);

export const LogsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [logs, setLogs] = useState<Log[]>([]);
  const evtSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Only connect once
    if (!evtSourceRef.current) {
      const evtSource = new EventSource('/api/logs/stream');
      evtSourceRef.current = evtSource;

      evtSource.onmessage = (event) => {
        try {
          const logData = JSON.parse(event.data);
          
          // Ignore SSE keep-alive pings sent from the backend
          if (logData.type === 'ping') {
            return;
          }

          setLogs(prev => {
            const newLogs = [...prev, logData as Log];
            // Keep last 1000 logs to prevent memory leak
            if (newLogs.length > 1000) return newLogs.slice(newLogs.length - 1000);
            return newLogs;
          });
        } catch (err) {
          console.error("Failed to parse log", err);
        }
      };

      evtSource.onerror = (err) => {
        console.error("SSE Error", err);
        // EventSource automatically tries to reconnect
      };
    }

    return () => {
      // We don't close the connection on unmount because we want it to live as long as the app
    };
  }, []);

  const clearLogs = () => setLogs([]);

  return (
    <LogsContext.Provider value={{ logs, clearLogs }}>
      {children}
    </LogsContext.Provider>
  );
};

export const useLogs = () => {
  const context = useContext(LogsContext);
  if (!context) throw new Error("useLogs must be used within a LogsProvider");
  return context;
};
