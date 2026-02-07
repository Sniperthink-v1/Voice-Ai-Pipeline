import type { TurnState, ConnectionStatus } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

interface DebugPanelProps {
  currentState: TurnState;
  connectionStatus: ConnectionStatus;
  sessionId: string;
  logs: { timestamp: Date; type: string; content: string }[];
  onClose: () => void;
}

export default function DebugPanel({
  currentState,
  connectionStatus,
  sessionId,
  logs,
  onClose,
}: DebugPanelProps) {
  const getStateColor = (state: TurnState) => {
    switch (state) {
      case 'IDLE':
        return 'bg-idle';
      case 'LISTENING':
        return 'bg-listening';
      case 'SPECULATIVE':
        return 'bg-speculative';
      case 'COMMITTED':
        return 'bg-committed';
      case 'SPEAKING':
        return 'bg-speaking';
    }
  };

  return (
    <div className="fixed bottom-20 right-4 w-96 max-h-[600px] z-40 animate-in slide-in-from-bottom-5">
      <Card className="shadow-2xl">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-lg">Debug Panel</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-6 w-6"
          >
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connection Info */}
          <div>
            <h3 className="text-sm font-medium mb-2">Connection</h3>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <Badge
                  variant={connectionStatus === 'connected' ? 'success' : 'secondary'}
                >
                  {connectionStatus}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Session ID:</span>
                <span className="font-mono">{sessionId || 'None'}</span>
              </div>
            </div>
          </div>

          <Separator />

          {/* State Machine */}
          <div>
            <h3 className="text-sm font-medium mb-2">State Machine</h3>
            <div className="flex flex-wrap gap-2">
              {(['IDLE', 'LISTENING', 'SPECULATIVE', 'COMMITTED', 'SPEAKING'] as TurnState[]).map((state) => (
                <div
                  key={state}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    state === currentState
                      ? `${getStateColor(state)} text-white shadow-md scale-110`
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {state}
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Logs */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-sm font-medium">Logs</h3>
              <span className="text-xs text-muted-foreground">
                {logs.length} entries
              </span>
            </div>
            <ScrollArea className="flex-1 min-h-0">
              <div className="space-y-1">
                {logs.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No logs yet</p>
                ) : (
                  logs.slice(-50).reverse().map((log, index) => (
                    <div
                      key={index}
                      className="text-xs font-mono p-2 rounded bg-muted"
                    >
                      <span className="text-muted-foreground">
                        [{log.timestamp.toLocaleTimeString()}]
                      </span>{' '}
                      <span
                        className={
                          log.type === 'partial'
                            ? 'text-muted-foreground'
                            : log.type === 'final'
                            ? 'text-listening'
                            : log.type === 'agent'
                            ? 'text-speaking'
                            : 'text-committed'
                        }
                      >
                        {log.content}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
