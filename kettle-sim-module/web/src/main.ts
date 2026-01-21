/**
 * Main entry point for the kettle simulation web visualizer.
 *
 * This module:
 * - Initializes the Three.js visualization
 * - Manages connection to the Viam machine
 * - Polls for joint positions and sensor data
 * - Handles user interactions (start/stop trial, etc.)
 */

import { RobotVisualizer } from './robot-visualizer';
import { ViamClient, TrialStatus } from './viam-client';

// UI Elements
const canvas = document.getElementById('canvas') as HTMLCanvasElement;
const statusDot = document.getElementById('status-dot') as HTMLElement;
const statusText = document.getElementById('status-text') as HTMLElement;
const hostInput = document.getElementById('host') as HTMLInputElement;
const apiKeyInput = document.getElementById('api-key') as HTMLInputElement;
const connectBtn = document.getElementById('connect-btn') as HTMLButtonElement;
const startTrialBtn = document.getElementById('start-trial-btn') as HTMLButtonElement;
const stopTrialBtn = document.getElementById('stop-trial-btn') as HTMLButtonElement;
const singleCycleBtn = document.getElementById('single-cycle-btn') as HTMLButtonElement;
const trialStatusEl = document.getElementById('trial-status') as HTMLElement;
const cycleCountEl = document.getElementById('cycle-count') as HTMLElement;
const trialIdEl = document.getElementById('trial-id') as HTMLElement;
const forceZEl = document.getElementById('force-z') as HTMLElement;
const logEl = document.getElementById('log') as HTMLElement;

// Joint position elements
const jointEls = [
  document.getElementById('j1') as HTMLElement,
  document.getElementById('j2') as HTMLElement,
  document.getElementById('j3') as HTMLElement,
  document.getElementById('j4') as HTMLElement,
  document.getElementById('j5') as HTMLElement,
  document.getElementById('j6') as HTMLElement,
];

// Global state
let visualizer: RobotVisualizer | null = null;
let viamClient: ViamClient | null = null;
let pollInterval: number | null = null;

/**
 * Log a message to the UI log panel.
 */
function log(message: string, type: 'info' | 'error' | 'success' = 'info'): void {
  const entry = document.createElement('div');
  entry.className = `entry ${type}`;
  entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;

  // Keep only last 50 entries
  while (logEl.children.length > 50) {
    logEl.removeChild(logEl.children[0]);
  }
}

/**
 * Update connection status UI.
 */
function setConnectionStatus(status: 'disconnected' | 'connecting' | 'connected' | 'error'): void {
  statusDot.className = 'status-dot';

  switch (status) {
    case 'disconnected':
      statusText.textContent = 'Disconnected';
      connectBtn.textContent = 'Connect';
      connectBtn.disabled = false;
      break;
    case 'connecting':
      statusText.textContent = 'Connecting...';
      connectBtn.textContent = 'Connecting...';
      connectBtn.disabled = true;
      break;
    case 'connected':
      statusDot.classList.add('connected');
      statusText.textContent = 'Connected';
      connectBtn.textContent = 'Disconnect';
      connectBtn.disabled = false;
      break;
    case 'error':
      statusDot.classList.add('error');
      statusText.textContent = 'Error';
      connectBtn.textContent = 'Retry';
      connectBtn.disabled = false;
      break;
  }

  // Enable/disable control buttons based on connection
  const connected = status === 'connected';
  startTrialBtn.disabled = !connected;
  stopTrialBtn.disabled = !connected;
  singleCycleBtn.disabled = !connected;
}

/**
 * Update joint position display.
 */
function updateJointDisplay(positions: number[]): void {
  for (let i = 0; i < 6 && i < positions.length; i++) {
    jointEls[i].textContent = positions[i].toFixed(1);
  }
}

/**
 * Update trial status display.
 */
function updateTrialDisplay(status: TrialStatus): void {
  trialStatusEl.textContent = status.active ? 'Active' : 'Idle';
  cycleCountEl.textContent = status.cycle_count.toString();
  trialIdEl.textContent = status.trial_id || '-';

  // Update button states
  startTrialBtn.disabled = status.active;
  stopTrialBtn.disabled = !status.active;
  singleCycleBtn.disabled = status.active;
}

/**
 * Poll for simulation data.
 */
async function pollData(): Promise<void> {
  if (!viamClient || !viamClient.isConnected()) return;

  try {
    // Get joint positions
    const positions = await viamClient.getJointPositions();
    updateJointDisplay(positions.values);

    // Update 3D visualization
    if (visualizer) {
      visualizer.updateJointPositions(positions.values);
    }

    // Get sensor readings
    const readings = await viamClient.getSensorReadings();
    forceZEl.textContent = readings.fz.toFixed(2);

    // Get trial status
    const status = await viamClient.getTrialStatus();
    updateTrialDisplay(status);
  } catch (error) {
    // Silent fail for polling - don't spam the log
    console.error('Poll error:', error);
  }
}

/**
 * Connect to the Viam machine.
 */
async function connect(): Promise<void> {
  const host = hostInput.value.trim();
  if (!host) {
    log('Please enter a host address', 'error');
    return;
  }

  setConnectionStatus('connecting');
  log(`Connecting to ${host}...`);

  try {
    viamClient = new ViamClient();
    await viamClient.connect({
      host,
      apiKey: apiKeyInput.value.trim() || undefined,
    });

    setConnectionStatus('connected');
    log('Connected successfully', 'success');

    // Start polling
    pollInterval = window.setInterval(pollData, 50); // 20Hz
  } catch (error) {
    setConnectionStatus('error');
    log(`Connection failed: ${error}`, 'error');
    viamClient = null;
  }
}

/**
 * Disconnect from the Viam machine.
 */
async function disconnect(): Promise<void> {
  if (pollInterval !== null) {
    clearInterval(pollInterval);
    pollInterval = null;
  }

  if (viamClient) {
    await viamClient.disconnect();
    viamClient = null;
  }

  setConnectionStatus('disconnected');
  log('Disconnected');
}

/**
 * Handle connect/disconnect button click.
 */
async function handleConnectClick(): Promise<void> {
  if (viamClient && viamClient.isConnected()) {
    await disconnect();
  } else {
    await connect();
  }
}

/**
 * Start a new trial.
 */
async function handleStartTrial(): Promise<void> {
  if (!viamClient) return;

  try {
    await viamClient.startTrial();
    log('Trial started', 'success');
  } catch (error) {
    log(`Failed to start trial: ${error}`, 'error');
  }
}

/**
 * Stop the current trial.
 */
async function handleStopTrial(): Promise<void> {
  if (!viamClient) return;

  try {
    const result = await viamClient.stopTrial();
    log(`Trial stopped. Cycles: ${result.cycle_count}`, 'success');
  } catch (error) {
    log(`Failed to stop trial: ${error}`, 'error');
  }
}

/**
 * Execute a single cycle.
 */
async function handleSingleCycle(): Promise<void> {
  if (!viamClient) return;

  try {
    singleCycleBtn.disabled = true;
    await viamClient.executeSingleCycle();
    log('Cycle executed', 'success');
  } catch (error) {
    log(`Failed to execute cycle: ${error}`, 'error');
  } finally {
    singleCycleBtn.disabled = false;
  }
}

/**
 * Initialize the application.
 */
function init(): void {
  // Initialize 3D visualizer
  visualizer = new RobotVisualizer(canvas);
  log('3D visualizer initialized');

  // Set up event listeners
  connectBtn.addEventListener('click', handleConnectClick);
  startTrialBtn.addEventListener('click', handleStartTrial);
  stopTrialBtn.addEventListener('click', handleStopTrial);
  singleCycleBtn.addEventListener('click', handleSingleCycle);

  // Initialize UI state
  setConnectionStatus('disconnected');

  log('Ready to connect');
}

// Start the application
init();
