/**
 * Three.js robot arm visualizer.
 *
 * Creates a 3D scene with a simplified Lite6 robot arm and updates
 * joint positions in real-time based on simulation data.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Lite6 link dimensions (matching MJCF model)
const LINK_DIMS = {
  base: { radius: 0.06, height: 0.05 },
  link1: { radius: 0.05, height: 0.123 },
  link2: { radius: 0.04, height: 0.2 },
  link3: { radius: 0.035, height: 0.09 },
  link4: { radius: 0.03, height: 0.15 },
  link5: { radius: 0.025, height: 0.08 },
  link6: { radius: 0.025, height: 0.06 },
};

// Joint rotation axes
const JOINT_AXES = [
  new THREE.Vector3(0, 0, 1), // joint1: Z
  new THREE.Vector3(0, 1, 0), // joint2: Y
  new THREE.Vector3(0, 1, 0), // joint3: Y
  new THREE.Vector3(0, 0, 1), // joint4: Z
  new THREE.Vector3(0, 1, 0), // joint5: Y
  new THREE.Vector3(0, 0, 1), // joint6: Z
];

export class RobotVisualizer {
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private controls: OrbitControls;
  private joints: THREE.Object3D[] = [];
  private animationId: number | null = null;

  constructor(canvas: HTMLCanvasElement) {
    // Scene setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1a1a2e);

    // Camera setup
    const aspect = canvas.clientWidth / canvas.clientHeight;
    this.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
    this.camera.position.set(1, 0.8, 1);
    this.camera.lookAt(0, 0.3, 0);

    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);

    // Orbit controls
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.set(0, 0.3, 0);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;

    // Lighting
    this.setupLighting();

    // Create robot arm
    this.createRobot();

    // Create ground plane
    this.createGround();

    // Create table
    this.createTable();

    // Handle resize
    window.addEventListener('resize', () => this.onResize(canvas));

    // Start render loop
    this.animate();
  }

  private setupLighting(): void {
    // Ambient light
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambient);

    // Main directional light
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 10, 5);
    dirLight.castShadow = true;
    this.scene.add(dirLight);

    // Fill light
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-5, 5, -5);
    this.scene.add(fillLight);
  }

  private createGround(): void {
    const geometry = new THREE.PlaneGeometry(10, 10);
    const material = new THREE.MeshStandardMaterial({
      color: 0x2c3e50,
      roughness: 0.8,
    });
    const ground = new THREE.Mesh(geometry, material);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // Grid helper
    const grid = new THREE.GridHelper(10, 20, 0x0f3460, 0x0f3460);
    grid.position.y = 0.001;
    this.scene.add(grid);
  }

  private createTable(): void {
    const geometry = new THREE.BoxGeometry(0.6, 0.02, 0.8);
    const material = new THREE.MeshStandardMaterial({
      color: 0x8b4513,
      roughness: 0.7,
    });
    const table = new THREE.Mesh(geometry, material);
    table.position.set(0.4, 0.35, 0);
    this.scene.add(table);
  }

  private createRobot(): void {
    // Materials
    const baseMaterial = new THREE.MeshStandardMaterial({
      color: 0x333333,
      roughness: 0.5,
    });
    const linkMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.3,
    });
    const endMaterial = new THREE.MeshStandardMaterial({
      color: 0x444444,
      roughness: 0.5,
    });

    // Base link
    const base = this.createLink(LINK_DIMS.base, baseMaterial);
    base.position.y = LINK_DIMS.base.height / 2;
    this.scene.add(base);

    // Joint 1 pivot (rotates around Z)
    const joint1 = new THREE.Object3D();
    joint1.position.y = LINK_DIMS.base.height / 2;
    base.add(joint1);
    this.joints.push(joint1);

    // Link 1
    const link1 = this.createLink(LINK_DIMS.link1, linkMaterial);
    link1.position.y = LINK_DIMS.link1.height / 2;
    joint1.add(link1);

    // Joint 2 pivot (rotates around Y)
    const joint2 = new THREE.Object3D();
    joint2.position.y = LINK_DIMS.link1.height / 2;
    link1.add(joint2);
    this.joints.push(joint2);

    // Link 2
    const link2 = this.createLink(LINK_DIMS.link2, linkMaterial);
    link2.position.y = LINK_DIMS.link2.height / 2;
    joint2.add(link2);

    // Joint 3 pivot (rotates around Y)
    const joint3 = new THREE.Object3D();
    joint3.position.y = LINK_DIMS.link2.height / 2;
    link2.add(joint3);
    this.joints.push(joint3);

    // Link 3
    const link3 = this.createLink(LINK_DIMS.link3, linkMaterial);
    link3.position.y = LINK_DIMS.link3.height / 2;
    joint3.add(link3);

    // Joint 4 pivot (rotates around Z)
    const joint4 = new THREE.Object3D();
    joint4.position.y = LINK_DIMS.link3.height / 2;
    link3.add(joint4);
    this.joints.push(joint4);

    // Link 4
    const link4 = this.createLink(LINK_DIMS.link4, linkMaterial);
    link4.position.y = LINK_DIMS.link4.height / 2;
    joint4.add(link4);

    // Joint 5 pivot (rotates around Y)
    const joint5 = new THREE.Object3D();
    joint5.position.y = LINK_DIMS.link4.height / 2;
    link4.add(joint5);
    this.joints.push(joint5);

    // Link 5
    const link5 = this.createLink(LINK_DIMS.link5, linkMaterial);
    link5.position.y = LINK_DIMS.link5.height / 2;
    joint5.add(link5);

    // Joint 6 pivot (rotates around Z)
    const joint6 = new THREE.Object3D();
    joint6.position.y = LINK_DIMS.link5.height / 2;
    link5.add(joint6);
    this.joints.push(joint6);

    // Link 6 (end effector)
    const link6 = this.createLink(LINK_DIMS.link6, endMaterial);
    link6.position.y = LINK_DIMS.link6.height / 2;
    joint6.add(link6);

    // End effector marker
    const markerGeometry = new THREE.SphereGeometry(0.02);
    const markerMaterial = new THREE.MeshStandardMaterial({
      color: 0xff0000,
      emissive: 0xff0000,
      emissiveIntensity: 0.5,
    });
    const marker = new THREE.Mesh(markerGeometry, markerMaterial);
    marker.position.y = LINK_DIMS.link6.height / 2;
    link6.add(marker);
  }

  private createLink(
    dims: { radius: number; height: number },
    material: THREE.Material
  ): THREE.Mesh {
    const geometry = new THREE.CylinderGeometry(
      dims.radius,
      dims.radius,
      dims.height,
      16
    );
    return new THREE.Mesh(geometry, material);
  }

  /**
   * Update joint positions from simulation data.
   *
   * @param positions Joint angles in degrees
   */
  updateJointPositions(positions: number[]): void {
    if (positions.length !== 6) return;

    for (let i = 0; i < 6; i++) {
      const angle = (positions[i] * Math.PI) / 180; // Convert to radians
      const axis = JOINT_AXES[i];

      // Reset rotation and apply new angle around the joint axis
      this.joints[i].rotation.set(0, 0, 0);

      if (axis.z === 1) {
        this.joints[i].rotation.z = angle;
      } else if (axis.y === 1) {
        this.joints[i].rotation.y = angle;
      }
    }
  }

  private animate(): void {
    this.animationId = requestAnimationFrame(() => this.animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  private onResize(canvas: HTMLCanvasElement): void {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
  }

  dispose(): void {
    if (this.animationId !== null) {
      cancelAnimationFrame(this.animationId);
    }
    this.renderer.dispose();
  }
}
