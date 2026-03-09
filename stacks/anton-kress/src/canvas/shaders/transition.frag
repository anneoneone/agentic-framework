#ifdef GL_ES
precision mediump float;
#endif

uniform float uProgress;  // 0 → 1: transition progress
uniform float uTime;

varying vec2 vUv;

// Smooth noise for organic wipe edge
float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1,0)), u.x),
    mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), u.x),
    u.y
  );
}

void main() {
  // Diagonal dissolve with noise at the edge
  float diag = vUv.x * 0.6 + vUv.y * 0.4;
  float n = noise(vUv * 6.0 + uTime * 0.2) * 0.15;
  float mask = smoothstep(uProgress - 0.12, uProgress + 0.12, diag + n);

  // Dark transition color
  vec3 color = vec3(0.047, 0.047, 0.071);

  gl_FragColor = vec4(color, mask * (1.0 - uProgress));
}
