import * as THREE from "three";

// Procedural geometry only: no downloaded models, textures, fonts or trackers.
export function mountCompanion(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(240, 180, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 240 / 180, .1, 30);
  camera.position.set(0, .25, 6.2);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.HemisphereLight(0xdafcff, 0x294153, 3));
  const key = new THREE.DirectionalLight(0xffffff, 5);
  key.position.set(-3, 4, 5); scene.add(key);
  const rim = new THREE.DirectionalLight(0xa7ed63, 6);
  rim.position.set(3, 1, -2); scene.add(rim);
  const robot = new THREE.Group(); scene.add(robot);
  const shell = new THREE.MeshPhysicalMaterial({ color: 0xe7f4e9, metalness: .42, roughness: .23, clearcoat: 1 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x102333, metalness: .55, roughness: .24 });
  const glow = new THREE.MeshStandardMaterial({ color: 0xc6ff79, emissive: 0xa3ee4f, emissiveIntensity: 1.1, roughness: .3 });
  const teal = new THREE.MeshStandardMaterial({ color: 0x3edbd5, metalness: .45, roughness: .25 });
  function mesh(geometry, material, x, y, z, scale) {
    const item = new THREE.Mesh(geometry, material);
    item.position.set(x, y, z);
    if (scale) item.scale.set(...scale);
    robot.add(item); return item;
  }
  mesh(new THREE.SphereGeometry(.83, 40, 28), shell, 0, .25, 0, [1.15, .85, .85]);
  mesh(new THREE.SphereGeometry(.7, 36, 24), dark, 0, .24, .4, [1.1, .65, .65]);
  const eyes = [-.29, .29].map(x => mesh(new THREE.CapsuleGeometry(.065, .12, 4, 10), glow, x, .28, .853));
  mesh(new THREE.TorusGeometry(.105, .018, 8, 24, Math.PI), teal, 0, .1, .86).rotation.z = Math.PI;
  mesh(new THREE.SphereGeometry(.39, 28, 20), shell, 0, -.65, -.02, [1.1, .72, .8]);
  mesh(new THREE.SphereGeometry(.105, 16, 12), glow, 0, -.63, .29);
  for (const x of [-1, 1]) {
    mesh(new THREE.SphereGeometry(.19, 20, 14), teal, x * .99, .2, 0, [.48, 1, 1]);
    mesh(new THREE.SphereGeometry(.13, 16, 12), shell, x * .61, -.61, 0, [.85, 1.6, .85]).rotation.z = x * .45;
  }
  mesh(new THREE.CylinderGeometry(.025, .025, .24, 12), dark, 0, 1.03, 0);
  mesh(new THREE.IcosahedronGeometry(.11, 1), glow, 0, 1.19, 0);
  const orbit = new THREE.Mesh(new THREE.TorusGeometry(1.36, .015, 8, 100), teal);
  orbit.rotation.set(1.24, .22, -.28); scene.add(orbit);
  const satellite = new THREE.Mesh(new THREE.IcosahedronGeometry(.07, 1), glow); scene.add(satellite);
  let frame = 0, visible = true, disposed = false, targetX = 0, targetY = 0;
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const started = performance.now();
  function draw(now = performance.now()) {
    frame = 0;
    if (disposed || document.hidden || !visible) return;
    const t = motion.matches ? 0 : (now - started) / 1000;
    robot.position.y = Math.sin(t * 1.5) * .055;
    robot.rotation.y += ((motion.matches ? -.12 : targetX - .12) - robot.rotation.y) * .08;
    robot.rotation.x += ((motion.matches ? .03 : targetY + .03) - robot.rotation.x) * .08;
    const blink = !motion.matches && t % 5.3 > 5.15 ? .18 : 1;
    eyes.forEach(eye => { eye.scale.y = blink; });
    satellite.position.set(Math.cos(t * .55) * 1.36, Math.sin(t * .55) * .42 - .12, Math.sin(t * .55) * 1.2);
    renderer.render(scene, camera);
    if (!motion.matches) frame = requestAnimationFrame(draw);
  }
  function resume() { if (!frame && !disposed) draw(); }
  function point(event) {
    const rect = canvas.getBoundingClientRect();
    targetX = ((event.clientX - rect.left) / rect.width - .5) * .65;
    targetY = ((event.clientY - rect.top) / rect.height - .5) * .3;
  }
  function reset() { targetX = targetY = 0; }
  const observer = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? false; resume(); });
  observer.observe(canvas);
  canvas.addEventListener("pointermove", point);
  canvas.addEventListener("pointerleave", reset);
  document.addEventListener("visibilitychange", resume);
  motion.addEventListener("change", resume);
  resume();
  return () => {
    disposed = true; cancelAnimationFrame(frame); observer.disconnect();
    canvas.removeEventListener("pointermove", point); canvas.removeEventListener("pointerleave", reset);
    document.removeEventListener("visibilitychange", resume); motion.removeEventListener("change", resume);
    scene.traverse(item => { if (item.isMesh) item.geometry.dispose(); });
    for (const material of [shell, dark, glow, teal]) material.dispose();
    renderer.dispose(); renderer.forceContextLoss();
  };
}
