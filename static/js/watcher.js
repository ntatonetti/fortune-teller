// The camera and face detection (MediaPipe, runs locally in the browser).
// Reports the nearest face: where it is and how close (by face width).

import { FaceDetector, FilesetResolver } from "/vendor/mediapipe/vision_bundle.mjs";

export class Watcher {
  constructor(video) {
    this.video = video;
    this.detector = null;
    this.nearest = null; // {x, y, w} normalized 0..1 in the camera image, or null
    this.faces = [];
    this._lastVideoTime = -1;
    this._snap = document.createElement("canvas");
  }

  static async cameras() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === "videoinput");
  }

  async start(deviceId) {
    if (this.video.srcObject) this.video.srcObject.getTracks().forEach((t) => t.stop());
    const constraints = {
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, ...(deviceId ? { deviceId: { exact: deviceId } } : {}) },
      audio: false,
    };
    this.video.srcObject = await navigator.mediaDevices.getUserMedia(constraints);
    await this.video.play();
    if (!this.detector) {
      const fileset = await FilesetResolver.forVisionTasks("/vendor/mediapipe/wasm");
      this.detector = await FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "/vendor/mediapipe/blaze_face_short_range.tflite", delegate: "GPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.5,
      });
    }
  }

  // Call once per animation frame.
  update(now) {
    const v = this.video;
    if (!this.detector || v.readyState < 2 || v.currentTime === this._lastVideoTime) return;
    this._lastVideoTime = v.currentTime;
    const res = this.detector.detectForVideo(v, now);
    const vw = v.videoWidth;
    const vh = v.videoHeight;
    this.faces = res.detections.map((d) => {
      const b = d.boundingBox;
      return { x: (b.originX + b.width / 2) / vw, y: (b.originY + b.height / 2) / vh, w: b.width / vw, h: b.height / vh };
    });
    this.nearest = this.faces.reduce((best, f) => (!best || f.w > best.w ? f : best), null);
  }

  // A JPEG of the current camera frame for Claude, base64 data URL.
  snapshot(maxWidth = 1024) {
    const v = this.video;
    if (!v.videoWidth) return null;
    const s = Math.min(1, maxWidth / v.videoWidth);
    this._snap.width = Math.round(v.videoWidth * s);
    this._snap.height = Math.round(v.videoHeight * s);
    this._snap.getContext("2d").drawImage(v, 0, 0, this._snap.width, this._snap.height);
    return this._snap.toDataURL("image/jpeg", 0.82);
  }
}
