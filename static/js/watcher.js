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
    if (this.fake !== undefined) {
      // Test hook (window.oracleFakeFace): pretend this face is there, or null for nobody.
      this.faces = this.fake ? [this.fake] : [];
      this.nearest = this.fake;
      return;
    }
    const v = this.video;
    if (!this.detector || v.readyState < 2 || v.currentTime === this._lastVideoTime) return;
    this._lastVideoTime = v.currentTime;
    const res = this.detector.detectForVideo(v, now);
    const vw = v.videoWidth;
    const vh = v.videoHeight;
    this.faces = res.detections.map((d) => {
      const b = d.boundingBox;
      // keypoints come normalized: right eye, left eye, nose, mouth, ears; keep eyes and mouth
      const kp = d.keypoints?.length >= 4 ? [d.keypoints[0], d.keypoints[1], d.keypoints[3]] : null;
      return { x: (b.originX + b.width / 2) / vw, y: (b.originY + b.height / 2) / vh, w: b.width / vw, h: b.height / vh, kp };
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

  // The nearest face cut out of the current frame, mirrored like a looking glass.
  // With keypoints: a loose square with crop.marks (eyes left-to-right, mouth) in crop
  // pixels, for the puppet to line up with hers. Without: framed tight, chin to
  // hairline, in her face's proportions (100:128). Stays in memory; null if no face.
  faceCrop(width = 240) {
    const v = this.video;
    const f = this.nearest;
    if (!f || !v.videoWidth) return null;
    const vw = v.videoWidth;
    const vh = v.videoHeight;
    if (f.kp) {
      const side = Math.min(vw, vh, f.w * vw * 2.4);
      const sx = Math.max(0, Math.min(vw - side, f.x * vw - side / 2));
      const sy = Math.max(0, Math.min(vh - side, f.y * vh - side / 2));
      const k = Math.min(1, 480 / side);
      const crop = document.createElement("canvas");
      crop.width = crop.height = Math.round(side * k);
      const c = crop.getContext("2d");
      c.translate(crop.width, 0);
      c.scale(-1, 1);
      c.drawImage(v, sx, sy, side, side, 0, 0, crop.width, crop.height);
      const at = (p) => ({ x: crop.width - (p.x * vw - sx) * k, y: (p.y * vh - sy) * k });
      const [e1, e2, mouth] = f.kp.map(at);
      crop.marks = { eyes: e1.x < e2.x ? [e1, e2] : [e2, e1], mouth };
      return crop;
    }
    const boxH = (f.h || (f.w * vw) / vh) * vh; // detector box: about brows to chin
    const sh = Math.min(vh, boxH * 1.2);
    const sw = Math.min(vw, sh / 1.28);
    const sx = Math.max(0, Math.min(vw - sw, f.x * vw - sw / 2));
    const sy = Math.max(0, Math.min(vh - sh, f.y * vh + boxH * 0.55 - sh)); // chin at the bottom of her oval
    const crop = document.createElement("canvas");
    crop.width = width;
    crop.height = Math.round(width * 1.28);
    const c = crop.getContext("2d");
    c.translate(crop.width, 0);
    c.scale(-1, 1);
    c.drawImage(v, sx, sy, sw, sh, 0, 0, crop.width, crop.height);
    return crop;
  }
}
