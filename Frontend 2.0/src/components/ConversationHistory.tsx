import { useEffect, useRef, useCallback } from 'react';
import type { ConversationMessage } from '@/types';
import { ScrollArea } from '@/components/ui/scroll-area';
import { User, Bot } from 'lucide-react';

interface ConversationHistoryProps {
  messages: ConversationMessage[];
  partialTranscript?: string;
}

export default function ConversationHistory({ messages, partialTranscript }: ConversationHistoryProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    // Radix ScrollArea renders a [data-radix-scroll-area-viewport] child
    // which is the actual scrollable container
    const viewport = scrollAreaRef.current?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null;
    if (viewport) {
      requestAnimationFrame(() => {
        viewport.scrollTo({
          top: viewport.scrollHeight,
          behavior: 'smooth',
        });
      });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, partialTranscript, scrollToBottom]);

  if (messages.length === 0 && !partialTranscript) {
    return (
      <div className="h-48 flex items-center justify-center text-muted-foreground">
        <p className="text-sm">No conversation yet. Start speaking!</p>
      </div>
    );
  }

  return (
    <ScrollArea ref={scrollAreaRef} className="h-full">
      <div className="p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role === 'agent' && (
              <div className="w-8 h-8 rounded-full bg-speaking flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-white" />
              </div>
            )}
            
            <div
              className={`max-w-[70%] rounded-lg p-3 ${
                message.role === 'user'
                  ? 'bg-listening text-white'
                  : 'bg-card border border-border'
              }`}
            >
              <p className="text-sm">{message.text}</p>
              <p className="text-xs mt-1 opacity-70">
                {new Date(message.timestamp).toLocaleTimeString()}
              </p>
            </div>

            {message.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-listening flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-white" />
              </div>
            )}
          </div>
        ))}

        {/* Partial transcript */}
        {partialTranscript && (
          <div className="flex gap-3 justify-end">
            <div className="max-w-[70%] rounded-lg p-3 bg-listening/50 border-2 border-listening">
              <p className="text-sm italic text-white">{partialTranscript}</p>
              <p className="text-xs mt-1 opacity-70 text-white">typing...</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-listening flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-white" />
            </div>
          </div>
        )}

      </div>
    </ScrollArea>
  );
}
