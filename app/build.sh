#!/usr/bin/env bash
set -o pipefail

# Desabilitar Poetry
export PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar apenas com pip
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt