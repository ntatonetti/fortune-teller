// Corner-pin projection mapping: a CSS matrix3d that takes a w x h element and
// lands its four corners on four arbitrary screen points (the classic
// "keystone" warp, so a face drawn flat lines up with a real head).

// Solve the 8 unknowns of the homography mapping src[i] -> dst[i].
function solve(src, dst) {
  const A = [];
  const b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i];
    const [u, v] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]);
    b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]);
    b.push(v);
  }
  // Gaussian elimination with partial pivoting
  const n = 8;
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(A[r][col]) > Math.abs(A[pivot][col])) pivot = r;
    [A[col], A[pivot]] = [A[pivot], A[col]];
    [b[col], b[pivot]] = [b[pivot], b[col]];
    if (Math.abs(A[col][col]) < 1e-12) return null; // degenerate quad
    for (let r = col + 1; r < n; r++) {
      const f = A[r][col] / A[col][col];
      for (let k = col; k < n; k++) A[r][k] -= f * A[col][k];
      b[r] -= f * b[col];
    }
  }
  const h = new Array(n);
  for (let r = n - 1; r >= 0; r--) {
    let s = b[r];
    for (let k = r + 1; k < n; k++) s -= A[r][k] * h[k];
    h[r] = s / A[r][r];
  }
  return h;
}

// corners: [topLeft, topRight, bottomRight, bottomLeft] as [x, y] in CSS px.
export function cornerPinMatrix(w, h, corners) {
  const src = [
    [0, 0],
    [w, 0],
    [w, h],
    [0, h],
  ];
  const k = solve(src, corners);
  if (!k) return null;
  const [a, b, c, d, e, f, g, hh] = k;
  // 3x3 [a b c; d e f; g hh 1] embedded in a column-major 4x4 for CSS.
  return [a, d, 0, g, b, e, 0, hh, 0, 0, 1, 0, c, f, 0, 1];
}

export function applyMatrix(m, x, y) {
  const X = m[0] * x + m[4] * y + m[12];
  const Y = m[1] * x + m[5] * y + m[13];
  const W = m[3] * x + m[7] * y + m[15];
  return [X / W, Y / W];
}

export function cssMatrix(m) {
  return `matrix3d(${m.map((v) => +v.toFixed(10)).join(",")})`;
}
