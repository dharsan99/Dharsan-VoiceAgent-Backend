#!/bin/bash

# Download Llama 3 8B model using Ollama
echo "Downloading Llama 3 8B model..."
ollama pull llama3:8b

echo "Downloading Llama 3 8B model (quantized)..."
ollama pull llama3:8b:q4_0

echo "Available models:"
ollama list
