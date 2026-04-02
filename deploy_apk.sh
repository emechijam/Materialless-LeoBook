#!/usr/bin/env bash
# Build, verify, and upload the LeoBook Android APK to Supabase Storage.
#
# Usage:
#   ./deploy_apk.sh
#   ./deploy_apk.sh --skip-build

set -euo pipefail

SUPABASE_URL="https://jefoqzewyvscdqcpnjxu.supabase.co"
BUCKET="app-releases"
EXPECTED_APPLICATION_ID="com.materialless.leobookapp"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/leobookapp"
ANDROID_DIR="$APP_DIR/android"
PUBSPEC="$APP_DIR/pubspec.yaml"
APK_OUTPUT="$APP_DIR/build/app/outputs/flutter-apk"
KEY_PROPERTIES_FILE="$ANDROID_DIR/key.properties"
LOCAL_PROPERTIES_FILE="$ANDROID_DIR/local.properties"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' is required but not available in PATH."
    exit 1
  fi
}

read_local_property() {
  local key="$1"
  if [ ! -f "$LOCAL_PROPERTIES_FILE" ]; then
    return 1
  fi

  local value
  value="$(sed -n "s/^${key}=//p" "$LOCAL_PROPERTIES_FILE" | head -1 | tr -d '\r')"
  if [ -z "$value" ]; then
    return 1
  fi

  value="${value//\\\\/\\}"
  value="${value//\\:/:}"
  printf '%s' "$value"
}

resolve_android_sdk_root() {
  local candidates=()

  if [ -n "${ANDROID_SDK_ROOT:-}" ]; then
    candidates+=("$ANDROID_SDK_ROOT")
  fi
  if [ -n "${ANDROID_HOME:-}" ]; then
    candidates+=("$ANDROID_HOME")
  fi

  local sdk_from_local_properties
  sdk_from_local_properties="$(read_local_property sdk.dir || true)"
  if [ -n "$sdk_from_local_properties" ]; then
    candidates+=("$sdk_from_local_properties")
  fi

  candidates+=(
    "$HOME/Android/Sdk"
    "/usr/local/lib/android/sdk"
    "/opt/android-sdk"
    "/opt/android-sdk-linux"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if [ -n "$candidate" ] && [ -d "$candidate" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done

  return 1
}

resolve_java_tool() {
  local tool_name="$1"

  if command -v "$tool_name" >/dev/null 2>&1; then
    command -v "$tool_name"
    return 0
  fi

  if [ -n "${JAVA_HOME:-}" ]; then
    local java_home_tool="$JAVA_HOME/bin/$tool_name"
    if [ -x "$java_home_tool" ]; then
      printf '%s' "$java_home_tool"
      return 0
    fi
  fi

  echo "ERROR: '$tool_name' is required but was not found in PATH or JAVA_HOME/bin." >&2
  exit 1
}

resolve_android_tool() {
  local tool_name="$1"

  if command -v "$tool_name" >/dev/null 2>&1; then
    command -v "$tool_name"
    return 0
  fi

  if [ -n "${ANDROID_SDK_ROOT:-}" ] && [ -d "${ANDROID_SDK_ROOT:-}" ]; then
    :
  else
    ANDROID_SDK_ROOT="$(resolve_android_sdk_root || true)"
  fi

  if [ -z "${ANDROID_SDK_ROOT:-}" ]; then
    echo "ERROR: Android SDK root could not be found. Set ANDROID_SDK_ROOT or ANDROID_HOME." >&2
    exit 1
  fi

  local build_tools_dir="$ANDROID_SDK_ROOT/build-tools"
  if [ ! -d "$build_tools_dir" ]; then
    echo "ERROR: Android build-tools were not found under $build_tools_dir" >&2
    exit 1
  fi

  local resolved_path
  resolved_path="$(
    find "$build_tools_dir" -maxdepth 2 -type f \( -name "$tool_name" -o -name "${tool_name}.exe" -o -name "${tool_name}.bat" \) \
      | sort -V \
      | tail -1
  )"

  if [ -z "$resolved_path" ]; then
    echo "ERROR: '$tool_name' was not found under $build_tools_dir" >&2
    exit 1
  fi

  printf '%s' "$resolved_path"
}

normalize_fingerprint() {
  printf '%s' "$1" | tr -d '[:space:]:-' | tr '[:upper:]' '[:lower:]'
}

read_key_property() {
  local key="$1"
  sed -n "s/^${key}=//p" "$KEY_PROPERTIES_FILE" | head -1 | tr -d '\r'
}

resolve_keystore_path() {
  local store_file="$1"
  if [[ "$store_file" =~ ^([A-Za-z]:[\\/]|/) ]]; then
    printf '%s' "$store_file"
  else
    printf '%s/%s' "$ANDROID_DIR" "$store_file"
  fi
}

verify_release_apk() {
  local apk_path="$1"
  local version="$2"

  if [ ! -f "$KEY_PROPERTIES_FILE" ]; then
    echo "ERROR: Missing $KEY_PROPERTIES_FILE. Refusing to upload an unverified APK."
    exit 1
  fi

  local key_alias
  local key_password
  local store_file_rel
  local store_password
  key_alias="$(read_key_property keyAlias)"
  key_password="$(read_key_property keyPassword)"
  store_file_rel="$(read_key_property storeFile)"
  store_password="$(read_key_property storePassword)"

  if [ -z "$key_alias" ] || [ -z "$key_password" ] || [ -z "$store_file_rel" ] || [ -z "$store_password" ]; then
    echo "ERROR: key.properties is incomplete. Refusing to upload an unverified APK."
    exit 1
  fi

  local store_file
  store_file="$(resolve_keystore_path "$store_file_rel")"
  if [ ! -f "$store_file" ]; then
    echo "ERROR: Release keystore not found at $store_file"
    exit 1
  fi

  local signer_output
  signer_output="$("$APKSIGNER_BIN" verify --print-certs "$apk_path")"

  local actual_sha
  local actual_subject
  actual_sha="$(printf '%s\n' "$signer_output" | sed -n 's/^Signer #1 certificate SHA-256 digest: //p' | head -1)"
  actual_subject="$(printf '%s\n' "$signer_output" | sed -n 's/^Signer #1 certificate DN: //p' | head -1)"

  if [ -z "$actual_sha" ]; then
    echo "ERROR: Could not read the APK signing fingerprint."
    exit 1
  fi

  if printf '%s\n' "$actual_subject" | grep -qi 'Android Debug'; then
    echo "ERROR: Refusing to upload a debug-signed APK."
    echo "Signer: $actual_subject"
    exit 1
  fi

  local keytool_output
  keytool_output="$("$KEYTOOL_BIN" -list -v -keystore "$store_file" -alias "$key_alias" -storepass "$store_password" -keypass "$key_password")"

  local expected_sha
  expected_sha="$(printf '%s\n' "$keytool_output" | sed -n 's/^[[:space:]]*SHA256: //p' | head -1)"

  if [ -z "$expected_sha" ]; then
    echo "ERROR: Could not read the expected release keystore fingerprint."
    exit 1
  fi

  if [ "$(normalize_fingerprint "$actual_sha")" != "$(normalize_fingerprint "$expected_sha")" ]; then
    echo "ERROR: APK signer does not match the configured release keystore."
    echo "Expected: $expected_sha"
    echo "Actual:   $actual_sha"
    exit 1
  fi

  local badging
  badging="$("$AAPT_BIN" dump badging "$apk_path")"

  local package_name
  local version_name
  package_name="$(printf '%s\n' "$badging" | sed -n "s/^package: name='\\([^']*\\)'.*/\\1/p" | head -1)"
  version_name="$(printf '%s\n' "$badging" | sed -n "s/^package: name='[^']*' versionCode='[^']*' versionName='\\([^']*\\)'.*/\\1/p" | head -1)"

  if [ "$package_name" != "$EXPECTED_APPLICATION_ID" ]; then
    echo "ERROR: Unexpected applicationId '$package_name'. Expected '$EXPECTED_APPLICATION_ID'."
    exit 1
  fi

  if [ "$version_name" != "$version" ]; then
    echo "ERROR: APK version '$version_name' does not match pubspec version '$version'."
    exit 1
  fi

  echo "Verified release signature for $apk_path"
}

upload_file() {
  local file_path="$1"
  local dest_name="$2"
  local content_type="$3"
  local response
  response="$(curl -s -w "\n%{http_code}" -X POST \
    "${SUPABASE_URL}/storage/v1/object/${BUCKET}/${dest_name}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: ${content_type}" \
    -H "x-upsert: true" \
    --data-binary "@${file_path}")"

  local http_code
  local body
  http_code="$(printf '%s\n' "$response" | tail -1)"
  body="$(printf '%s\n' "$response" | sed '$d')"

  if [ "$http_code" = "200" ]; then
    echo "Uploaded ${dest_name} (HTTP ${http_code})"
  else
    echo "ERROR: Upload failed for ${dest_name} (HTTP ${http_code})"
    echo "$body"
    exit 1
  fi
}

require_command flutter
require_command curl

KEYTOOL_BIN="$(resolve_java_tool keytool)"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$(resolve_android_sdk_root || true)}"
APKSIGNER_BIN="$(resolve_android_tool apksigner)"
AAPT_BIN="$(resolve_android_tool aapt)"

VERSION="$(grep '^version:' "$PUBSPEC" | head -1 | sed 's/version: *//;s/+.*//')"
if [ -z "$VERSION" ]; then
  echo "ERROR: Could not read the app version from $PUBSPEC"
  exit 1
fi

APK_NAME="LeoBook-v${VERSION}.apk"
LATEST_NAME="LeoBook-latest.apk"
PUBLIC_URL="${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/${LATEST_NAME}"

if [ "${1:-}" != "--skip-build" ]; then
  echo "Building release APK..."
  cd "$APP_DIR"
  flutter build apk --release
  cd "$SCRIPT_DIR"
else
  echo "Skipping build (--skip-build)"
fi

SOURCE_APK="$APK_OUTPUT/app-release.apk"
if [ ! -f "$SOURCE_APK" ]; then
  echo "ERROR: APK not found at $SOURCE_APK"
  exit 1
fi

cp "$SOURCE_APK" "$APK_OUTPUT/$APK_NAME"
cp "$SOURCE_APK" "$APK_OUTPUT/$LATEST_NAME"

verify_release_apk "$APK_OUTPUT/$LATEST_NAME" "$VERSION"
verify_release_apk "$APK_OUTPUT/$APK_NAME" "$VERSION"

if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  for env_file in "$APP_DIR/.env" "$SCRIPT_DIR/.env"; do
    if [ -f "$env_file" ]; then
      loaded_key="$(grep -E '^[[:space:]]*(SUPABASE_SERVICE_ROLE_KEY|SUPABASE_SERVICE_KEY)=' "$env_file" | head -1 | sed -E 's/^[[:space:]]*(SUPABASE_SERVICE_ROLE_KEY|SUPABASE_SERVICE_KEY)=//' | tr -d '"' | tr -d "'" | xargs || true)"
      if [ -n "$loaded_key" ]; then
        export SUPABASE_SERVICE_ROLE_KEY="$loaded_key"
        break
      fi
    fi
  done
fi

if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY was not found in the environment or .env files."
  exit 1
fi

echo "Ensuring bucket '$BUCKET' exists..."
bucket_check="$(curl -s -o /dev/null -w "%{http_code}" \
  "${SUPABASE_URL}/storage/v1/bucket/${BUCKET}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}")"

if [ "$bucket_check" != "200" ]; then
  echo "Creating bucket '$BUCKET'..."
  curl -s -X POST \
    "${SUPABASE_URL}/storage/v1/bucket" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"${BUCKET}\", \"name\": \"${BUCKET}\", \"public\": true}" >/dev/null
fi

echo "Uploading APKs to Supabase..."
upload_file "$APK_OUTPUT/$LATEST_NAME" "$LATEST_NAME" "application/vnd.android.package-archive"
upload_file "$APK_OUTPUT/$APK_NAME" "$APK_NAME" "application/vnd.android.package-archive"

METADATA_FILE="$APK_OUTPUT/metadata.json"
cat > "$METADATA_FILE" << EOF
{
  "version": "$VERSION",
  "apk_url": "$PUBLIC_URL",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "Uploading metadata.json..."
upload_file "$METADATA_FILE" "metadata.json" "application/json"

echo "Deploy complete"
echo "Version:  $VERSION"
echo "APK URL:  $PUBLIC_URL"
echo "Metadata: ${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/metadata.json"
