#!/bin/bash
#
# Setup script to initialize the AnamneseAI project with uv
# Run this once after cloning the repository

set -e  # Exit on any error

echo "🚀 Setting up AnamneseAI project with uv..."
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   # or"
    echo "   pip install uv"
    exit 1
fi

echo "✅ uv found: $(uv --version)"
echo

# Initialize the project with uv
echo "📦 Initializing uv project..."
uv sync

echo
echo "🔧 Creating virtual environment and installing dependencies..."
# uv sync automatically creates the virtual environment and installs dependencies

echo
echo "✅ Setup complete!"
echo
echo "📋 Next steps:"
echo "   1. Make sure you have your .env file with OPENAI_API_KEY"
echo "   2. Run the application with: ./start.sh"
echo "   3. Or manually with: uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000"
echo
echo "🔧 Useful uv commands:"
echo "   uv add <package>      # Add a new dependency"
echo "   uv remove <package>   # Remove a dependency"
echo "   uv sync               # Sync dependencies"
echo "   uv run <command>      # Run a command in the virtual environment"
echo "   uv shell              # Activate the virtual environment"
echo 