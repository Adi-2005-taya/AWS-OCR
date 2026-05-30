import re

file_path = 'd:/AWS/anti aws text extractor/src/static/signup.html'
with open(file_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Replace laser container with floating lines container
html = html.replace('<div id="laser-container"', '<div id="floating-lines-container"')

# Remove the three.js cdn and laser script. 
# We'll just remove everything from the first <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.150.1/three.min.js"></script> to the end of the file, then append the closing body/html tags and the new script.
# Wait, the closing body tag is after the script.
script_start_idx = html.find('<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.150.1/three.min.js"></script>')
if script_start_idx != -1:
    html = html[:script_start_idx] # truncate there

floating_lines_script = """
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.150.1/three.min.js"></script>
<script>
const vertexShader = `
precision highp float;
void main() {
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const fragmentShader = `
precision highp float;

uniform float iTime;
uniform vec3  iResolution;
uniform float animationSpeed;

uniform bool enableTop;
uniform bool enableMiddle;
uniform bool enableBottom;

uniform int topLineCount;
uniform int middleLineCount;
uniform int bottomLineCount;

uniform float topLineDistance;
uniform float middleLineDistance;
uniform float bottomLineDistance;

uniform vec3 topWavePosition;
uniform vec3 middleWavePosition;
uniform vec3 bottomWavePosition;

uniform vec2 iMouse;
uniform bool interactive;
uniform float bendRadius;
uniform float bendStrength;
uniform float bendInfluence;

uniform bool parallax;
uniform float parallaxStrength;
uniform vec2 parallaxOffset;

uniform vec3 lineGradient[8];
uniform int lineGradientCount;

const vec3 BLACK = vec3(0.0);
const vec3 PINK  = vec3(233.0, 71.0, 245.0) / 255.0;
const vec3 BLUE  = vec3(47.0,  75.0, 162.0) / 255.0;

mat2 rotate(float r) {
  return mat2(cos(r), sin(r), -sin(r), cos(r));
}

vec3 background_color(vec2 uv) {
  vec3 col = vec3(0.0);
  float y = sin(uv.x - 0.2) * 0.3 - 0.1;
  float m = uv.y - y;
  col += mix(BLUE, BLACK, smoothstep(0.0, 1.0, abs(m)));
  col += mix(PINK, BLACK, smoothstep(0.0, 1.0, abs(m - 0.8)));
  return col * 0.5;
}

vec3 getLineColor(float t, vec3 baseColor) {
  if (lineGradientCount <= 0) return baseColor;
  vec3 gradientColor;
  if (lineGradientCount == 1) {
    gradientColor = lineGradient[0];
  } else {
    float clampedT = clamp(t, 0.0, 0.9999);
    float scaled = clampedT * float(lineGradientCount - 1);
    int idx = int(floor(scaled));
    float f = fract(scaled);
    int idx2 = min(idx + 1, lineGradientCount - 1);
    vec3 c1 = lineGradient[idx];
    vec3 c2 = lineGradient[idx2];
    gradientColor = mix(c1, c2, f);
  }
  return gradientColor * 0.5;
}

float wave(vec2 uv, float offset, vec2 screenUv, vec2 mouseUv, bool shouldBend) {
  float time = iTime * animationSpeed;
  float x_offset   = offset;
  float x_movement = time * 0.1;
  float amp        = sin(offset + time * 0.2) * 0.3;
  float y          = sin(uv.x + x_offset + x_movement) * amp;

  if (shouldBend) {
    vec2 d = screenUv - mouseUv;
    float influence = exp(-dot(d, d) * bendRadius);
    float bendOffset = (mouseUv.y - screenUv.y) * influence * bendStrength * bendInfluence;
    y += bendOffset;
  }

  float m = uv.y - y;
  return 0.0175 / max(abs(m) + 0.01, 1e-3) + 0.01;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
  vec2 baseUv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
  baseUv.y *= -1.0;
  
  if (parallax) {
    baseUv += parallaxOffset;
  }

  vec3 col = vec3(0.0);
  vec3 b = lineGradientCount > 0 ? vec3(0.0) : background_color(baseUv);

  vec2 mouseUv = vec2(0.0);
  if (interactive) {
    mouseUv = (2.0 * iMouse - iResolution.xy) / iResolution.y;
    mouseUv.y *= -1.0;
  }
  
  if (enableBottom) {
    for (int i = 0; i < 50; ++i) { // Fixed max loops for WebGL compatibility
      if (i >= bottomLineCount) break;
      float fi = float(i);
      float t = fi / max(float(bottomLineCount - 1), 1.0);
      vec3 lineCol = getLineColor(t, b);
      float angle = bottomWavePosition.z * log(length(baseUv) + 1.0);
      vec2 ruv = baseUv * rotate(angle);
      col += lineCol * wave(
        ruv + vec2(bottomLineDistance * fi + bottomWavePosition.x, bottomWavePosition.y),
        1.5 + 0.2 * fi, baseUv, mouseUv, interactive
      ) * 0.2;
    }
  }

  if (enableMiddle) {
    for (int i = 0; i < 50; ++i) {
      if (i >= middleLineCount) break;
      float fi = float(i);
      float t = fi / max(float(middleLineCount - 1), 1.0);
      vec3 lineCol = getLineColor(t, b);
      float angle = middleWavePosition.z * log(length(baseUv) + 1.0);
      vec2 ruv = baseUv * rotate(angle);
      col += lineCol * wave(
        ruv + vec2(middleLineDistance * fi + middleWavePosition.x, middleWavePosition.y),
        2.0 + 0.15 * fi, baseUv, mouseUv, interactive
      );
    }
  }

  if (enableTop) {
    for (int i = 0; i < 50; ++i) {
      if (i >= topLineCount) break;
      float fi = float(i);
      float t = fi / max(float(topLineCount - 1), 1.0);
      vec3 lineCol = getLineColor(t, b);
      float angle = topWavePosition.z * log(length(baseUv) + 1.0);
      vec2 ruv = baseUv * rotate(angle);
      ruv.x *= -1.0;
      col += lineCol * wave(
        ruv + vec2(topLineDistance * fi + topWavePosition.x, topWavePosition.y),
        1.0 + 0.2 * fi, baseUv, mouseUv, interactive
      ) * 0.1;
    }
  }

  fragColor = vec4(col, 1.0);
}

void main() {
  vec4 color = vec4(0.0);
  mainImage(color, gl_FragCoord.xy);
  gl_FragColor = color;
}
`;

(function initFloatingLines() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runFloatingLines);
  } else {
    runFloatingLines();
  }

  function runFloatingLines() {
    const mount = document.getElementById('floating-lines-container');
    if (!mount || !window.THREE) return;

    mount.style.mixBlendMode = 'screen';

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    camera.position.z = 1;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    mount.appendChild(renderer.domElement);

    const uniforms = {
      iTime: { value: 0 },
      iResolution: { value: new THREE.Vector3(1, 1, 1) },
      animationSpeed: { value: 1 },

      enableTop: { value: true },
      enableMiddle: { value: true },
      enableBottom: { value: true },

      topLineCount: { value: 10 },
      middleLineCount: { value: 15 },
      bottomLineCount: { value: 20 },

      topLineDistance: { value: 0.08 },
      middleLineDistance: { value: 0.06 },
      bottomLineDistance: { value: 0.04 },

      topWavePosition: { value: new THREE.Vector3(10.0, 0.5, -0.4) },
      middleWavePosition: { value: new THREE.Vector3(5.0, 0.0, 0.2) },
      bottomWavePosition: { value: new THREE.Vector3(2.0, -0.7, -1) },

      iMouse: { value: new THREE.Vector2(-1000, -1000) },
      interactive: { value: true },
      bendRadius: { value: 5.0 },
      bendStrength: { value: -0.5 },
      bendInfluence: { value: 0 },

      parallax: { value: true },
      parallaxStrength: { value: 0.2 },
      parallaxOffset: { value: new THREE.Vector2(0, 0) },

      lineGradient: { value: Array.from({ length: 8 }, () => new THREE.Vector3(1, 1, 1)) },
      lineGradientCount: { value: 0 }
    };

    const material = new THREE.ShaderMaterial({
      uniforms,
      vertexShader,
      fragmentShader
    });

    const geometry = new THREE.PlaneGeometry(2, 2);
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const clock = new THREE.Clock();

    let targetMouse = new THREE.Vector2(-1000, -1000);
    let currentMouse = new THREE.Vector2(-1000, -1000);
    let targetInfluence = 0;
    let currentInfluence = 0;
    let targetParallax = new THREE.Vector2(0, 0);
    let currentParallax = new THREE.Vector2(0, 0);
    const mouseDamping = 0.05;

    const setSize = () => {
      const width = mount.clientWidth || window.innerWidth;
      const height = mount.clientHeight || window.innerHeight;
      renderer.setSize(width, height, false);
      uniforms.iResolution.value.set(renderer.domElement.width, renderer.domElement.height, 1);
    };

    setSize();
    window.addEventListener('resize', setSize);

    const handlePointerMove = event => {
      const rect = renderer.domElement.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const dpr = renderer.getPixelRatio();

      targetMouse.set(x * dpr, (rect.height - y) * dpr);
      targetInfluence = 1.0;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const offsetX = (x - centerX) / rect.width;
      const offsetY = -(y - centerY) / rect.height;
      targetParallax.set(offsetX * 0.2, offsetY * 0.2);
    };

    const handlePointerLeave = () => {
      targetInfluence = 0.0;
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerleave', handlePointerLeave);

    const renderLoop = () => {
      uniforms.iTime.value = clock.getElapsedTime();

      currentMouse.lerp(targetMouse, mouseDamping);
      uniforms.iMouse.value.copy(currentMouse);

      currentInfluence += (targetInfluence - currentInfluence) * mouseDamping;
      uniforms.bendInfluence.value = currentInfluence;

      currentParallax.lerp(targetParallax, mouseDamping);
      uniforms.parallaxOffset.value.copy(currentParallax);

      renderer.render(scene, camera);
      requestAnimationFrame(renderLoop);
    };
    renderLoop();
  }
})();
</script>
</body>
</html>
"""

html += floating_lines_script

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(html)
