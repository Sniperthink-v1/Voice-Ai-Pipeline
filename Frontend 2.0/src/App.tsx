import { useState, useEffect, useRef } from 'react';
import type { TurnState, ConnectionStatus, ServerMessage, Document, ConversationMessage } from './types';
import { AudioRecorder, AudioPlayer, float32ToInt16Base64 } from './audioUtils';
import { Toaster } from './components/ui/toaster';
import { useToast } from './components/ui/use-toast';
import VoiceVisualizer from './components/VoiceVisualizer';
import DocumentSidebar from './components/DocumentSidebar';
import ConversationHistory from './components/ConversationHistory';
import DebugPanel from './components/DebugPanel';
import { Button } from './components/ui/button';
import { Mic, MicOff, Hand, Bug } from 'lucide-react';

function App() {
  // Connection & State
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [currentState, setCurrentState] = useState<TurnState>('IDLE');
  const [sessionId, setSessionId] = useState<string>('');
  
  // Voice Recording
  const [isRecording, setIsRecording] = useState(false);
  const [audioUnlocked, setAudioUnlocked] = useState(false);
  
  // Conversation
  const [conversationHistory, setConversationHistory] = useState<ConversationMessage[]>([]);
  const [partialTranscript, setPartialTranscript] = useState('');
  const lastAgentMessageRef = useRef<string>('');
  const lastUserMessageRef = useRef<string>('');
  
  // Ball animation: container shrinks, ball relocates to corner when container too small
  // Container height shrinks based on message count, ball stays same size
  // At 4+ messages: ball moves to floating position in top-right corner
  const messageCount = conversationHistory.length;
  const isBallFloating = messageCount >= 4; // Ball moves to corner at 4+ messages
  
  // Container height decreases as messages increase (for first 4 messages)
  const getContainerHeight = () => {
    if (messageCount === 0) return 'flex-1 p-8'; // Full height with padding
    if (messageCount === 1) return 'h-80 p-8'; // 320px
    if (messageCount === 2) return 'h-56 p-6'; // 224px
    if (messageCount === 3) return 'h-32 p-4'; // 128px
    return 'h-0 p-0'; // Collapsed - no height, no padding
  };
  
  // Documents
  const [documents, setDocuments] = useState<Document[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  
  // Error & Debug
  const [error, setError] = useState<string>('');
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const [debugLogs, setDebugLogs] = useState<{timestamp: Date, type: string, content: string}[]>([]);
  
  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<AudioRecorder | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  
  const { toast } = useToast();
  
  // WebSocket URL from environment
  const wsUrl = import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000/ws/voice';
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  // Initialize audio player
  useEffect(() => {
    playerRef.current = new AudioPlayer();
    
    // Set callback for when audio playback completes
    playerRef.current.setOnComplete(() => {
      console.log('Audio playback complete - notifying backend');
      wsRef.current?.send(JSON.stringify({
        type: 'playback_complete',
        data: {
          timestamp: Date.now(),
        },
      }));
    });
    
    return () => {
      playerRef.current?.stop();
    };
  }, []);
  
  // Auto-connect on page load
  useEffect(() => {
    handleConnect();
  }, []);
  
  // Unlock audio on iOS with user interaction
  const unlockAudio = async () => {
    if (audioUnlocked) return;
    
    try {
      if (playerRef.current) {
        await playerRef.current.unlockIOSAudio();
      }
      console.log('✅ iOS Audio unlocked successfully');
      setAudioUnlocked(true);
    } catch (e) {
      console.warn('⚠️ Audio unlock failed:', e);
      setAudioUnlocked(true);
    }
  };
  
  const handleConnect = () => {
    // Unlock audio on iOS first
    unlockAudio();
    
    setConnectionStatus('connecting');
    setError('');
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
      
      // Send connect message
      ws.send(JSON.stringify({
        type: 'connect',
        data: {}
      }));
      
      toast({
        title: "Connected",
        description: "Voice pipeline ready. Start speaking!",
      });
    };

    ws.onmessage = (event) => {
      const message: ServerMessage = JSON.parse(event.data);
      console.log('>>> RECV:', message.type);

      switch (message.type) {
        case 'session_ready':
          setSessionId(message.data.session_id);
          console.log('Session ready:', message.data.session_id);
          break;
        
        case 'state_change':
          const fromState = message.data.from_state;
          const toState = message.data.to_state;
          setCurrentState(toState);
          console.log('State:', fromState, '->', toState);
          
          addDebugLog('state', `State: ${fromState} → ${toState}`);
          
          // If transitioning from SPEAKING to LISTENING, user interrupted - stop audio
          if (fromState === 'SPEAKING' && toState === 'LISTENING') {
            console.log('User interrupted - stopping audio playback');
            playerRef.current?.stop();
          }
          
          // Clear transcripts when a new turn starts
          if (fromState === 'IDLE' && toState === 'LISTENING') {
            setPartialTranscript('');
          }
          break;
        
        case 'transcript_partial':
          setPartialTranscript(message.data.text);
          addDebugLog('partial', message.data.text);
          break;
        
        case 'transcript_final':
          const finalText = message.data.text;
          setPartialTranscript('');
          
          // Add user message to conversation history (dedupe by comparing to last message)
          if (finalText !== lastUserMessageRef.current) {
            lastUserMessageRef.current = finalText;
            const userMsg: ConversationMessage = {
              id: Date.now().toString(),
              role: 'user',
              text: finalText,
              timestamp: Date.now(),
            };
            setConversationHistory(prev => [...prev, userMsg]);
          }
          
          addDebugLog('final', `[FINAL] ${finalText}`);
          break;
        
        case 'agent_audio_chunk':
          console.log(`🔊 AUDIO CHUNK #${message.data.chunk_index} final=${message.data.is_final}`);
          if (message.data.chunk_index === 0) {
            console.log('🔊 Resetting audio stream');
            playerRef.current?.resetStream();
          }
          if (message.data.audio && !message.data.is_final) {
            playerRef.current?.addChunk(message.data.audio);
          }
          if (message.data.is_final) {
            console.log('🔊 FINALIZE - starting playback');
            playerRef.current?.finalize();
          }
          break;
        
        case 'agent_text_fallback':
          setError(`TTS failed: ${message.data.reason}`);
          
          // Add agent message only if TTS failed (dedupe by text)
          if (message.data.text !== lastAgentMessageRef.current) {
            lastAgentMessageRef.current = message.data.text;
            const fallbackMsg: ConversationMessage = {
              id: Date.now().toString(),
              role: 'agent',
              text: message.data.text,
              timestamp: Date.now(),
            };
            setConversationHistory(prev => [...prev, fallbackMsg]);
          }
          addDebugLog('agent', `[FALLBACK] ${message.data.text}`);
          break;
        
        case 'turn_complete':
          console.log('Turn complete:', message.data);
          
          // Only add to history if different from last agent message (prevents duplicates)
          if (message.data.agent_text !== lastAgentMessageRef.current) {
            lastAgentMessageRef.current = message.data.agent_text;
            
            const agentMsg: ConversationMessage = {
              id: Date.now().toString(),
              role: 'agent',
              text: message.data.agent_text,
              timestamp: Date.now(),
            };
            setConversationHistory(prev => [...prev, agentMsg]);
            addDebugLog('agent', `[AGENT] ${message.data.agent_text}`);
          }
          break;
        
        case 'error':
          console.error('Error:', message.data.message);
          setError(message.data.message);
          toast({
            variant: "destructive",
            title: "Error",
            description: message.data.message,
          });
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('disconnected');
      setError('WebSocket connection failed');
      toast({
        variant: "destructive",
        title: "Connection Failed",
        description: "Could not connect to voice server",
      });
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');
      setSessionId('');
      handleStopRecording();
      toast({
        title: "Disconnected",
        description: "Connection to voice server closed",
      });
    };
  };
  
  const handleStartRecording = async () => {
    console.log('🎤 handleStartRecording called');
    
    // Unlock audio on iOS first
    try {
      await unlockAudio();
      console.log('🎤 unlockAudio completed');
    } catch (e) {
      console.error('🎤 unlockAudio failed:', e);
    }
    
    if (!wsRef.current || connectionStatus !== 'connected') {
      const msg = !wsRef.current ? 'Not connected' : 'Connection not ready';
      console.error('🎤 Cannot start recording:', msg);
      setError(msg);
      toast({
        variant: "destructive",
        title: "Cannot Record",
        description: msg,
      });
      return;
    }

    try {
      console.log('🎤 Creating AudioRecorder...');
      const recorder = new AudioRecorder();
      recorderRef.current = recorder;

      let chunkCount = 0;
      console.log('🎤 Starting recorder...');
      await recorder.start((audioData: Float32Array) => {
        // Convert to base64 PCM and send to backend
        const audioBase64 = float32ToInt16Base64(audioData);
        chunkCount++;
        // Only log every 20th chunk to reduce noise
        if (chunkCount % 20 === 1) {
          console.log(`[MIC] Chunk #${chunkCount} sent`);
        }
        
        wsRef.current?.send(JSON.stringify({
          type: 'audio_chunk',
          data: {
            audio: audioBase64,
            format: 'pcm',
            sample_rate: 16000,
          },
        }));
      });

      setIsRecording(true);
      setError('');
      console.log('🎤 Recording started successfully');
    } catch (err) {
      console.error('🎤 Failed to start recording:', err);
      setError(`Microphone access denied: ${(err as Error).message}`);
      toast({
        variant: "destructive",
        title: "Microphone Error",
        description: "Could not access microphone",
      });
    }
  };

  const handleStopRecording = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setIsRecording(false);
    console.log('Recording stopped');
  };

  const handleInterrupt = () => {
    // Stop agent audio
    playerRef.current?.stop();
    
    // Send interrupt message
    wsRef.current?.send(JSON.stringify({
      type: 'interrupt',
      data: {
        timestamp: Date.now(),
      },
    }));
    
    console.log('Interrupted agent');
    toast({
      title: "Interrupted",
      description: "Agent stopped speaking",
    });
  };

  const addDebugLog = (type: string, content: string) => {
    setDebugLogs(prev => [...prev, { timestamp: new Date(), type, content }]);
  };
  
  const getStatusText = () => {
    if (connectionStatus === 'connecting') {
      return 'Connecting to voice pipeline...';
    }
    
    if (documents.length === 0) {
      return 'Upload a document to get started';
    }
    
    const hasProcessedDoc = documents.some(d => d.status === 'indexed');
    if (!hasProcessedDoc) {
      return 'Processing document...';
    }
    
    switch (currentState) {
      case 'IDLE':
        return 'Ready - Click "Start Speaking"';
      case 'LISTENING':
        return 'Listening...';
      case 'SPECULATIVE':
        return 'Processing...';
      case 'COMMITTED':
        return 'Generating response...';
      case 'SPEAKING':
        return 'Speaking...';
      default:
        return 'Idle';
    }
  };

  const getStatusIcon = () => {
    switch (currentState) {
      case 'LISTENING':
        return '🎤';
      case 'SPECULATIVE':
      case 'COMMITTED':
        return '⏱️';
      case 'SPEAKING':
        return '🤖';
      default:
        return '⚪';
    }
  };

  // Auto-connect when document is uploaded
  const handleDocumentUploaded = async (doc: Document) => {
    setDocuments(prev => [...prev, doc]);
    setActiveDocumentId(doc.id);
    
    // Auto-connect if not already connected
    if (connectionStatus === 'disconnected') {
      handleConnect();
    }
    
    toast({
      title: "Document Ready",
      description: `${doc.filename} is ready. Start speaking!`,
    });
  };

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Document Sidebar */}
      <DocumentSidebar
        documents={documents}
        activeDocumentId={activeDocumentId}
        sessionId={sessionId}
        connectionStatus={connectionStatus}
        apiUrl={apiUrl}
        onDocumentUploaded={handleDocumentUploaded}
        onDocumentSelect={setActiveDocumentId}
        onConnect={handleConnect}
        onError={(msg) => {
          setError(msg);
          toast({
            variant: "destructive",
            title: "Error",
            description: msg,
          });
        }}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {/* Header */}
        <header className="border-b border-border p-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Talk with your document</h1>
            <p className="text-sm text-muted-foreground">
              Upload a document and have a conversation about it
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              connectionStatus === 'connected' ? 'bg-speaking text-white' :
              connectionStatus === 'connecting' ? 'bg-committed text-white' :
              'bg-muted text-muted-foreground'
            }`}>
              {connectionStatus === 'connected' ? '● Connected' : 
               connectionStatus === 'connecting' ? '○ Connecting...' : 
               '○ Disconnected'}
            </div>
            
            {/* Floating Ball - appears when isBallFloating */}
            {isBallFloating && (
              <div className="ml-3">
                <VoiceVisualizer
                  currentState={currentState}
                  isRecording={isRecording}
                  size="small"
                />
              </div>
            )}
          </div>
        </header>

        {/* Voice Interface Container - shrinks as messages increase */}
        <div className={`flex flex-col items-center justify-center transition-all duration-500 ease-in-out overflow-y-auto overflow-x-hidden ${getContainerHeight()}`}>
          {/* Visualizer - only show here when NOT floating */}
          {!isBallFloating && (
            <div className="transition-all duration-500 ease-in-out flex-shrink-0">
              <VoiceVisualizer
                currentState={currentState}
                isRecording={isRecording}
              />
            </div>
          )}

          {/* Status - only show when ball is in container */}
          {!isBallFloating && (
            <div className="text-center mt-4 flex-shrink-0">
              <div className="font-medium flex items-center justify-center gap-2 text-lg">
                <span>{getStatusIcon()}</span>
                <span>{getStatusText()}</span>
              </div>
              {partialTranscript && (
                <p className="text-sm text-muted-foreground italic mt-2">
                  {partialTranscript}
                </p>
              )}
            </div>
          )}

          {/* Control Buttons - only show when ball is in container */}
          {!isBallFloating && (
            <div className="flex items-center gap-4 mt-4 flex-shrink-0 pb-4">
            {!isRecording ? (
              <Button
                size="lg"
                onClick={handleStartRecording}
                disabled={
                  connectionStatus !== 'connected' ||
                  documents.length === 0 ||
                  !documents.some(d => d.status === 'indexed')
                }
                className="gap-2"
              >
                <Mic className="w-5 h-5" />
                Start Speaking
              </Button>
            ) : (
              <Button
                size="lg"
                variant="destructive"
                onClick={handleStopRecording}
                className="gap-2"
              >
                <MicOff className="w-5 h-5" />
                Stop Speaking
              </Button>
            )}
            
            {currentState === 'SPEAKING' && (
              <Button
                size="lg"
                variant="outline"
                onClick={handleInterrupt}
                className="gap-2"
              >
                <Hand className="w-5 h-5" />
                Interrupt
              </Button>
            )}
          </div>
          )}

          {/* Error Display */}
          {error && !isBallFloating && (
            <div className="bg-destructive/10 border border-destructive text-destructive rounded-lg p-4 max-w-md mt-4">
              <strong>Error:</strong> {error}
            </div>
          )}
        </div>

        {/* Floating Controls Bar - appears when ball is floating */}
        {isBallFloating && (
          <div className="flex items-center justify-center gap-4 px-8 py-3 border-b border-border bg-card/50">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{getStatusIcon()}</span>
              <span>{getStatusText()}</span>
            </div>
            {partialTranscript && (
              <p className="text-sm text-muted-foreground italic">
                {partialTranscript}
              </p>
            )}
            <div className="flex items-center gap-2">
              {!isRecording ? (
                <Button
                  size="sm"
                  onClick={handleStartRecording}
                  disabled={
                    connectionStatus !== 'connected' ||
                    documents.length === 0 ||
                    !documents.some(d => d.status === 'indexed')
                  }
                  className="gap-1"
                >
                  <Mic className="w-4 h-4" />
                  Speak
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleStopRecording}
                  className="gap-1"
                >
                  <MicOff className="w-4 h-4" />
                  Stop
                </Button>
              )}
              {currentState === 'SPEAKING' && (
                <Button size="sm" variant="outline" onClick={handleInterrupt} className="gap-1">
                  <Hand className="w-4 h-4" />
                  Stop AI
                </Button>
              )}
            </div>
            {error && (
              <span className="text-sm text-destructive">{error}</span>
            )}
          </div>
        )}

        {/* Conversation History - grows as ball container shrinks */}
        <div
          className={`min-h-0 border-t border-border flex flex-col overflow-hidden transition-all duration-500 ease-in-out ${
            messageCount === 0 ? 'h-0 border-t-0' : 'flex-1'
          }`}
        >
          <ConversationHistory
            messages={conversationHistory}
            partialTranscript={partialTranscript}
          />
        </div>
      </main>

      {/* Floating Debug Button */}
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          variant="outline"
          size="icon"
          onClick={() => setShowDebugPanel(!showDebugPanel)}
          className="rounded-full shadow-lg"
        >
          <Bug className="w-5 h-5" />
        </Button>
      </div>

      {/* Debug Panel */}
      {showDebugPanel && (
        <DebugPanel
          currentState={currentState}
          connectionStatus={connectionStatus}
          sessionId={sessionId}
          logs={debugLogs}
          onClose={() => setShowDebugPanel(false)}
        />
      )}

      {/* Toast Notifications */}
      <Toaster />
    </div>
  );
}

export default App;
