uniform float uTime;
uniform float uProgress;
uniform float uHover;
uniform float uSelected;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 10.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - 0.5;
  i = mod289(i);
  vec4 p = permute(permute(permute(i.z + vec4(0.,i1.z,i2.z,1.)) + i.y + vec4(0.,i1.y,i2.y,1.)) + i.x + vec4(0.,i1.x,i2.x,1.));
  vec3 ns = 0.142857142857 * vec3(0., 1., -1.) - vec3(0., 0., 1.) * 0.0;
  // simplified — return basic noise
  float n = fract(sin(dot(v, vec3(12.9898, 78.233, 45.164))) * 43758.5453);
  return n * 2.0 - 1.0;
}

void main() {
  vNormal = normal;
  vPosition = position;

  float noise = snoise(position * 1.5 + uTime * 0.3);
  vNoise = noise;

  float scale = 1.0 + uHover * 0.08 + uSelected * 0.3;
  float blobStrength = 0.06 + uHover * 0.04;

  vec3 displaced = position * scale + normal * noise * blobStrength;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
