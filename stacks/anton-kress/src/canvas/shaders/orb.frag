#ifdef GL_ES
precision mediump float;
#endif

uniform float uTime;
uniform float uHover;
uniform float uSelected;
uniform vec3  uColor;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

void main() {
  // Fresnel-like rim glow
  vec3 viewDir = normalize(cameraPosition - vPosition);
  float rim = 1.0 - max(dot(viewDir, vNormal), 0.0);
  rim = pow(rim, 2.5);

  vec3 baseColor = uColor * (0.3 + vNoise * 0.1 + 0.1);
  vec3 glowColor = uColor * (1.5 + uHover * 0.5);

  vec3 color = mix(baseColor, glowColor, rim);
  color += uColor * uSelected * 0.4;

  // Animated inner shimmer
  float shimmer = sin(vPosition.y * 8.0 + uTime * 2.0) * 0.05 + 0.95;
  color *= shimmer;

  float alpha = 0.85 + rim * 0.15;

  gl_FragColor = vec4(color, alpha);
}
