// The camera and face detection (MediaPipe from its CDN, runs in the browser).
// Reports the nearest face: where it is, how close (by face width), and
// whether it's turned toward her or away (talking to a friend, say).

import { FaceDetector, FaceLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.1.1/vision_bundle.mjs";

export class Watcher {
  constructor(video) {
    this.video = video;
    this.detector = null;
    this.landmarker = null; // the face mesh, for lining the guest's face up with hers
    this.nearest = null; // {x, y, w, h, kp, turn} normalized 0..1 in the camera image, or null
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
      const fileset = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.1.1/wasm");
      this.detector = await FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite", delegate: "GPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.5,
      });
      FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" },
        runningMode: "IMAGE",
        numFaces: 1,
      })
        .then((l) => (this.landmarker = l))
        .catch((e) => console.warn("no face mesh; the flicker lines up from the detector's keypoints", e));
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
      // How far the nose sits off the line between the eyes, in eye-widths:
      // about 0 facing her, 0.5 or more turned well to one side.
      const [eyeR, eyeL, nose] = d.keypoints || [];
      const turn = nose ? Math.abs(nose.x - (eyeR.x + eyeL.x) / 2) / Math.max(0.01, Math.abs(eyeR.x - eyeL.x)) : 0;
      return { x: (b.originX + b.width / 2) / vw, y: (b.originY + b.height / 2) / vh, w: b.width / vw, h: b.height / vh, kp, turn };
    });
    this.nearest = this.faces.reduce((best, f) => (!best || f.w > best.w ? f : best), null);
  }

  // The nearest guest has turned their head away from her.
  get lookingAway() {
    return this.nearest?.turn > 0.3;
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
      crop.marks = this._meshMarks(crop) || { eyes: e1.x < e2.x ? [e1, e2] : [e2, e1], mouth };
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

  // The iris centres and the middle of the lips, found by the face mesh in the crop
  // itself: much closer than the detector's rough keypoints, which also lag a frame.
  _meshMarks(crop) {
    let lm;
    try {
      lm = this.landmarker?.detect(crop).faceLandmarks?.[0];
    } catch (e) {
      console.warn("face mesh failed", e);
    }
    if (!lm || lm.length < 478) return null;
    const at = (i) => ({ x: lm[i].x * crop.width, y: lm[i].y * crop.height });
    const [a, b, upper, lower] = [at(468), at(473), at(13), at(14)];
    return { eyes: a.x < b.x ? [a, b] : [b, a], mouth: { x: (upper.x + lower.x) / 2, y: (upper.y + lower.y) / 2 } };
  }
}
