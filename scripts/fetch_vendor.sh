#!/usr/bin/env bash
# Downloads the MediaPipe face-detection runtime + model into static/vendor so the
# booth keeps working if the party Wi-Fi drops. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${MEDIAPIPE_VERSION:-1.1.1}"
DEST=static/vendor/mediapipe
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST/wasm"
(cd "$TMP" && npm pack "@mediapipe/tasks-vision@$VERSION" >/dev/null && tar xzf ./*.tgz)
cp "$TMP/package/vision_bundle.mjs" "$DEST/"
cp "$TMP"/package/wasm/* "$DEST/wasm/"
curl -fsSL -o "$DEST/blaze_face_short_range.tflite" \
  https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite
echo "MediaPipe $VERSION vendored into $DEST"
ls -la "$DEST" "$DEST/wasm"
