#!/bin/bash
#
# Migration script to transition from pip-based setup to uv
# This script helps existing users migrate their project to use uv

set -e  # Exit on any error

echo "🔄 Migrating AnamneseAI project to uv..."
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ uv installed successfully"
    echo "   You may need to restart your shell or run: source ~/.bashrc"
    echo
fi

echo "✅ uv found: $(uv --version)"
echo

# Backup existing virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Backing up existing .venv directory..."
    mv .venv .venv.backup.$(date +%Y%m%d_%H%M%S)
    echo "   Backed up to .venv.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Remove old requirements.txt from backend if it exists
if [ -f "backend/requirements.txt" ]; then
    echo "🗑️  Removing old backend/requirements.txt (dependencies now in pyproject.toml)..."
    mv backend/requirements.txt backend/requirements.txt.backup
    echo "   Backed up to backend/requirements.txt.backup"
fi

echo
echo "🔧 Initializing uv project and installing dependencies..."
uv sync

echo
echo "✅ Migration complete!"
echo
echo "📋 What changed:"
echo "   ✓ Old .venv backed up (if existed)"
echo "   ✓ backend/requirements.txt backed up"
echo "   ✓ Dependencies now managed via pyproject.toml"
echo "   ✓ New virtual environment created with uv"
echo
echo "📋 Next steps:"
echo "   1. Test the application: ./start.sh"
echo "   2. If everything works, you can remove backup files"
echo "   3. Use 'uv add <package>' to add new dependencies"
echo
echo "🔧 New workflow:"
echo "   - Use: uv run <command>     # instead of activating venv"
echo "   - Use: uv add <package>     # instead of pip install"
echo "   - Use: uv sync              # to update dependencies"
echo 