# iPhone Testing Guide (Without Owning an iPhone)

## Quick Overview

Your app now has comprehensive remote debugging tools. When someone tests on iPhone, they can capture and send you detailed diagnostics.

## What I Added

### 1. **Debug Panel** (Bottom-right corner of app)
   - Click "🐛 Debug" button to open full diagnostics
   - Shows device info, browser capabilities, permissions
   - Real-time console logs
   - One-click report generation

### 2. **Error Boundary**
   - Catches any React crashes
   - Shows user-friendly error screen
   - Allows copying error details
   - Stores errors in localStorage for later retrieval

### 3. **Backend Debug Endpoint**
   - `POST /api/debug/report` - Receives debug reports
   - `GET /api/debug/reports?ios_only=true` - View iOS-specific reports
   - Saves reports to `backend/debug_logs/` directory

## How to Test on iPhone (Without Owning One)

### Option 1: BrowserStack (Recommended)
**Free trial available, most realistic testing**

1. Go to https://www.browserstack.com/
2. Sign up for free trial (no credit card for first test)
3. Select "Live" → "iOS" → Choose iPhone model
4. Enter your Railway URL
5. Use built-in developer tools to see console logs

**Pros:** Real device, inspect console, screenshots
**Cons:** Limited free time

---

### Option 2: Use Remote Tester + Debug Panel
**Best for ongoing testing**

1. Have someone with iPhone visit your Railway URL
2. Ask them to click "🐛 Debug" button (bottom-right)
3. Have them test the app functionality
4. Click "Share Report" button - sends report to your backend
5. You access reports at: `https://your-railway-url.app/api/debug/reports?ios_only=true`

**Pros:** Free, real user testing, captures everything
**Cons:** Need someone with iPhone

---

### Option 3: Safari Technology Preview (Limited)
**Free, but not perfect for iOS-specific issues**

1. Download Safari Technology Preview (Mac only)
2. Enable Develop → User Agent → Safari - iOS 17 - iPhone
3. Open your Railway URL
4. Limited - doesn't catch all iOS issues

---

### Option 4: iOS Simulator (Mac only)
**Perfect for development if you have Mac**

1. Install Xcode from Mac App Store
2. Open Xcode → Open Developer Tool → Simulator
3. Choose iPhone model
4. Open Safari in simulator
5. Navigate to your Railway URL

**Pros:** Free, accurate, full debugging tools
**Cons:** Requires Mac computer

---

## Common iPhone Issues & Solutions

### Issue 1: Microphone Access Denied
**Symptom:** Debug panel shows `microphone: "denied"`

**Cause:** iPhone requires HTTPS for microphone (Railway provides this ✅)

**Fix:**
- Verify Railway URL uses `https://` (not `http://`)
- Update frontend `.env`:
  ```
  VITE_WEBSOCKET_URL=wss://your-backend.railway.app/ws/voice
  VITE_API_BASE_URL=https://your-backend.railway.app
  ```
- Note the `wss://` for WebSocket (secure)

---

### Issue 2: WebSocket Connection Fails
**Symptom:** Connection stuck on "connecting"

**Possible causes:**
1. Backend not deployed
2. CORS not configured
3. WebSocket URL incorrect

**Debug steps:**
1. Test backend health: `https://your-backend.railway.app/health`
2. Check debug panel "Test WebSocket" button
3. Look for CORS errors in console logs
4. Verify `FRONTEND_URL` in Railway environment variables matches your frontend URL

---

### Issue 3: Audio Doesn't Play
**Symptom:** Agent text appears but no audio

**Possible causes:**
1. iOS requires user interaction before audio
2. TTS service (ElevenLabs) failed
3. Audio format not supported

**Debug:**
- Debug panel will show if AudioContext is supported
- Check if `agent_text_fallback` message appears (means TTS failed)
- iOS requires first audio playback after user gesture (tap button)

---

### Issue 4: Page Won't Load
**Symptom:** Blank screen, nothing happens

**Debug with Error Boundary:**
- If React crashes, error screen appears automatically
- User can click "Copy Error Report" and send to you
- Error stored in localStorage (persists across refreshes)

**Manual debug:**
- Have tester open: Settings → Safari → Advanced → Web Inspector (requires Mac)
- Or use debug panel before crash happens

---

## Reading Debug Reports

When you receive a report (via backend or paste link), here's what to look for:

### Device Info
```json
{
  "isIOS": true,           // ← Confirms it's iPhone
  "isSafari": true,        // ← Safari has specific quirks
  "screenSize": "390x844", // ← iPhone model (e.g., iPhone 13)
  "isStandalone": false    // ← Added to home screen?
}
```

### Feature Support
```json
{
  "hasMediaDevices": true,     // ← Can access microphone
  "hasWebSocket": true,        // ← Can connect
  "hasAudioContext": true,     // ← Can play audio
  "permissions": {
    "microphone": "denied"     // ← **KEY**: Shows permission issue
  }
}
```

### Recent Errors
```json
{
  "consoleLogs": [
    "[ERROR] WebSocket connection failed",  // ← Connection issue
    "[LOG] Recording started",              // ← Microphone works
    "[WARN] AudioContext suspended"         // ← User didn't interact yet
  ]
}
```

---

## Automated Testing Script

I'll create a test script you can run from desktop browser to simulate issues:

```javascript
// Paste this in browser console to simulate common issues
(function simulateiOSIssues() {
  console.log('🧪 Starting iOS simulation tests...');
  
  // Test 1: Check if microphone available
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(() => console.log('✅ Microphone access works'))
    .catch(e => console.error('❌ Microphone failed:', e.message));
  
  // Test 2: Check WebSocket
  const ws = new WebSocket('wss://your-backend.railway.app/ws/voice');
  ws.onopen = () => { console.log('✅ WebSocket connected'); ws.close(); };
  ws.onerror = () => console.error('❌ WebSocket failed');
  
  // Test 3: Check AudioContext
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (AudioContext) {
    const ctx = new AudioContext();
    console.log('✅ AudioContext supported, state:', ctx.state);
  } else {
    console.error('❌ AudioContext not supported');
  }
})();
```

---

## Deployment Checklist for iPhone Compatibility

Before asking testers to try your app:

- [ ] Backend deployed to Railway with HTTPS
- [ ] Frontend deployed with HTTPS (or use Railway for frontend too)
- [ ] Environment variables updated:
  - [ ] `VITE_WEBSOCKET_URL=wss://...` (secure WebSocket)
  - [ ] `VITE_API_BASE_URL=https://...`
  - [ ] Backend `FRONTEND_URL` matches frontend domain
- [ ] CORS allows frontend origin in backend
- [ ] Debug panel integrated (✅ Done)
- [ ] Error boundary added (✅ Done)
- [ ] `/api/debug/report` endpoint working (✅ Done)

---

## Getting Real-Time Help

### Share Live Debug Link
1. Have tester open your app on iPhone
2. Click Debug button
3. Click "Share Report"
4. They send you the paste.ee link or you check `/api/debug/reports`

### Use Video Call + Screen Share
1. FaceTime/Zoom with iPhone user
2. Ask them to share screen
3. Watch them use the app
4. See exactly what errors appear

---

## Quick Test Commands

### Check backend health
```bash
curl https://your-backend.railway.app/health
```

### Get iOS reports
```bash
curl https://your-backend.railway.app/api/debug/reports?ios_only=true
```

### Test WebSocket (desktop)
```javascript
const ws = new WebSocket('wss://your-backend.railway.app/ws/voice');
ws.onopen = () => console.log('Connected!');
ws.onerror = (e) => console.error('Error:', e);
```

---

## Next Steps

1. **Deploy your changes:**
   ```bash
   git add .
   git commit -m "Add remote debugging for iPhone testing"
   git push origin main
   ```

2. **Update Railway environment variables** (if needed):
   - Make sure `FRONTEND_URL` is correct
   - Verify all API keys are set

3. **Test from your desktop first:**
   - Open dev tools (F12)
   - Click debug panel
   - Generate a report to verify backend endpoint works

4. **Have someone test on iPhone:**
   - Share Railway URL
   - Ask them to click Debug button
   - Review the report they generate

5. **Access reports at:** `https://your-backend.railway.app/api/debug/reports?ios_only=true`

---

## Pro Tips

### For Testers
- **First time:** Safari will ask for microphone permission - click "Allow"
- **Audio not playing:** Tap screen first (iOS requires user interaction)
- **Connection issues:** Check WiFi/cellular is working
- **Reload doesn't fix:** Clear Safari cache (Settings → Safari → Clear History)

### For You
- Check Railway logs: Dashboard → Deployments → View Logs
- Search for session IDs to trace specific user issues
- Debug reports auto-save to `backend/debug_logs/` folder
- Use `ios_only=true` parameter to filter iOS-specific issues

---

## Summary

You now have:
1. ✅ **Debug Panel** - Users can self-diagnose
2. ✅ **Error Boundary** - Catches crashes gracefully
3. ✅ **Backend Logging** - Stores reports for analysis
4. ✅ **Remote Testing Options** - 4 ways to test without iPhone

**Most practical approach:** Find someone with iPhone → Send Railway URL → Ask them to use Debug Panel → Review reports

Let me know which testing method you want to try first!
