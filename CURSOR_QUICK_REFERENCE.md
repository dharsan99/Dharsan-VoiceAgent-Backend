# Cursor Quick Reference - Dharsan Voice Agent

## 🚀 Setup Commands

```bash
# One-time setup
./setup-cursor-workspace.sh

# Open optimized workspace
cursor dharsan-voice-agent.code-workspace
```

## ⌨️ Essential Shortcuts

| Action | Shortcut | Description |
|--------|----------|-------------|
| Command Palette | `Ctrl+Shift+P` | Access all commands |
| Quick File Open | `Ctrl+P` | Open files by name |
| Run Task | `Ctrl+Shift+P` → "Tasks: Run Task" | Execute project tasks |
| Start Debugging | `F5` | Start selected debug config |
| Symbol Search | `Ctrl+T` | Find symbols across workspace |
| Go to Definition | `F12` | Navigate to code definition |
| Find References | `Shift+F12` | Find all symbol references |
| Format Document | `Shift+Alt+F` | Format current file |
| Toggle Terminal | `Ctrl+`` | Show/hide terminal |
| Multi-cursor | `Ctrl+D` | Select next occurrence |

## 🎯 Quick Tasks

### Auto-Start Development Environment
- **Open Terminals**: `Ctrl+Shift+P` → "📱 Open Development Terminals"
- **Auto-Start Full Stack**: `Ctrl+Shift+P` → "🚀 Auto-Start Development Environment"
- **Backend Only**: `Ctrl+Shift+P` → "🔧 Start Backend Services"
- **Frontend Only**: `Ctrl+Shift+P` → "🎨 Start Frontend Dev Server"

### Manual Setup
- **Script**: `./auto-start-development.sh` (opens separate Terminal windows)
- **Backend Terminal**: `source venv/bin/activate && ./start_backend_services.sh`
- **Frontend Terminal**: `cd ../Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend && nvm use v20 && npm run dev`

### Quick Commands
```bash
# Frontend development
cd Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend
npm run dev          # Start dev server
npm test            # Run tests
npm run build       # Production build

# Backend development
cd v2/orchestrator
go run main.go      # Start orchestrator

cd v2/media-server
go run cmd/server/main.go  # Start media server
```

## 🐛 Debug Configurations

| Service | Debug Config | Port |
|---------|-------------|------|
| Frontend | 🎨 Debug Frontend | 3000 |
| Orchestrator | 🔧 Debug Orchestrator | 8080 |
| Media Server | 📡 Debug Media Server | 8081 |
| Full Stack | 🚀 Full Stack Debug | Multiple |

## 📝 Code Snippets

| Trigger | Description |
|---------|-------------|
| `rva-component` | React Voice Agent component |
| `rva-hook` | Custom React hook |
| `go-handler` | Go HTTP handler with CORS |
| `py-endpoint` | Python Flask/FastAPI endpoint |
| `k8s-deployment` | Kubernetes deployment |

## 🔍 File Navigation

### Workspace Folders
- 🏠 **Root** - Scripts and config
- 🎨 **Frontend** - React app
- 🔧 **Backend V2** - Services
- 🐹 **Orchestrator** - Main coordinator
- 📡 **Media Server** - Audio handling
- ☸️ **Kubernetes** - Deployment files

### File Nesting (Auto-organized)
- `package.json` → `package-lock.json`
- `*.ts` → `*.test.ts`, `*.spec.ts`
- `Dockerfile` → `docker-compose.yml`
- `main.go` → `go.mod`, `go.sum`

## ⚙️ Settings Highlights

### Auto-formatting
- **TypeScript/React**: Prettier on save
- **Go**: goimports on save
- **Python**: Black formatter on save

### IntelliSense
- Auto-imports enabled
- Type hints displayed
- Path completion active
- Symbol suggestions enhanced

## 🔧 Problem Solving

### Common Issues
| Issue | Solution |
|-------|----------|
| Extensions not installed | `Ctrl+Shift+P` → "Show Recommended Extensions" |
| Task won't run | Check prerequisites (Node.js, Go, Python) |
| Debug not working | Verify services are running on correct ports |
| Slow performance | Restart TypeScript language server |
| Import errors | `Ctrl+Shift+P` → "TypeScript: Restart TS Server" |

### Performance Tips
- Close unused tabs
- Exclude large directories from search
- Use workspace instead of opening entire folder
- Restart language servers when needed

## 🚦 Status Indicators

### Editor Status Bar
- **Branch**: Current git branch
- **Errors**: TypeScript/ESLint errors count
- **Language**: Current file language mode
- **Encoding**: File encoding (UTF-8)
- **Line Ending**: CRLF/LF indicator

### Terminal
- Multiple terminals for different services
- Integrated terminal for quick commands
- Task-specific terminal sessions

## 📚 Quick Help

### Documentation Access
- `F1` - Help and documentation
- `Ctrl+Shift+P` → "Help: Welcome" - Getting started
- Hover over symbols for inline docs
- `Ctrl+K, Ctrl+I` - Show hover information

### Extension Commands
- `Ctrl+Shift+X` - Extensions view
- `Ctrl+Shift+G` - Source control view
- `Ctrl+Shift+E` - Explorer view
- `Ctrl+Shift+D` - Debug view

---

**💡 Pro Tip**: Use `Ctrl+Shift+P` and start typing to discover all available commands!