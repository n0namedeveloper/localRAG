import React, { useState, useEffect } from 'react';
import { Loader } from './Loader';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-git';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  is_code: boolean;
}

interface ChatResponse {
  answer: string;
  sources: Array<{
    file_path: string;
    start_line: number;
    end_line: number;
    snippet: string;
  }>;
}

export const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const formatCode = (code: string, language: string) => {
    return Prism.highlight(code, Prism.languages[language] || Prism.languages.python, language);
  };

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user' as const, content: input, is_code: false };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: input }),
      });

      const data: ChatResponse = await response.json();
      const assistantMessage = { 
        role: 'assistant' as const, 
        content: data.answer, 
        is_code: false 
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages(prev => [...prev, { 
        role: 'assistant' as const, 
        content: 'Sorry, there was an error processing your request.', 
        is_code: false 
      }]);
    }
    setIsStreaming(false);
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex justify-between items-center p-4 bg-gray-800 text-white">
        <h1 className="text-xl font-bold">CodeRAG Chat</h1>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl p-4 rounded-lg ${message.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'}`}>
              {message.content}
            </div>
          </div>
        ))}
        {isLoading && <Loader />}
      </div>
      
      <div className="p-4 border-t">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask your question..."
            className="flex-1 p-2 border rounded"
          />
          <button
            onClick={handleSendMessage}
            disabled={isStreaming}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};