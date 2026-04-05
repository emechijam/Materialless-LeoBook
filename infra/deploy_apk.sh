#!/usr/bin/env bash
# Build, verify, and upload the LeoBook Android APK to Supabase Storage.
# This version reads signing credentials directly from leobookapp/.env
#
# Usage:
#   ./deploy_apk.sh
#   ./deploy_apk.sh --skip-build

set -euo pipefail

# Ensure the script is running under Bash (prevents syntax errors if invoked with sh/dash)
if [ -z "${BASH_VERSION:-}" ]; then
  echo "ERROR: This script must be executed with bash (not sh or dash)." >&2
  echo "Try: bash ./deploy_apk.sh" >&2
  exit 1
fi

SUPABASE_URL="https://jefoqzewyvscdqcpnjxu.supabase.co"
BUCKET="app-releases"
EXPECTED_APPLICATION_ID="com.materialless.leobookapp"
DEFAULT_UPDATE_ABI="arm64-v8a"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/../leobookapp"
ANDROID_DIR="$APP_DIR/android"
PUBSPEC="$APP_DIR/pubspec.yaml"
APK_OUTPUT="$APP_DIR/build/app/outputs/flutter-apk"
KEY_PROPERTIES_FILE="$ANDROID_DIR/key.properties"
LOCAL_PROPERTIES_FILE="$ANDROID_DIR/local.properties"
TEMP_SIGNING_DIR=""
KEY_PROPERTIES_BACKUP=""
RESTORE_KEY_PROPERTIES=0

cleanup_temp_signing() {
  if [ -n "$KEY_PROPERTIES_BACKUP" ] && [ -f "$KEY_PROPERTIES_BACKUP" ]; then
    mv "$KEY_PROPERTIES_BACKUP" "$KEY_PROPERTIES_FILE"
  elif [ "$RESTORE_KEY_PROPERTIES" = "1" ] && [ -f "$KEY_PROPERTIES_FILE" ]; then
    rm -f "$KEY_PROPERTIES_FILE"
  fi

  if [ -n "$TEMP_SIGNING_DIR" ] && [ -d "$TEMP_SIGNING_DIR" ]; then
    rm -rf "$TEMP_SIGNING_DIR"
  fi
}

trap cleanup_temp_signing EXIT

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' is required but not available in PATH."
    exit 1
  fi
}

load_env_file() {
  local env_file="$1"
  if [ ! -f "$env_file" ]; then
    return 0
  fi

  local line=""
  local key=""
  local value=""
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"

    case "$line" in
      ""|\#*)
        continue
        ;;
    esac

    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*) ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"

      if [[ "$value" =~ ^\"(.*)\"$ ]]; then
        value="${BASH_REMATCH[1]}"
      elif [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
      fi

      if [ -z "${!key+x}" ]; then
        export "$key=$value"
      fi
    fi
  done < "$env_file"
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

public_url_for_name() {
  local object_name="$1"
  printf '%s/storage/v1/object/public/%s/%s' "$SUPABASE_URL" "$BUCKET" "$object_name"
}

first_non_empty_env() {
  local var_name
  for var_name in "$@"; do
    if [ -n "${!var_name:-}" ]; then
      printf '%s' "${!var_name}"
      return 0
    fi
  done
  return 1
}

# Read a var directly from .env files on disk - bypasses parent-process env inheritance.
# Needed because Leo.py exports its env to bash subprocesses; load_env_file skips
# already-set vars (even empty ones), so signing creds may be invisible to first_non_empty_env.
_read_from_env_files() {
  local var_name="$1"
  local env_file v
  for env_file in "$APP_DIR/.env" "$SCRIPT_DIR/.env"; do
    [ -f "$env_file" ] || continue
    v="$(grep -m1 "^[[:space:]]*${var_name}=" "$env_file" 2>/dev/null | sed 's/^[^=]*=//')"
    v="${v%$'\r'}"
    v="${v//\"}"
    v="${v//\'}"
    [ -n "$v" ] && { printf '%s' "$v"; return 0; }
  done
  return 1
}

prepare_release_signing() {
  if [ -f "$KEY_PROPERTIES_FILE" ]; then
    return 0
  fi

  local keystore_path=""
  local store_password=""
  local key_alias=""
  local key_password=""

  keystore_path="$(first_non_empty_env LEOBOOK_KEYSTORE_PATH KEYSTORE_PATH || true)"
  # Auto-detect bundled repo keystore when path is unset or points to a placeholder
  local bundled_jks="$APP_DIR/android/app/leobook-release.jks"
  if { [ -z "$keystore_path" ] || [ ! -f "$keystore_path" ]; } && [ -f "$bundled_jks" ]; then
    keystore_path="$bundled_jks"
  fi
  store_password="$(first_non_empty_env LEOBOOK_STORE_PASSWORD STORE_PASSWORD || _read_from_env_files LEOBOOK_STORE_PASSWORD || true)"
  key_alias="$(first_non_empty_env LEOBOOK_KEY_ALIAS KEY_ALIAS || _read_from_env_files LEOBOOK_KEY_ALIAS || true)"
  key_password="$(first_non_empty_env LEOBOOK_KEY_PASSWORD KEY_PASSWORD || _read_from_env_files LEOBOOK_KEY_PASSWORD || true)"

  if [ -z "$store_password" ] || [ -z "$key_alias" ] || [ -z "$key_password" ]; then
    echo "ERROR: Release signing credentials not found." >&2
    echo "Either:" >&2
    echo "  1) Add to leobookapp/.env or infra/.env: LEOBOOK_STORE_PASSWORD, LEOBOOK_KEY_ALIAS, LEOBOOK_KEY_PASSWORD" >&2
    echo "     (aliases: STORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD) plus LEOBOOK_KEYSTORE_PATH or LEOBOOK_KEYSTORE_BASE64" >&2
    echo "  2) Or create leobookapp/android/key.properties pointing at your release .jks (see Flutter Android signing)." >&2
    echo "See README.md → Deploy APK." >&2
    exit 1
  fi

  TEMP_SIGNING_DIR="$(mktemp -d)"
  local temp_keystore="$TEMP_SIGNING_DIR/leobook-release.jks"

  # Resolve keystore: file path → base64 decode → error
  if [ -n "$keystore_path" ] && [ -f "$keystore_path" ]; then
    cp "$keystore_path" "$temp_keystore"
    echo "✓ Keystore loaded from file: $keystore_path"
  elif [ -n "${LEOBOOK_KEYSTORE_BASE64:-}" ]; then
    printf '%s' "$LEOBOOK_KEYSTORE_BASE64" | base64 -d > "$temp_keystore" 2>/dev/null
    if [ ! -s "$temp_keystore" ]; then
      echo "ERROR: Failed to decode LEOBOOK_KEYSTORE_BASE64"
      exit 1
    fi
    echo "✓ Keystore decoded from LEOBOOK_KEYSTORE_BASE64"
  else
    echo "ERROR: No keystore found. Set LEOBOOK_KEYSTORE_PATH to a valid file or LEOBOOK_KEYSTORE_BASE64."
    exit 1
  fi

  if [ -f "$KEY_PROPERTIES_FILE" ]; then
    KEY_PROPERTIES_BACKUP="$TEMP_SIGNING_DIR/key.properties.backup"
    cp "$KEY_PROPERTIES_FILE" "$KEY_PROPERTIES_BACKUP"
  else
    RESTORE_KEY_PROPERTIES=1
  fi

  cat > "$KEY_PROPERTIES_FILE" << EOF
storePassword=$store_password
keyPassword=$key_password
keyAlias=$key_alias
storeFile=$temp_keystore
EOF
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

stage_split_apk() {
  local abi="$1"
  local source_apk="${APK_OUTPUT}/app-${abi}-release.apk"
  if [ ! -f "$source_apk" ]; then
    return 1
  fi

  local latest_name="LeoBook-latest-${abi}.apk"
  local version_name="LeoBook-v${VERSION}-${abi}.apk"

  cp "$source_apk" "$APK_OUTPUT/$latest_name"
  cp "$source_apk" "$APK_OUTPUT/$version_name"

  verify_release_apk "$APK_OUTPUT/$latest_name" "$VERSION"
  verify_release_apk "$APK_OUTPUT/$version_name" "$VERSION"

  upload_file "$APK_OUTPUT/$latest_name" "$latest_name" "application/vnd.android.package-archive"
  upload_file "$APK_OUTPUT/$version_name" "$version_name" "application/vnd.android.package-archive"

  return 0
}

require_command flutter
require_command curl
require_command base64

load_env_file "$APP_DIR/.env"
load_env_file "$SCRIPT_DIR/.env"
# Also load a committed signing env (not gitignored, safe for Codespaces)
load_env_file "$SCRIPT_DIR/signing.env"

KEYTOOL_BIN="$(resolve_java_tool keytool)"
ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$(resolve_android_sdk_root || true)}"
APKSIGNER_BIN="$(resolve_android_tool apksigner)"
AAPT_BIN="$(resolve_android_tool aapt)"
prepare_release_signing

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
  flutter build apk --release --split-per-abi
  cd "$SCRIPT_DIR"
else
  echo "Skipping build (--skip-build)"
fi

DEFAULT_SOURCE_APK=""
for candidate_abi in "$DEFAULT_UPDATE_ABI" "armeabi-v7a" "x86_64"; do
  candidate_apk="${APK_OUTPUT}/app-${candidate_abi}-release.apk"
  if [ -f "$candidate_apk" ]; then
    DEFAULT_SOURCE_APK="$candidate_apk"
    DEFAULT_SOURCE_ABI="$candidate_abi"
    break
  fi
done

if [ -z "$DEFAULT_SOURCE_APK" ] && [ -f "$APK_OUTPUT/app-release.apk" ]; then
  DEFAULT_SOURCE_APK="$APK_OUTPUT/app-release.apk"
  DEFAULT_SOURCE_ABI="universal"
fi

if [ -z "$DEFAULT_SOURCE_APK" ]; then
  echo "ERROR: No APK was found in $APK_OUTPUT"
  exit 1
fi

cp "$DEFAULT_SOURCE_APK" "$APK_OUTPUT/$APK_NAME"
cp "$DEFAULT_SOURCE_APK" "$APK_OUTPUT/$LATEST_NAME"

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

APK_URLS_JSON=""
if stage_split_apk "arm64-v8a"; then
  APK_URLS_JSON="${APK_URLS_JSON}    \"arm64-v8a\": \"$(public_url_for_name "LeoBook-latest-arm64-v8a.apk")\""
fi
if stage_split_apk "armeabi-v7a"; then
  if [ -n "$APK_URLS_JSON" ]; then
    APK_URLS_JSON="${APK_URLS_JSON},\n"
  fi
  APK_URLS_JSON="${APK_URLS_JSON}    \"armeabi-v7a\": \"$(public_url_for_name "LeoBook-latest-armeabi-v7a.apk")\""
fi
if stage_split_apk "x86_64"; then
  if [ -n "$APK_URLS_JSON" ]; then
    APK_URLS_JSON="${APK_URLS_JSON},\n"
  fi
  APK_URLS_JSON="${APK_URLS_JSON}    \"x86_64\": \"$(public_url_for_name "LeoBook-latest-x86_64.apk")\""
fi

if [ "$DEFAULT_SOURCE_ABI" = "universal" ]; then
  if [ -n "$APK_URLS_JSON" ]; then
    APK_URLS_JSON="${APK_URLS_JSON},\n"
  fi
  APK_URLS_JSON="${APK_URLS_JSON}    \"universal\": \"$(public_url_for_name "$LATEST_NAME")\""
fi

METADATA_FILE="$APK_OUTPUT/metadata.json"
cat > "$METADATA_FILE" << EOF
{
  "version": "$VERSION",
  "apk_url": "$PUBLIC_URL",
  "default_abi": "$DEFAULT_SOURCE_ABI",
  "apk_urls": {
$(printf '%b\n' "$APK_URLS_JSON")
  },
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "Uploading metadata.json..."
upload_file "$METADATA_FILE" "metadata.json" "application/json"

echo "Deploy complete"
echo "Version:  $VERSION"
echo "APK URL:  $PUBLIC_URL"
echo "Metadata: ${SUPABASE_URL}/storage/v1/object/public/${BUCKET}/metadata.json"
