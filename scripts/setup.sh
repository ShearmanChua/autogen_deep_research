#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Ensure pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo "pyenv not found. Installing pyenv..."
    curl https://pyenv.run | bash

    # Set up pyenv environment in shell
    export PATH="$HOME/.pyenv/bin:$PATH"
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"
    eval "$(pyenv virtualenv-init -)"
else
    echo "pyenv is already installed."
fi

# Load pyenv in case script is running in a fresh shell
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

PYTHON_VERSION="3.11.10"
VIRTUALENV_NAME="agent_research"

# Install Python 3.11.10 if not installed
if ! pyenv versions --bare | grep -q "^${PYTHON_VERSION}$"; then
    echo "Installing Python $PYTHON_VERSION..."
    pyenv install $PYTHON_VERSION
else
    echo "Python $PYTHON_VERSION is already installed."
fi

# Create virtualenv if it doesn't exist
if ! pyenv virtualenvs --bare | grep -q "^${VIRTUALENV_NAME}$"; then
    echo "Creating virtualenv $VIRTUALENV_NAME with Python $PYTHON_VERSION..."
    pyenv virtualenv $PYTHON_VERSION $VIRTUALENV_NAME
else
    echo "Virtualenv $VIRTUALENV_NAME already exists."
fi

# Set local pyenv to the virtualenv
pyenv local $VIRTUALENV_NAME
echo "Set local pyenv environment to $VIRTUALENV_NAME"

pip install -r requirements-dev.txt
pre-commit install

# For cross-platform collaboration
git config --global core.autocrlf true   # On Windows
git config --global core.autocrlf input  # On Linux/macOS

