#!/bin/bash

# Repository Cleanup Script
# This script helps remove sensitive files from the repository

echo "🚨 Repository Security Cleanup Script"
echo "====================================="
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

echo "📋 Checking for sensitive files..."

# List of sensitive files to check
SENSITIVE_FILES=(
    ".env"
    ".env.local"
    ".env.local.backup"
    ".env.local.phase2"
    "v1_metrics.db"
    "test-frontend-deployment.html"
    "test-https-wss-complete.sh"
    "test-wss-connection.sh"
    "fix-wss-connection.sh"
    "phase2-backend-test-results.json"
    "deploy-production.sh"
    "deploy-session-fixes.sh"
    "deploy-session-fixes-proper.sh"
    "fix-kafka-topics.sh"
    "check-deployment.sh"
    "PRODUCTION_DEPLOYMENT_SECURITY_GUIDE.md"
    "FRONTEND_DEPLOYMENT_SUCCESS.md"
    "FRONTEND_DEPLOYMENT_MERGE_SUCCESS.md"
    "FRONTEND_FIX_DEPLOYMENT.md"
    "HTTPS_WSS_IMPLEMENTATION_SUCCESS.md"
    "PRODUCTION_CONFIG.md"
    "temp-media-server-deployment.yaml"
    "temp-orchestrator-deployment.yaml"
)

# List of large files to check
LARGE_FILES=(
    "test_audio_llm_fix.wav"
    "test_audio_simple_complete.wav"
    "test_audio_complete_pipeline.wav"
    "test_audio_no_kafka.wav"
    "test_audio_analysis.wav"
    "test_audio_mock.wav"
    "test_audio_debug.wav"
    "test_hello.wav"
    "test_complex_text_new.wav"
    "test_complex_text.wav"
    "test_new_tts.wav"
    "test_audio_direct.wav"
    "test_audio.wav"
)

echo "🔍 Checking for sensitive files..."
FOUND_SENSITIVE=()

for file in "${SENSITIVE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "⚠️  Found sensitive file: $file"
        FOUND_SENSITIVE+=("$file")
    fi
done

echo ""
echo "🔍 Checking for large audio files..."
FOUND_LARGE=()

for file in "${LARGE_FILES[@]}"; do
    if [ -f "$file" ]; then
        size=$(du -h "$file" | cut -f1)
        echo "📁 Found large file: $file ($size)"
        FOUND_LARGE+=("$file")
    fi
done

echo ""
echo "🔍 Checking for .wav files..."
WAV_FILES=$(find . -name "*.wav" -type f 2>/dev/null)
if [ -n "$WAV_FILES" ]; then
    echo "🎵 Found .wav files:"
    echo "$WAV_FILES"
fi

echo ""
echo "🔍 Checking for .db files..."
DB_FILES=$(find . -name "*.db" -type f 2>/dev/null)
if [ -n "$DB_FILES" ]; then
    echo "🗄️  Found .db files:"
    echo "$DB_FILES"
fi

echo ""
echo "🔍 Checking for test files..."
TEST_FILES=$(find . -name "test-*.html" -o -name "test-*.py" -o -name "test-*.js" 2>/dev/null)
if [ -n "$TEST_FILES" ]; then
    echo "🧪 Found test files:"
    echo "$TEST_FILES"
fi

echo ""
echo "====================================="
echo "📊 Summary:"
echo "Sensitive files found: ${#FOUND_SENSITIVE[@]}"
echo "Large files found: ${#FOUND_LARGE[@]}"

if [ ${#FOUND_SENSITIVE[@]} -gt 0 ] || [ ${#FOUND_LARGE[@]} -gt 0 ]; then
    echo ""
    echo "🚨 ACTION REQUIRED:"
    echo "The following files should be removed from the repository:"
    echo ""
    
    if [ ${#FOUND_SENSITIVE[@]} -gt 0 ]; then
        echo "Sensitive files:"
        for file in "${FOUND_SENSITIVE[@]}"; do
            echo "  - $file"
        done
        echo ""
    fi
    
    if [ ${#FOUND_LARGE[@]} -gt 0 ]; then
        echo "Large files:"
        for file in "${FOUND_LARGE[@]}"; do
            echo "  - $file"
        done
        echo ""
    fi
    
    echo "💡 Recommendations:"
    echo "1. Remove these files from git history using:"
    echo "   git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch <filename>' --prune-empty --tag-name-filter cat -- --all"
    echo ""
    echo "2. Update .gitignore to prevent future commits of these file types"
    echo ""
    echo "3. Rotate any exposed credentials immediately"
    echo ""
    echo "4. Consider using git-secrets or similar tools for future protection"
    
    read -p "Do you want to proceed with removing these files from git history? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 Removing files from git history..."
        
        # Create a list of files to remove
        FILES_TO_REMOVE=("${FOUND_SENSITIVE[@]}" "${FOUND_LARGE[@]}")
        
        if [ ${#FILES_TO_REMOVE[@]} -gt 0 ]; then
            # Build the git filter-branch command
            CMD="git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch"
            for file in "${FILES_TO_REMOVE[@]}"; do
                CMD="$CMD $file"
            done
            CMD="$CMD' --prune-empty --tag-name-filter cat -- --all"
            
            echo "Executing: $CMD"
            eval "$CMD"
            
            echo ""
            echo "✅ Files removed from git history"
            echo "⚠️  You need to force push to update the remote repository:"
            echo "   git push origin --force --all"
            echo "   git push origin --force --tags"
        fi
    else
        echo "❌ Cleanup cancelled"
    fi
else
    echo "✅ No sensitive or large files found!"
    echo "Your repository appears to be clean."
fi

echo ""
echo "🔒 Security Recommendations:"
echo "1. Enable GitHub security scanning"
echo "2. Use environment variables for secrets"
echo "3. Implement pre-commit hooks"
echo "4. Regular security audits"
echo "5. Monitor for exposed secrets"

echo ""
echo "📚 For more information, see SECURITY_CHECKLIST.md" 