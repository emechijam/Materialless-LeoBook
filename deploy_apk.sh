#!/usr/bin/env bash
# deploy_apk.sh — Build, rename, and upload LeoBook APK to Supabase Storage.
#
# Usage:
#   ./deploy_apk.sh                     # Build release APK and upload
#   ./deploy_apk.sh --skip-build        # Upload existing APK (skip build)
#
# Requirements:
#   - flutter CLI in PATH
#   - supabase CLI in PATH (or SUPABASE_ACCESS_TOKEN env var for API upload)
#   - jq (for JSON manipulation)
#
# The script:
#   1. Reads version from pubspec.yaml
#   2. Builds release APK
#   3. Renames to LeoBook-v{VERSION}.apk
#   4. Uploads APK to Supabase Storage bucket 'app-releases'
#   5. Uploads updated metadata.json

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────
SUPABASE_URL="https://jefoqzewyvscdqcpnjxu.supabase.co"
BUCKET="app-releases"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/leobookapp"
PUBSPEC="$APP_DIR/pubspec.yaml"
APK_OUTPUT="$APP_DIR/build/app/outputs/flutter-apk"

# ── Read version from pubspec.yaml ────────────────────────────────────────
VERSION=$(grep '^version:' "$PUBSPEC" | head -1 | sed 's/version: *//;s/+.*//')
if [ -z "$VERSION" ]; then
  echo "❌ Could not read version from $PUBSPEC"
  exit 1
fi
echo "📦 Version: $VERSION"

APK_NAME="LeoBook-v${VERSION}.apk"
LATEST_NAME="LeoBook-latest.apk"
PUBLIC_URL="${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/${LATEST_NAME}"

# ── Build ─────────────────────────────────────────────────────────────────
if [ "${1:-}" != "--skip-build" ]; then
  echo "🔨 Building release APK (split-per-abi)..."
  cd "$APP_DIR"
  flutter build apk --release --split-per-abi
  cd "$SCRIPT_DIR"
else
  echo "⏭  Skipping build (--skip-build)"
fi

# ── Rename ────────────────────────────────────────────────────────────────
# Prefer arm64 split APK (smaller, covers 95%+ of modern devices)
SOURCE_APK="$APK_OUTPUT/app-arm64-v8a-release.apk"
if [ ! -f "$SOURCE_APK" ]; then
  # Fallback to fat APK
  SOURCE_APK="$APK_OUTPUT/app-release.apk"
fi
if [ ! -f "$SOURCE_APK" ]; then
  echo "❌ APK not found at $APK_OUTPUT"
  exit 1
fi

APK_SIZE=$(du -h "$SOURCE_APK" | cut -f1)
cp "$SOURCE_APK" "$APK_OUTPUT/$APK_NAME"
cp "$SOURCE_APK" "$APK_OUTPUT/$LATEST_NAME"
echo "✅ Renamed → $APK_NAME ($APK_SIZE)"

# ── Load Supabase key from .env if not already set ────────────────────────
if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  ENV_FILE="$APP_DIR/.env"
  if [ -f "$ENV_FILE" ]; then
    # Extract SUPABASE_SERVICE_ROLE_KEY from .env (handles quotes and spaces)
    _KEY=$(grep -E '^SUPABASE_SERVICE_ROLE_KEY=' "$ENV_FILE" | head -1 | sed 's/^SUPABASE_SERVICE_ROLE_KEY=//' | tr -d '"' | tr -d "'" | xargs)
    if [ -n "$_KEY" ]; then
      export SUPABASE_SERVICE_ROLE_KEY="$_KEY"
      echo "🔑 Loaded service role key from .env"
    fi
  fi
fi

if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo ""
  echo "⚠️  SUPABASE_SERVICE_ROLE_KEY not found in .env or environment."
  echo "   Add it to leobookapp/.env:"
  echo "   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key"
  echo ""
  echo "   Or export it: export SUPABASE_SERVICE_ROLE_KEY='...'"
  echo ""
  exit 1
fi

# ── Ensure bucket exists (auto-create if missing) ─────────────────────────
echo "🪣 Ensuring bucket '$BUCKET' exists..."
BUCKET_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
  "${SUPABASE_URL}/storage/v1/bucket/${BUCKET}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}")

if [ "$BUCKET_CHECK" != "200" ]; then
  echo "   Creating bucket '$BUCKET'..."
  CREATE_RESP=$(curl -s -X POST \
    "${SUPABASE_URL}/storage/v1/bucket" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"${BUCKET}\", \"name\": \"${BUCKET}\", \"public\": true}")
  echo "   $CREATE_RESP"
else
  echo "   ✅ Bucket exists"
fi

# ── Upload helper ─────────────────────────────────────────────────────────
upload_file() {
  local FILE_PATH="$1"
  local DEST_NAME="$2"
  local CONTENT_TYPE="$3"
  local RESP
  RESP=$(curl -s -w "\n%{http_code}" -X POST \
    "${SUPABASE_URL}/storage/v1/object/${BUCKET}/${DEST_NAME}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: ${CONTENT_TYPE}" \
    -H "x-upsert: true" \
    --data-binary "@${FILE_PATH}")
  local HTTP_CODE
  HTTP_CODE=$(echo "$RESP" | tail -1)
  local BODY
  BODY=$(echo "$RESP" | sed '$d')
  if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ $DEST_NAME → HTTP $HTTP_CODE"
  else
    echo "   ❌ $DEST_NAME → HTTP $HTTP_CODE: $BODY"
  fi
}

# Upload APK (as LeoBook-latest.apk — stable URL)
echo "📤 Uploading APKs to Supabase..."
upload_file "$APK_OUTPUT/$LATEST_NAME" "$LATEST_NAME" "application/vnd.android.package-archive"
upload_file "$APK_OUTPUT/$APK_NAME" "$APK_NAME" "application/vnd.android.package-archive"

# ── Upload metadata.json ──────────────────────────────────────────────────
METADATA_FILE="$APK_OUTPUT/metadata.json"
cat > "$METADATA_FILE" << EOF
{
  "version": "$VERSION",
  "apk_url": "$PUBLIC_URL",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📤 Uploading metadata.json..."
upload_file "$METADATA_FILE" "metadata.json" "application/json"

echo ""
echo "✅ Deploy complete!"
echo "   Version:  $VERSION"
echo "   APK URL:  $PUBLIC_URL"
echo "   Metadata: ${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/metadata.json"

