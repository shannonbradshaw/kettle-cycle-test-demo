/**
 * Three.js robot arm visualizer.
 *
 * Creates a 3D scene with a simplified Lite6 robot arm, gripper,
 * and kettle. Updates joint positions in real-time.
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
    this.camera.position.set(0.6, 0.7, 0.9);
    this.camera.lookAt(0.15, 0.4, 0);

    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Orbit controls
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.set(0.15, 0.4, 0);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;

    // Lighting
    this.setupLighting();

    // Create scene elements
    this.createGround();
    this.createTable();
    this.createKettle();
    this.createRobot();

    // Set initial joint positions for gripping pose
    this.setInitialGrippingPose();

    // Handle resize
    window.addEventListener('resize', () => this.onResize(canvas));

    // Start render loop
    this.animate();
  }

  private setupLighting(): void {
    // Ambient light
    const ambient = new THREE.AmbientLight(0xffffff, 0.5);
    this.scene.add(ambient);

    // Main directional light with shadows
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(3, 5, 3);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 0.1;
    dirLight.shadow.camera.far = 20;
    dirLight.shadow.camera.left = -2;
    dirLight.shadow.camera.right = 2;
    dirLight.shadow.camera.top = 2;
    dirLight.shadow.camera.bottom = -2;
    this.scene.add(dirLight);

    // Fill light
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-3, 3, -3);
    this.scene.add(fillLight);

    // Rim light for better depth
    const rimLight = new THREE.DirectionalLight(0x88ccff, 0.2);
    rimLight.position.set(0, 2, -5);
    this.scene.add(rimLight);
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
    const tableHeight = 0.35;
    const tableWidth = 0.8;
    const tableDepth = 0.6;

    // Aluminum extrusion material (80/20 style)
    const extrusionMaterial = new THREE.MeshStandardMaterial({
      color: 0xb0b0b0,
      roughness: 0.4,
      metalness: 0.7,
    });

    // Work surface material (phenolic/black composite)
    const surfaceMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a1a,
      roughness: 0.6,
      metalness: 0.1,
    });

    // Table top (phenolic work surface)
    const topGeometry = new THREE.BoxGeometry(tableWidth, 0.025, tableDepth);
    const tableTop = new THREE.Mesh(topGeometry, surfaceMaterial);
    tableTop.position.set(0.3, tableHeight, 0);
    tableTop.castShadow = true;
    tableTop.receiveShadow = true;
    this.scene.add(tableTop);

    // Aluminum extrusion profile size
    const extrusionSize = 0.04;

    // Create extrusion segment helper
    const createExtrusion = (length: number, vertical: boolean = false) => {
      const geo = vertical
        ? new THREE.BoxGeometry(extrusionSize, length, extrusionSize)
        : new THREE.BoxGeometry(length, extrusionSize, extrusionSize);
      return new THREE.Mesh(geo, extrusionMaterial);
    };

    // Vertical legs (4 corners)
    const legHeight = tableHeight - 0.025;
    const legPositions = [
      [-0.1 + extrusionSize / 2, legHeight / 2, tableDepth / 2 - extrusionSize / 2],
      [0.7 - extrusionSize / 2, legHeight / 2, tableDepth / 2 - extrusionSize / 2],
      [-0.1 + extrusionSize / 2, legHeight / 2, -tableDepth / 2 + extrusionSize / 2],
      [0.7 - extrusionSize / 2, legHeight / 2, -tableDepth / 2 + extrusionSize / 2],
    ];
    legPositions.forEach(([x, y, z]) => {
      const leg = createExtrusion(legHeight, true);
      leg.position.set(x, y, z);
      leg.castShadow = true;
      this.scene.add(leg);
    });

    // Top frame rails (along X)
    const topRailY = tableHeight - 0.025 - extrusionSize / 2;
    const topRailLength = tableWidth;
    [[tableDepth / 2 - extrusionSize / 2], [-tableDepth / 2 + extrusionSize / 2]].forEach(([z]) => {
      const rail = createExtrusion(topRailLength);
      rail.position.set(0.3, topRailY, z);
      rail.castShadow = true;
      this.scene.add(rail);
    });

    // Top frame rails (along Z)
    const sideRailLength = tableDepth - extrusionSize * 2;
    [[-0.1 + extrusionSize / 2], [0.7 - extrusionSize / 2]].forEach(([x]) => {
      const rail = createExtrusion(sideRailLength);
      rail.rotation.y = Math.PI / 2;
      rail.position.set(x, topRailY, 0);
      rail.castShadow = true;
      this.scene.add(rail);
    });

    // Bottom cross braces (for stability, like real workbenches)
    const braceY = 0.1;
    // Front and back braces
    [[tableDepth / 2 - extrusionSize / 2], [-tableDepth / 2 + extrusionSize / 2]].forEach(([z]) => {
      const brace = createExtrusion(topRailLength);
      brace.position.set(0.3, braceY, z);
      brace.castShadow = true;
      this.scene.add(brace);
    });

    // Side braces
    [[-0.1 + extrusionSize / 2], [0.7 - extrusionSize / 2]].forEach(([x]) => {
      const brace = createExtrusion(sideRailLength);
      brace.rotation.y = Math.PI / 2;
      brace.position.set(x, braceY, 0);
      brace.castShadow = true;
      this.scene.add(brace);
    });

    // Corner gussets (triangular braces at top corners)
    const gussetMaterial = new THREE.MeshStandardMaterial({
      color: 0x909090,
      roughness: 0.5,
      metalness: 0.6,
    });
    const gussetShape = new THREE.Shape();
    gussetShape.moveTo(0, 0);
    gussetShape.lineTo(0.06, 0);
    gussetShape.lineTo(0, -0.06);
    gussetShape.closePath();
    const gussetGeometry = new THREE.ExtrudeGeometry(gussetShape, {
      depth: 0.005,
      bevelEnabled: false,
    });

    // Add gussets at each corner
    const gussetPositions = [
      { x: -0.1 + extrusionSize, y: topRailY + extrusionSize / 2, z: tableDepth / 2 - extrusionSize, rotY: 0 },
      { x: 0.7 - extrusionSize, y: topRailY + extrusionSize / 2, z: tableDepth / 2 - extrusionSize, rotY: Math.PI / 2 },
      { x: -0.1 + extrusionSize, y: topRailY + extrusionSize / 2, z: -tableDepth / 2 + extrusionSize, rotY: -Math.PI / 2 },
      { x: 0.7 - extrusionSize, y: topRailY + extrusionSize / 2, z: -tableDepth / 2 + extrusionSize, rotY: Math.PI },
    ];
    gussetPositions.forEach(({ x, y, z, rotY }) => {
      const gusset = new THREE.Mesh(gussetGeometry, gussetMaterial);
      gusset.position.set(x, y, z);
      gusset.rotation.set(Math.PI / 2, rotY, 0);
      this.scene.add(gusset);
    });
  }

  private createKettle(): void {
    const kettleGroup = new THREE.Group();

    // Kettle body (main cylinder with slight taper)
    const bodyGeometry = new THREE.CylinderGeometry(0.06, 0.07, 0.12, 24);
    const kettleMaterial = new THREE.MeshStandardMaterial({
      color: 0xc0c0c0,
      metalness: 0.8,
      roughness: 0.2,
    });
    const body = new THREE.Mesh(bodyGeometry, kettleMaterial);
    body.position.y = 0.06;
    body.castShadow = true;
    kettleGroup.add(body);

    // Kettle bottom (rounded)
    const bottomGeometry = new THREE.SphereGeometry(0.07, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
    const bottom = new THREE.Mesh(bottomGeometry, kettleMaterial);
    bottom.rotation.x = Math.PI;
    bottom.castShadow = true;
    kettleGroup.add(bottom);

    // Kettle lid
    const lidGeometry = new THREE.CylinderGeometry(0.05, 0.06, 0.02, 24);
    const lid = new THREE.Mesh(lidGeometry, kettleMaterial);
    lid.position.y = 0.13;
    lid.castShadow = true;
    kettleGroup.add(lid);

    // Lid knob
    const knobGeometry = new THREE.SphereGeometry(0.015, 12, 12);
    const knobMaterial = new THREE.MeshStandardMaterial({
      color: 0x222222,
      roughness: 0.5,
    });
    const knob = new THREE.Mesh(knobGeometry, knobMaterial);
    knob.position.y = 0.15;
    kettleGroup.add(knob);

    // Spout
    const spoutCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(0.06, 0.06, 0),
      new THREE.Vector3(0.12, 0.08, 0),
      new THREE.Vector3(0.13, 0.14, 0)
    );
    const spoutGeometry = new THREE.TubeGeometry(spoutCurve, 12, 0.012, 8, false);
    const spout = new THREE.Mesh(spoutGeometry, kettleMaterial);
    spout.castShadow = true;
    kettleGroup.add(spout);

    // Handle
    const handleCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(-0.06, 0.04, 0),
      new THREE.Vector3(-0.12, 0.08, 0),
      new THREE.Vector3(-0.06, 0.12, 0)
    );
    const handleGeometry = new THREE.TubeGeometry(handleCurve, 12, 0.01, 8, false);
    const handleMaterial = new THREE.MeshStandardMaterial({
      color: 0x333333,
      roughness: 0.6,
    });
    const handle = new THREE.Mesh(handleGeometry, handleMaterial);
    handle.castShadow = true;
    kettleGroup.add(handle);

    // Position kettle on table (to the right of arm)
    // Rotated so handle faces the arm for gripping
    kettleGroup.position.set(0.35, 0.365, 0);
    kettleGroup.rotation.y = Math.PI; // Handle faces arm
    this.scene.add(kettleGroup);
  }

  private createRobot(): void {
    // Mount position: on the table surface
    const tableHeight = 0.35;
    const mountX = 0.0; // Left side of table
    const mountZ = 0.0; // Center front-to-back

    // Materials
    const baseMaterial = new THREE.MeshStandardMaterial({
      color: 0x2a2a2a,
      roughness: 0.4,
      metalness: 0.6,
    });
    const linkMaterial = new THREE.MeshStandardMaterial({
      color: 0xf0f0f0,
      roughness: 0.3,
      metalness: 0.4,
    });
    const accentMaterial = new THREE.MeshStandardMaterial({
      color: 0x3498db,
      roughness: 0.4,
      metalness: 0.5,
    });
    const endMaterial = new THREE.MeshStandardMaterial({
      color: 0x444444,
      roughness: 0.5,
      metalness: 0.6,
    });

    // Mounting plate (bolted to table)
    const mountPlate = new THREE.Mesh(
      new THREE.CylinderGeometry(0.08, 0.08, 0.01, 24),
      baseMaterial
    );
    mountPlate.position.set(mountX, tableHeight + 0.005, mountZ);
    mountPlate.castShadow = true;
    this.scene.add(mountPlate);

    // Mounting bolts
    const boltMaterial = new THREE.MeshStandardMaterial({
      color: 0x666666,
      metalness: 0.8,
      roughness: 0.3,
    });
    const boltGeometry = new THREE.CylinderGeometry(0.006, 0.006, 0.008, 8);
    const boltPositions = [
      [0.055, 0], [-0.055, 0], [0, 0.055], [0, -0.055],
    ];
    boltPositions.forEach(([dx, dz]) => {
      const bolt = new THREE.Mesh(boltGeometry, boltMaterial);
      bolt.position.set(mountX + dx, tableHeight + 0.014, mountZ + dz);
      this.scene.add(bolt);
    });

    // Base link
    const base = this.createLink(LINK_DIMS.base, baseMaterial);
    base.position.set(mountX, tableHeight + 0.01 + LINK_DIMS.base.height / 2, mountZ);
    base.castShadow = true;
    this.scene.add(base);

    // Base accent ring
    const baseRing = new THREE.Mesh(
      new THREE.TorusGeometry(0.055, 0.008, 8, 24),
      accentMaterial
    );
    baseRing.rotation.x = Math.PI / 2;
    baseRing.position.y = LINK_DIMS.base.height;
    base.add(baseRing);

    // Joint 1 pivot (rotates around Z)
    const joint1 = new THREE.Object3D();
    joint1.position.y = LINK_DIMS.base.height / 2;
    base.add(joint1);
    this.joints.push(joint1);

    // Link 1
    const link1 = this.createLink(LINK_DIMS.link1, linkMaterial);
    link1.position.y = LINK_DIMS.link1.height / 2;
    link1.castShadow = true;
    joint1.add(link1);

    // Joint 2 pivot (rotates around Y)
    const joint2 = new THREE.Object3D();
    joint2.position.y = LINK_DIMS.link1.height / 2;
    link1.add(joint2);
    this.joints.push(joint2);

    // Link 2
    const link2 = this.createLink(LINK_DIMS.link2, linkMaterial);
    link2.position.y = LINK_DIMS.link2.height / 2;
    link2.castShadow = true;
    joint2.add(link2);

    // Joint 3 pivot (rotates around Y)
    const joint3 = new THREE.Object3D();
    joint3.position.y = LINK_DIMS.link2.height / 2;
    link2.add(joint3);
    this.joints.push(joint3);

    // Link 3
    const link3 = this.createLink(LINK_DIMS.link3, linkMaterial);
    link3.position.y = LINK_DIMS.link3.height / 2;
    link3.castShadow = true;
    joint3.add(link3);

    // Joint 4 pivot (rotates around Z)
    const joint4 = new THREE.Object3D();
    joint4.position.y = LINK_DIMS.link3.height / 2;
    link3.add(joint4);
    this.joints.push(joint4);

    // Link 4
    const link4 = this.createLink(LINK_DIMS.link4, linkMaterial);
    link4.position.y = LINK_DIMS.link4.height / 2;
    link4.castShadow = true;
    joint4.add(link4);

    // Joint 5 pivot (rotates around Y)
    const joint5 = new THREE.Object3D();
    joint5.position.y = LINK_DIMS.link4.height / 2;
    link4.add(joint5);
    this.joints.push(joint5);

    // Link 5
    const link5 = this.createLink(LINK_DIMS.link5, linkMaterial);
    link5.position.y = LINK_DIMS.link5.height / 2;
    link5.castShadow = true;
    joint5.add(link5);

    // Joint 6 pivot (rotates around Z)
    const joint6 = new THREE.Object3D();
    joint6.position.y = LINK_DIMS.link5.height / 2;
    link5.add(joint6);
    this.joints.push(joint6);

    // Link 6 (wrist)
    const link6 = this.createLink(LINK_DIMS.link6, endMaterial);
    link6.position.y = LINK_DIMS.link6.height / 2;
    link6.castShadow = true;
    joint6.add(link6);

    // Create gripper end effector
    const gripper = this.createGripper();
    gripper.position.y = LINK_DIMS.link6.height / 2 + 0.01;
    link6.add(gripper);
  }

  private createGripper(): THREE.Group {
    const gripper = new THREE.Group();

    const gripperMaterial = new THREE.MeshStandardMaterial({
      color: 0x333333,
      roughness: 0.5,
      metalness: 0.7,
    });

    const fingerMaterial = new THREE.MeshStandardMaterial({
      color: 0x555555,
      roughness: 0.6,
      metalness: 0.5,
    });

    // Gripper base plate (wider to accommodate larger fingers)
    const basePlate = new THREE.Mesh(
      new THREE.BoxGeometry(0.07, 0.018, 0.05),
      gripperMaterial
    );
    basePlate.position.y = 0.009;
    basePlate.castShadow = true;
    gripper.add(basePlate);

    // Gripper mounting cylinder
    const mount = new THREE.Mesh(
      new THREE.CylinderGeometry(0.018, 0.022, 0.025, 12),
      gripperMaterial
    );
    mount.position.y = 0.03;
    mount.castShadow = true;
    gripper.add(mount);

    // Left finger (spacing for kettle handle ~0.02m diameter)
    const leftFinger = this.createGripperFinger(fingerMaterial);
    leftFinger.position.set(-0.022, 0.018, 0);
    gripper.add(leftFinger);

    // Right finger
    const rightFinger = this.createGripperFinger(fingerMaterial);
    rightFinger.position.set(0.022, 0.018, 0);
    rightFinger.scale.x = -1;
    gripper.add(rightFinger);

    return gripper;
  }

  private createGripperFinger(material: THREE.Material): THREE.Group {
    const finger = new THREE.Group();

    // Finger base (wider)
    const fingerBase = new THREE.Mesh(
      new THREE.BoxGeometry(0.018, 0.03, 0.035),
      material
    );
    fingerBase.position.y = 0.015;
    fingerBase.castShadow = true;
    finger.add(fingerBase);

    // Finger tip (wider and longer for better grip)
    const tipGeometry = new THREE.BoxGeometry(0.012, 0.045, 0.03);
    const tip = new THREE.Mesh(tipGeometry, material);
    tip.position.set(0.005, 0.0525, 0);
    tip.rotation.z = -0.1;
    tip.castShadow = true;
    finger.add(tip);

    // Grip pad (wider rubber surface for better contact)
    const padMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a1a,
      roughness: 0.95,
    });
    const pad = new THREE.Mesh(
      new THREE.BoxGeometry(0.004, 0.035, 0.025),
      padMaterial
    );
    pad.position.set(0.012, 0.055, 0);
    finger.add(pad);

    return finger;
  }

  private createLink(
    dims: { radius: number; height: number },
    material: THREE.Material
  ): THREE.Mesh {
    const geometry = new THREE.CylinderGeometry(
      dims.radius,
      dims.radius,
      dims.height,
      24
    );
    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  /**
   * Set initial gripping pose for the arm.
   * Positions the arm to grip the kettle handle.
   */
  private setInitialGrippingPose(): void {
    // Joint angles in degrees for gripping pose:
    // The arm reaches from left side of table to kettle on right
    // Joint 1: Base rotation toward kettle (positive = CCW from above)
    // Joint 2: Shoulder flexion (reach forward/down)
    // Joint 3: Elbow flexion
    // Joint 4: Wrist rotation
    // Joint 5: Wrist pitch (angle gripper)
    // Joint 6: Tool rotation (orient gripper to handle)
    const grippingPose = [
      15,   // Joint 1: slight rotation toward kettle
      45,   // Joint 2: shoulder forward
      -30,  // Joint 3: elbow bend
      0,    // Joint 4: wrist rotation
      -75,  // Joint 5: wrist pitch down toward handle
      90,   // Joint 6: orient gripper perpendicular to handle
    ];

    this.updateJointPositions(grippingPose);
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
