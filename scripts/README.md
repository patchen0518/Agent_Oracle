# Development Scripts

This directory contains scripts to help with development workflow.

## dev-setup.sh

The main development startup script that launches both backend and frontend services.

### Usage

```bash
# From the project root directory
./scripts/dev-setup.sh
```

### What it does

1. **Pre-flight checks:**
   - Verifies you're in the correct directory
   - Checks for required configuration files
   - Creates `.env` from template if needed
   - Ensures virtual environment exists
   - Installs dependencies if missing
   - Verifies ports 8000 and 5173 are available

2. **Starts services:**
   - Backend: FastAPI server on http://localhost:8000
   - Frontend: Vite dev server on http://localhost:5173

3. **Monitoring:**
   - Logs output to `logs/backend.log` and `logs/frontend.log`
   - Monitors both processes for crashes
   - Provides health check status

4. **Cleanup:**
   - Gracefully stops both services when you press Ctrl+C
   - Kills any remaining processes

### Features

- ✅ Colored output for better readability
- ✅ Automatic dependency installation
- ✅ Port conflict detection
- ✅ Health checks
- ✅ Process monitoring
- ✅ Graceful shutdown
- ✅ Detailed logging
- ✅ Error handling

### Requirements

- `uv` (Python package manager)
- `npm` (Node.js package manager)
- `curl` (for health checks)
- `lsof` (for port checking)

### Troubleshooting

If the script fails:

1. **Check logs:**
   ```bash
   tail -f logs/backend.log
   tail -f logs/frontend.log
   ```

2. **Manual cleanup:**
   ```bash
   pkill -f "uvicorn main:app"
   pkill -f "vite"
   ```

3. **Port conflicts:**
   ```bash
   lsof -i :8000  # Check what's using port 8000
   lsof -i :5173  # Check what's using port 5173
   ```

4. **Missing API key:**
   - Edit `backend/.env`
   - Add your Gemini API key: `GEMINI_API_KEY=your_key_here`
   - Get key from: https://aistudio.google.com/app/apikey