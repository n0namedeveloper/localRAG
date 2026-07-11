import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

interface Log {
  timestamp: string;
  level: string;
  message: string;
  repo_name?: string;
  stage?: string;
}

export const Logs: React.FC = () => {
  const [logs, setLogs] = useState<Log[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let eventSource: EventSource;

    const connect = () => {
      eventSource = new EventSource('/api/logs');
      eventSource.onmessage = (event) => {
        const log: Log = JSON.parse(event.data);
        setLogs(prev => [log, ...prev]);
      };
      eventSource.onerror = () => {
        eventSource.close();
        setIsConnected(false);
      };
      setIsConnected(true);
    };

    connect();
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Logs</h1>
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 text-gray-600 hover:text-gray-800"
        >
          ← Back
        </button>
      </div>
      
      <div className="border rounded-lg overflow-hidden">
        <div className="bg-gray-100 px-4 py-2 border-b flex justify-between">
          <span className="font-medium">Real-time Logs</span>
          <span className={`text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="p-4 space-y-2 max-h-96 overflow-y-auto">
          {logs.map((log, index) => (
            <div
              key={index}
              className={`p-3 rounded border ${
                log.level === 'ERROR' ? 'border-red-500 bg-red-50' :
                log.level === 'WARNING' ? 'border-yellow-500 bg-yellow-50' :
                'border-gray-200'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className={`font-medium ${log.level === 'ERROR' ? 'text-red-600' : 
                  log.level === 'WARNING' ? 'text-yellow-600' : 'text-gray-800'}`}>
                  {log.level}
                </span>
                <span className="text-sm text-gray-500">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="text-gray-700">
                {log.repo_name ? `[${log.repo_name}] ` : ''}{log.message}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};