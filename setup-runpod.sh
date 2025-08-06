#!/bin/bash

echo "🚀 Setting up Runpod configuration..."

# Check if .env already exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists. Backing up to .env.backup"
    cp .env .env.backup
fi

# Copy Runpod example to .env
cp .env.runpod.example .env

echo "📝 Please edit .env file and add your Runpod configuration:"
echo ""
echo "Required settings:"
echo "  - RUNPOD_API_KEY: Your Runpod API key"
echo "  - AUTH_PASSWORD: Password for frontend login"
echo "  - JWT_SECRET: A secure random string"
echo ""
echo "Optional settings:"
echo "  - RUNPOD_POD_ID: Existing pod ID (if you have one)"
echo "  - RUNPOD_TEMPLATE_ID: Template to create new pods"
echo ""
echo "After editing .env, run:"
echo "  docker-compose -f docker-compose.runpod.yml up -d"
echo ""
echo "To stop the old GCE system (if running):"
echo "  docker-compose down"