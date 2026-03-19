#!/usr/bin/env bash
set -euo pipefail

echo "=== LeoBook Codespace Auto-Setup (API 36) ==="

export DEBIAN_FRONTEND=noninteractive

# ---- 0. System dependencies ----
echo "[0/8] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq wget unzip curl git > /dev/null 2>&1 || true

# ---- 1. Python Dependencies ----
echo "[1/8] Installing Python dependencies..."
pip install --upgrade pip -q 2>/dev/null || true
[ -f requirements.txt ] && pip install -r requirements.txt -q || true
[ -f requirements-rl.txt ] && pip install -r requirements-rl.txt -q || true

# ---- 2. Playwright ----
echo "[2/8] Installing Playwright browsers..."
python -m playwright install-deps 2>/dev/null || true
python -m playwright install chromium 2>/dev/null || true

# ---- 3. Create Data Directories ----
echo "[3/8] Creating data directories..."
mkdir -p Data/Store/{models,Assets}
mkdir -p Data/Store/crests/{teams,leagues,flags}
mkdir -p Modules/Assets/{logos,crests}

# ---- 4. Flutter SDK ----
echo "[4/8] Installing Flutter SDK..."
FLUTTER_HOME="$HOME/flutter"
if [ ! -d "$FLUTTER_HOME" ]; then
    git clone https://github.com/flutter/flutter.git -b stable "$FLUTTER_HOME" --depth 1 2>/dev/null || true
fi

# ---- 5. Android SDK ----
echo "[5/8] Installing Android SDK..."
export ANDROID_HOME="$HOME/android-sdk"
mkdir -p "$ANDROID_HOME"

if [ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]; then
    echo "  Downloading Android SDK tools..."
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    cd /tmp
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O cmdline-tools.zip 2>/dev/null || true
    if [ -f cmdline-tools.zip ]; then
        unzip -q cmdline-tools.zip -d "$ANDROID_HOME/cmdline-tools/" 2>/dev/null || true
        mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" 2>/dev/null || true
        rm -f cmdline-tools.zip
    fi
    cd - > /dev/null
fi

# ---- 6. PATH persistence (critical for Codespaces) ----
echo "[6/8] Setting up persistent PATH..."

FLUTTER_BIN="$FLUTTER_HOME/bin"
SDK_BIN="$ANDROID_HOME/cmdline-tools/latest/bin"
PLATFORM_TOOLS="$ANDROID_HOME/platform-tools"

# Export for THIS session
export PATH="$FLUTTER_BIN:$SDK_BIN:$PLATFORM_TOOLS:$PATH"
export ANDROID_HOME

# Persist via /etc/profile.d/ (sourced by ALL login shells in Codespace)
sudo tee /etc/profile.d/leobook-env.sh > /dev/null << ENVEOF
export ANDROID_HOME="$ANDROID_HOME"
export PATH="$FLUTTER_BIN:\$SDK_BIN:\$PLATFORM_TOOLS:\$PATH"
export CHROME_EXECUTABLE="\$(which chromium 2>/dev/null || which google-chrome 2>/dev/null || echo '')"
ENVEOF
sudo chmod +x /etc/profile.d/leobook-env.sh

# Also add to .bashrc, .profile for maximum coverage
for rcfile in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.bash_profile"; do
    if ! grep -q 'flutter/bin' "$rcfile" 2>/dev/null; then
        cat >> "$rcfile" << RCEOF

# LeoBook dev environment
export ANDROID_HOME="$ANDROID_HOME"
export PATH="$FLUTTER_BIN:$SDK_BIN:$PLATFORM_TOOLS:\$PATH"
RCEOF
    fi
done

# ---- 7. Android SDK config ----
echo "[7/8] Configuring Android SDK & Flutter..."

# Accept licenses
mkdir -p "$ANDROID_HOME/licenses"
echo -e "\n24333f8a63b6825ea9c5514f83c2829b004d1fee" > "$ANDROID_HOME/licenses/android-sdk-license"
echo -e "\nd56f5187479451eabf01fb78af6dfcb131b33910" >> "$ANDROID_HOME/licenses/android-sdk-license"

# Install platform and build tools
if command -v sdkmanager &> /dev/null; then
    echo "  Installing platforms and build-tools..."
    sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0" > /dev/null 2>&1 || true
    sdkmanager "emulator" > /dev/null 2>&1 || true
fi

# Flutter config
"$FLUTTER_BIN/flutter" config --android-sdk "$ANDROID_HOME" 2>/dev/null || true
"$FLUTTER_BIN/flutter" precache 2>/dev/null || true

# Flutter app deps
if [ -d "leobookapp" ]; then
    cd leobookapp
    find . -name "build.gradle" -type f -exec sed -i 's/compileSdk .*/compileSdk 36/' {} + 2>/dev/null || true
    find . -name "build.gradle" -type f -exec sed -i 's/targetSdk .*/targetSdk 36/' {} + 2>/dev/null || true
    "$FLUTTER_BIN/flutter" pub get 2>/dev/null || true
    cd ..
fi

# ---- 8. VS Code Settings ----
echo "[8/8] Configuring VS Code..."
mkdir -p .vscode
[ ! -f .vscode/settings.json ] && cat > .vscode/settings.json << 'EOF'
{
  "python.terminal.useEnvFile": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.python",
    "editor.formatOnSave": true
  }
}
EOF

echo ""
echo "============================================"
echo "  ✓ LeoBook Setup Complete!"
echo "============================================"
echo "  Android SDK: $ANDROID_HOME"
echo "  Flutter:     $FLUTTER_HOME"
echo "  API Level:   36 (compileSdk)"
echo ""
echo "  If 'flutter' isn't found, run:"
echo "    source /etc/profile.d/leobook-env.sh"
echo ""