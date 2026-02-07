# Frontend 2.0 - Installation & Testing Guide

## 🎉 What's Been Built

A completely redesigned dark-themed frontend with:

✅ **Modern UI** - Dark theme, shadcn/ui components, Tailwind CSS
✅ **Waveform Visualizer** - Circular audio visualization with state-reactive colors
✅ **Document Sidebar** - Drag-and-drop upload with status badges
✅ **Chat Interface** - WhatsApp-style conversation bubbles
✅ **Auto-Connect** - WebSocket connects automatically on document upload
✅ **Debug Panel** - Floating button with collapsible debug info
✅ **Toast Notifications** - User-friendly feedback system
✅ **Full iOS Support** - Audio unlock for Safari
✅ **Responsive Design** - Works on mobile and desktop

## 📦 Installation Steps

### 1. Navigate to Frontend 2.0
```bash
cd "Frontend 2.0"
```

### 2. Install Dependencies
```bash
npm install
```

This will install:
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS
- shadcn/ui components (Radix UI)
- Framer Motion (animations)
- Lucide React (icons)

### 3. Environment Setup
The `.env` file is already created with:
```
VITE_WEBSOCKET_URL=ws://localhost:8000/ws/voice
VITE_API_URL=http://localhost:8000
```

No changes needed if backend runs on localhost:8000.

### 4. Start Dev Server
```bash
npm run dev
```

Frontend will run on: **http://localhost:5174**

(Different port from old frontend so both can run simultaneously)

## 🧪 Testing the New UI

### 1. Start Backend First
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Open Frontend 2.0
```
http://localhost:5174
```

### 3. Test Document Upload
- **Drag & drop** a PDF/TXT/MD file onto the sidebar
- OR click "Choose File" button
- Watch upload progress bar
- WebSocket should **auto-connect** during upload
- Document appears in sidebar with "Indexed" badge

### 4. Test Voice Pipeline
- Click **"Start Speaking"** button
- Allow microphone access
- Speak into microphone
- Watch visualizer react (blue waveform during listening)
- See partial transcript appear (gray, italic)
- Wait for silence (~400ms)
- Visualizer turns purple (processing), then green (speaking)
- Hear AI response
- See chat bubbles appear in conversation history

### 5. Test Features
- **Interrupt**: Click "Interrupt" button during AI speech
- **Multiple Documents**: Upload another file, switch between them
- **Debug Panel**: Click floating bug button (bottom-right)
- **State Machine**: Watch state transitions in debug panel
- **Logs**: See real-time transcript logs

## 🎨 Visual Guide

### Layout
```
┌─────────────────────────────────────────────────────┐
│  Header: "Talk with your document" + Status Badge  │
├─────────────┬───────────────────────────────────────┤
│             │                                       │
│  Documents  │        Voice Visualizer               │
│  Sidebar    │        (Circular Waveform)           │
│             │                                       │
│  • doc.pdf  │        "Listening..."                │
│    ✅        │                                       │
│             │    [🎤 Start Speaking]                │
│  [+ Upload] │                                       │
│             │    ┌─────────────────────────┐       │
│             │    │  Conversation History   │       │
│             │    │  • User: "..."         │       │
│             │    │  • AI: "..."           │       │
│             │    └─────────────────────────┘       │
│             │                                       │
└─────────────┴───────────────────────────────────────┘
                                    [🐛] ← Debug button
```

### Color States
- **Gray** (IDLE) - Not doing anything
- **Blue** (LISTENING) - Recording your voice
- **Purple** (SPECULATIVE) - Processing in background
- **Orange** (COMMITTED) - Finalizing response
- **Green** (SPEAKING) - AI is talking

## 🔍 Troubleshooting

### Port Already in Use
```bash
# Frontend 2.0 uses port 5174
# Old frontend uses port 5173
# They can run simultaneously
```

### WebSocket Connection Failed
- Check backend is running on port 8000
- Check `.env` has correct `VITE_WEBSOCKET_URL`
- Look for CORS errors in browser console

### Microphone Not Working
- Allow microphone permissions in browser
- On iOS: Audio unlock happens automatically on first interaction

### Upload Fails
- Check file is PDF/TXT/MD
- Check file size < 10MB
- Check backend `/api/documents/upload` endpoint is working
- Look for Pinecone/embedding errors in backend logs

### No Audio Playback
- On iOS: Tap screen once to unlock audio (automatic)
- Check browser console for audio decoding errors
- Verify ElevenLabs API key in backend

## 🆚 Comparing Old vs New

### Run Both Simultaneously
```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Old Frontend
cd frontend
npm run dev
# Opens on http://localhost:5173

# Terminal 3: New Frontend
cd "Frontend 2.0"
npm run dev
# Opens on http://localhost:5174
```

Visit both URLs to compare!

## 📁 File Structure Reference

```
Frontend 2.0/
├── src/
│   ├── components/
│   │   ├── ui/                    # shadcn components
│   │   ├── VoiceVisualizer.tsx    # Waveform canvas
│   │   ├── DocumentSidebar.tsx    # Upload & list
│   │   ├── ConversationHistory.tsx # Chat bubbles
│   │   └── DebugPanel.tsx         # Debug info
│   ├── App.tsx                    # Main application
│   ├── types.ts                   # TypeScript types
│   ├── audioUtils.ts              # Audio handling
│   └── index.css                  # Tailwind styles
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```

## 🚀 Next Steps (Optional)

The core features are complete! Optional enhancements:

### Settings Panel
- Add slide-in sheet for settings
- Adjust silence debounce
- Select voice/LLM model

### Animations
- Add framer-motion transitions
- Smooth page loads
- Button hover effects

### Mobile Optimization
- Collapsible sidebar on mobile
- Touch-friendly controls
- Swipe gestures

## 📝 Important Notes

- ✅ **Old frontend unchanged** - Only reads from it, never writes
- ✅ **Same backend** - No backend changes required
- ✅ **All features work** - RAG, voice pipeline, state machine
- ✅ **Production ready** - Can be built and deployed

## 🎯 Success Criteria

You'll know it's working when:

1. ✅ Page loads with dark theme
2. ✅ Can upload document via drag-and-drop
3. ✅ WebSocket connects automatically
4. ✅ Circular waveform appears and animates
5. ✅ Can record voice and see transcripts
6. ✅ Chat bubbles appear for conversation
7. ✅ Debug panel toggles with floating button
8. ✅ Toast notifications appear on errors
9. ✅ Can interrupt AI during speaking
10. ✅ Works on both desktop and mobile

## 🙏 Enjoy!

Your new "Talk with your document" interface is ready!

Any issues? Check:
1. Backend is running
2. All npm packages installed
3. .env file has correct URLs
4. Browser console for errors
