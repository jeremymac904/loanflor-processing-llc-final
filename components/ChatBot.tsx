import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, X, Send, Bot, Loader2, Sparkles } from 'lucide-react';
import { sendMessageToAI } from '../services/geminiService';
import { ChatMessage } from '../types';

export const ChatBot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'system',
      text: 'Welcome to LoanFlow Processing. I am the automated processing assistant. How can I clarify our workflow or services for you today?',
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      text: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const responseText = await sendMessageToAI(input);
      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'model',
        text: responseText,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      console.error(error);
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        text: "I'm having trouble connecting right now. Please call Ashley at (904) 535-1902.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-6 right-6 z-50 p-4 rounded-full shadow-[0_0_20px_rgba(198,156,109,0.4)] transition-all duration-300 hover:scale-110 flex items-center justify-center ${
          isOpen ? 'bg-red-500 rotate-90' : 'bg-brand-copper'
        }`}
      >
        {isOpen ? <X className="text-white" /> : <MessageSquare className="text-brand-dark" />}
      </button>

      {/* Chat Window */}
      <div
        className={`fixed bottom-24 right-6 w-[90vw] md:w-[400px] bg-brand-dark/95 backdrop-blur-xl border border-brand-medium rounded-2xl shadow-2xl z-50 transition-all duration-300 origin-bottom-right flex flex-col overflow-hidden ${
          isOpen ? 'opacity-100 scale-100 translate-y-0' : 'opacity-0 scale-95 translate-y-10 pointer-events-none'
        }`}
        style={{ height: 'min(500px, 70vh)' }}
      >
        {/* Header */}
        <div className="p-4 bg-brand-medium/50 border-b border-brand-medium flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-copper/20 flex items-center justify-center border border-brand-copper/50">
            <Sparkles size={16} className="text-brand-copper" />
          </div>
          <div>
            <h3 className="text-white font-bold font-serif text-sm">LoanFlow Assistant</h3>
            <p className="text-xs text-brand-copper flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
              Online
            </p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl p-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-brand-copper text-brand-dark font-medium rounded-tr-none'
                    : 'bg-brand-medium/40 text-gray-200 border border-brand-medium/50 rounded-tl-none'
                }`}
              >
                {msg.text}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-brand-medium/40 p-3 rounded-2xl rounded-tl-none flex gap-2 items-center">
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce delay-200"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 bg-brand-dark border-t border-brand-medium">
          <div className="flex items-center gap-2 bg-brand-medium/30 rounded-full px-4 py-2 border border-brand-medium/50 focus-within:border-brand-copper transition-colors">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about our processing..."
              className="flex-1 bg-transparent text-sm text-white placeholder-gray-500 focus:outline-none"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="text-brand-copper hover:text-white disabled:opacity-50 transition-colors"
            >
              {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
          <div className="text-[10px] text-gray-600 text-center mt-2">
            AI can make mistakes. Contact Ashley for critical info.
          </div>
        </div>
      </div>
    </>
  );
};