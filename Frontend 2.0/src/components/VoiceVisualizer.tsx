import { useEffect, useRef } from 'react';
import type { TurnState } from '@/types';

interface VoiceVisualizerProps {
  currentState: TurnState;
  isRecording: boolean;
  size?: 'normal' | 'small';
}

export default function VoiceVisualizer({ currentState, isRecording, size = 'normal' }: VoiceVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const barsRef = useRef<{ height: number; targetHeight: number }[]>(
    Array.from({ length: size === 'small' ? 20 : 40 }, () => ({ height: 20, targetHeight: 20 }))
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size based on prop
    const canvasSize = size === 'small' ? 48 : 300;
    canvas.width = canvasSize;
    canvas.height = canvasSize;

    const centerX = canvasSize / 2;
    const centerY = canvasSize / 2;
    const bars = barsRef.current;
    const barCount = bars.length;
    const barWidth = size === 'small' ? 2 : 4;
    const radius = size === 'small' ? 14 : 80;

    // Get color based on state
    const getStateColor = (): string => {
      switch (currentState) {
        case 'IDLE':
          return '#6b7280'; // gray
        case 'LISTENING':
          return '#3b82f6'; // blue
        case 'SPECULATIVE':
          return '#a855f7'; // purple
        case 'COMMITTED':
          return '#f59e0b'; // orange
        case 'SPEAKING':
          return '#10b981'; // green
        default:
          return '#6b7280';
      }
    };

    // Animation loop
    // Scale factor for small size
    const heightScale = size === 'small' ? 0.2 : 1;
    
    const animate = () => {
      ctx.clearRect(0, 0, canvasSize, canvasSize);

      // Update bar heights
      bars.forEach((bar) => {
        // Smooth transition to target height
        bar.height += (bar.targetHeight - bar.height) * 0.1;

        // Generate new target heights based on state
        if (Math.random() > 0.95) {
          if (currentState === 'LISTENING' && isRecording) {
            // More active in listening mode
            bar.targetHeight = (20 + Math.random() * 60) * heightScale;
          } else if (currentState === 'SPEAKING') {
            // Most active when speaking
            bar.targetHeight = (30 + Math.random() * 70) * heightScale;
          } else if (currentState === 'SPECULATIVE' || currentState === 'COMMITTED') {
            // Medium activity when processing
            bar.targetHeight = (15 + Math.random() * 40) * heightScale;
          } else {
            // Minimal activity when idle
            bar.targetHeight = (10 + Math.random() * 20) * heightScale;
          }
        }
      });

      // Draw bars in circular waveform
      const color = getStateColor();
      bars.forEach((bar, index) => {
        const angle = (index / barCount) * Math.PI * 2 - Math.PI / 2;
        const innerRadius = radius - bar.height / 2;
        const outerRadius = radius + bar.height / 2;

        const x1 = centerX + Math.cos(angle) * innerRadius;
        const y1 = centerY + Math.sin(angle) * innerRadius;
        const x2 = centerX + Math.cos(angle) * outerRadius;
        const y2 = centerY + Math.sin(angle) * outerRadius;

        // Add glow effect
        ctx.shadowBlur = 10;
        ctx.shadowColor = color;

        ctx.strokeStyle = color;
        ctx.lineWidth = barWidth;
        ctx.lineCap = 'round';

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      });

      // Draw center circle
      const centerCircleRadius = size === 'small' ? 8 : 40;
      ctx.shadowBlur = size === 'small' ? 5 : 20;
      ctx.shadowColor = color;
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.2;
      ctx.beginPath();
      ctx.arc(centerX, centerY, centerCircleRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;

      // Reset shadow
      ctx.shadowBlur = 0;

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [currentState, isRecording, size]);

  const displaySize = size === 'small' ? '48px' : '300px';

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        className="block"
        style={{ width: displaySize, height: displaySize }}
      />
    </div>
  );
}
