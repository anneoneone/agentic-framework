#ifdef GL_ES
precision mediump float;
#endif

uniform float uTime;
uniform float uProgress;

varying vec2 vUv;
varying float vNoise;

void main() {
  // Dark base palette — matches CSS vars
  vec3 colorSurface = vec3(0.047, 0.047, 0.071);  // #0c0c12
  vec3 colorAccent  = vec3(0.471, 0.392, 0.863);  // purple ~rgb(120,100,220)
  vec3 colorSecond  = vec3(0.2,   0.15,  0.55);   // deep indigo

  // Slow radial gradient from center
  float dist = length(vUv - 0.5) * 1.4;
  float radial = 1.0 - smoothstep(0.0, 1.0, dist);

  // Noise-driven colour shift
  float n = vNoise * 0.5 + 0.5;

  vec3 color = mix(colorSurface, colorSecond, radial * 0.6);
  color = mix(color, colorAccent, n * 0.35 * uProgress);

  // Subtle vignette
  color *= 1.0 - dist * 0.4;

  // Time-based breathing pulse
  float pulse = sin(uTime * 0.4) * 0.04 + 0.96;
  color *= pulse;

  gl_FragColor = vec4(color, 1.0);
}
