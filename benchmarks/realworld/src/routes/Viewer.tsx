// A product preview in three.js: a lit torus knot on a pedestal, rendered once into a canvas, with
// the model's measurements.
import { useEffect, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import {
  AmbientLight, Box3, BoxGeometry, Color, CylinderGeometry, DirectionalLight, Group, Mesh, MeshStandardMaterial,
  PerspectiveCamera, Scene, TorusKnotGeometry, Vector3, WebGLRenderer,
} from 'three';

function model(): Group {
  const group = new Group();
  const knot = new Mesh(new TorusKnotGeometry(1, 0.32, 160, 24), new MeshStandardMaterial({ color: 0x1b4d89, metalness: 0.4, roughness: 0.35 }));
  knot.position.y = 1.6;
  const pedestal = new Mesh(new CylinderGeometry(1.2, 1.4, 0.5, 48), new MeshStandardMaterial({ color: 0x888888 }));
  pedestal.position.y = 0.25;
  const base = new Mesh(new BoxGeometry(3.2, 0.1, 3.2), new MeshStandardMaterial({ color: 0x333333 }));
  group.add(knot, pedestal, base);
  return group;
}

function vertices(group: Group): number {
  let count = 0;
  group.traverse((o) => {
    if (o instanceof Mesh) count += o.geometry.getAttribute('position').count;
  });
  return count;
}

export default function Viewer() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState('Preparing scene');
  const [stats] = useState(() => {
    const m = model();
    const size = new Box3().setFromObject(m).getSize(new Vector3());
    return { vertices: vertices(m), size: `${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)}` };
  });

  useEffect(() => {
    const scene = new Scene();
    scene.background = new Color(0xf4f6f8);
    scene.add(model(), new AmbientLight(0xffffff, 0.5));
    const sun = new DirectionalLight(0xffffff, 1.2);
    sun.position.set(3, 6, 4);
    scene.add(sun);
    const camera = new PerspectiveCamera(45, 4 / 3, 0.1, 100);
    camera.position.set(4, 3.5, 6);
    camera.lookAt(0, 1.2, 0);
    let renderer: WebGLRenderer | null = null;
    try {
      renderer = new WebGLRenderer({ canvas: canvas.current!, antialias: true, preserveDrawingBuffer: true });
      renderer.setSize(480, 360, false);
      renderer.render(scene, camera);
      setStatus('Rendered with WebGL');
    } catch {
      setStatus('Rendered without WebGL');
    }
    return () => renderer?.dispose();
  }, []);

  return (
    <Box>
      <Typography variant="h5">Product preview</Typography>
      <Typography>
        {stats.vertices} vertices · bounds {stats.size}
      </Typography>
      <canvas ref={canvas} width={480} height={360} />
      <Typography variant="caption" component="div">
        {status === 'Preparing scene' ? status : 'Scene ready'}
      </Typography>
    </Box>
  );
}
