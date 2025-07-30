#!/bin/bash

# Cursor Performance Cleanup Script
# Removes performance-killing files from the workspace

set -e

echo "🧹 Cursor Performance Cleanup Script"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if we're in the right directory
if [ ! -f "dharsan-voice-agent.code-workspace" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_info "Analyzing workspace performance..."

# Count files before cleanup
total_files_before=$(find . -type f | wc -l)
total_size_before=$(du -sh . | cut -f1)

print_info "Current workspace: $total_files_before files, $total_size_before"

# Clean up large binary files that might not be in gitignore
print_info "Removing large binary files..."
find . -name "*.onnx" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "*.bin" -type f -size +50M -exec rm -f {} \; 2>/dev/null || true
find . -name "*.model" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "*.weights" -type f -exec rm -f {} \; 2>/dev/null || true

# Clean up test audio files
print_info "Removing test audio files..."
find . -name "test_*.wav" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "test_*.mp3" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "*.wav" -type f -size +1M -exec rm -f {} \; 2>/dev/null || true

# Clean up compiled binaries
print_info "Removing compiled binaries..."
find . -name "media-server" -type f -not -path "*/cmd/*" -exec rm -f {} \; 2>/dev/null || true
find . -name "orchestrator" -type f -not -path "*/cmd/*" -exec rm -f {} \; 2>/dev/null || true
find . -name "logging-service" -type f -not -path "*/cmd/*" -exec rm -f {} \; 2>/dev/null || true
find . -name "*-amd64" -type f -exec rm -f {} \; 2>/dev/null || true

# Clean up temporary files
print_info "Removing temporary files..."
find . -name "temp-*.yaml" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "temp-*.json" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "*.tmp" -type f -exec rm -f {} \; 2>/dev/null || true
find . -name "*.temp" -type f -exec rm -f {} \; 2>/dev/null || true

# Clean up log files
print_info "Cleaning up log files..."
find . -name "*.log" -type f -size +10M -exec truncate -s 1M {} \; 2>/dev/null || true

# Clean up Python cache
print_info "Removing Python cache..."
find . -name "__pycache__" -type d -exec rm -rf {} \; 2>/dev/null || true
find . -name "*.pyc" -type f -exec rm -f {} \; 2>/dev/null || true

# Clean up Go build cache
print_info "Cleaning Go build cache..."
if command -v go &> /dev/null; then
    go clean -cache 2>/dev/null || true
    go clean -modcache 2>/dev/null || true
fi

# Clean up Node.js if present
if [ -d "Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend/node_modules" ]; then
    print_info "Cleaning Node.js cache..."
    cd Dharsan-VoiceAgent-Frontend/dharsan-voiceagent-frontend
    npm cache clean --force 2>/dev/null || true
    cd ../..
fi

# Clean up excessive documentation files (keep important ones)
print_info "Organizing documentation..."
excessive_docs=$(find . -maxdepth 1 -name "*_SUCCESS.md" -o -name "*_FIX*.md" -o -name "*_IMPLEMENTATION*.md" | wc -l)
if [ "$excessive_docs" -gt 0 ]; then
    print_warning "Found $excessive_docs excessive documentation files"
    
    # Create a docs/archive directory if it doesn't exist
    mkdir -p docs/archive
    
    # Move excessive docs to archive
    find . -maxdepth 1 -name "*_SUCCESS.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_FIX*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_IMPLEMENTATION*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_ANALYSIS*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_SUMMARY.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_TESTING*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_DEPLOYMENT*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_STATUS*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_CHECKLIST.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    find . -maxdepth 1 -name "*_LOGS*.md" -exec mv {} docs/archive/ \; 2>/dev/null || true
    
    print_success "Moved excessive documentation to docs/archive/"
fi

# Count files after cleanup
total_files_after=$(find . -type f | wc -l)
total_size_after=$(du -sh . | cut -f1)

print_success "Cleanup complete!"
echo ""
echo "📊 Performance Impact:"
echo "   Before: $total_files_before files, $total_size_before"
echo "   After:  $total_files_after files, $total_size_after"
echo "   Removed: $((total_files_before - total_files_after)) files"
echo ""

# Restart language servers
print_info "Restarting language servers..."
print_warning "Please restart Cursor after this cleanup for best performance"

# Additional recommendations
echo "🚀 Performance Tips:"
echo "   1. Restart Cursor completely: Cmd+Q (Mac) / Alt+F4 (Windows)"
echo "   2. Use workspace file: cursor dharsan-voice-agent.code-workspace"
echo "   3. Close unused tabs and split editors"
echo "   4. Disable extensions you don't need"
echo "   5. Run this cleanup script weekly"
echo ""

print_success "🎉 Your Cursor workspace should now be much faster!"