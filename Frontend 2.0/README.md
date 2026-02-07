# Voice AI Pipeline - Frontend 2.0

Modern, redesigned frontend for the Voice AI Pipeline with dark theme and enhanced UX.

## 🎨 Features

- **Dark Theme** - Easy on the eyes, modern aesthetic
- **Waveform Visualizer** - Real-time circular audio visualization
- **Document Management** - Drag-and-drop upload with RAG integration
- **Chat Interface** - WhatsApp-style conversation bubbles
- **Auto-Connect** - Seamless WebSocket connection on document upload
- **Debug Panel** - Collapsible debug info (floating button)
- **Toast Notifications** - User-friendly error/success messages
- **Responsive Design** - Works on desktop and mobile
- **iOS Audio Support** - Full iOS Safari audio unlock handling

## 🚀 Quick Start

### Installation

```bash
cd "Frontend 2.0"
npm install
```

### Development

Create `.env` file:
```bash
cp .env.example .env
```

Edit `.env` if needed:
```
VITE_WEBSOCKET_URL=ws://localhost:8000/ws/voice
VITE_API_URL=http://localhost:8000
```

Run dev server:
```bash
npm run dev
```

Frontend will run on **http://localhost:5174** (different port from old frontend)

### Production Build

```bash
npm run build
npm run preview
```

## 📁 Project Structure

```
Frontend 2.0/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── toast.tsx
│   │   │   └── toaster.tsx
│   │   ├── VoiceVisualizer.tsx    # Waveform animation
│   │   ├── DocumentSidebar.tsx     # Upload & document list
│   │   ├── ConversationHistory.tsx # Chat bubbles
│   │   └── DebugPanel.tsx          # Debug info panel
│   ├── lib/
│   │   └── utils.ts         # Utility functions (cn)
│   ├── App.tsx              # Main application
│   ├── main.tsx             # React entry point
│   ├── types.ts             # TypeScript types
│   ├── audioUtils.ts        # Audio recording/playback
│   └── index.css            # Global styles (Tailwind)
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

## 🎯 Key Components

### VoiceVisualizer
- Canvas-based circular waveform
- State-reactive colors (IDLE/LISTENING/SPECULATIVE/COMMITTED/SPEAKING)
- Smooth animations with requestAnimationFrame

### DocumentSidebar
- Drag-and-drop file upload
- Status badges (indexed/processing/failed)
- Active document highlighting
- Auto-connect on successful upload

### ConversationHistory
- WhatsApp-style chat bubbles
- User messages (right, blue)
- AI responses (left, green/card)
- Partial transcript display (italic, bordered)
- Auto-scroll to latest message

### DebugPanel
- Floating button at bottom-right
- Connection status & session ID
- State machine visualization
- Real-time logs (last 50 entries)
- Collapsible for clean UI

## 🔧 Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **shadcn/ui** - Component library (Radix UI primitives)
- **Framer Motion** - Animations
- **Lucide React** - Icons

## 🎨 Design System

### Colors (Voice States)
```css
IDLE:        #6b7280 (gray)
LISTENING:   #3b82f6 (blue)
SPECULATIVE: #a855f7 (purple)
COMMITTED:   #f59e0b (orange)
SPEAKING:    #10b981 (green)
```

### Theme
- Background: `#0a0a0a` (near black)
- Card: `#1a1a1a` (dark gray)
- Border: `#2a2a2a` (subtle)
- Text Primary: `#f9fafb` (white)
- Text Secondary: `#9ca3af` (muted gray)

## 🔌 Backend Integration

Connects to existing Voice AI Pipeline backend:
- WebSocket: `/ws/voice` (real-time audio/transcription)
- REST API: `/api/documents/upload` (document RAG)

No backend changes required - fully compatible with existing API.

## 📱 Mobile Support

- Touch-friendly buttons (larger hit areas)
- Responsive layout (sidebar collapses on mobile)
- iOS audio unlock handling
- Mobile-optimized controls

## 🐛 Debugging

Toggle debug panel with floating button (bottom-right).

Shows:
- WebSocket connection status
- Current session ID
- State machine transitions
- Transcript logs (partial/final/agent/state)

## 🆚 Differences from Old Frontend

| Feature | Old | New |
|---------|-----|-----|
| Theme | Light | Dark |
| Connect Button | Manual | Auto (on upload) |
| Transcripts | Logs only | Chat bubbles + logs |
| State Display | Pills | Animated visualizer |
| Documents | Hidden upload | Sidebar with list |
| Debug | Always visible | Floating button |
| Styling | Inline CSS | Tailwind + shadcn |
| Animations | None | Framer Motion |

## 📝 Notes

- **Never modifies old `frontend/` folder** - completely separate
- Runs on different port (5174) to avoid conflicts
- Can run both frontends simultaneously
- Uses same backend APIs (no changes needed)
- All existing features preserved (RAG, voice pipeline, state machine)

## 🚀 Deployment

Build for production:
```bash
npm run build
```

Output in `dist/` folder - deploy to any static host (Vercel, Netlify, Railway, etc.)

Environment variables for production:
```
VITE_WEBSOCKET_URL=wss://your-backend.com/ws/voice
VITE_API_URL=https://your-backend.com
```
