/**
 * Viam SDK client connection for the kettle simulation.
 *
 * This module handles connecting to the Viam machine and provides
 * access to the arm and sensor components.
 */

import { createRobotClient, RobotClient } from '@viamrobotics/sdk';

export interface ConnectionConfig {
  host: string;
  apiKey?: string;
  apiKeyId?: string;
}

export interface JointPositions {
  values: number[];
}

export interface SensorReadings {
  fx: number;
  fy: number;
  fz: number;
  tx: number;
  ty: number;
  tz: number;
  trial_id: string;
  cycle_count: number;
  capture_state: string;
  should_sync: boolean;
}

export interface TrialStatus {
  active: boolean;
  trial_id: string;
  cycle_count: number;
}

export class ViamClient {
  private client: RobotClient | null = null;
  private armName = 'arm';
  private sensorName = 'force-sensor';
  private controllerName = 'cycle-controller';

  async connect(config: ConnectionConfig): Promise<void> {
    const credentials = config.apiKey
      ? { type: 'api-key' as const, payload: config.apiKey, authEntity: config.apiKeyId || '' }
      : undefined;

    this.client = await createRobotClient({
      host: config.host,
      credential: credentials,
      signalingAddress: `https://${config.host}`,
      // For local development without auth
      ...(credentials ? {} : { disableViamAuthenticationCredentials: true }),
    });
  }

  async disconnect(): Promise<void> {
    if (this.client) {
      await this.client.disconnect();
      this.client = null;
    }
  }

  isConnected(): boolean {
    return this.client !== null;
  }

  async getJointPositions(): Promise<JointPositions> {
    if (!this.client) {
      throw new Error('Not connected');
    }

    const arm = this.client.armClient(this.armName);
    const positions = await arm.getJointPositions();
    return { values: positions.values || [] };
  }

  async getSensorReadings(): Promise<SensorReadings> {
    if (!this.client) {
      throw new Error('Not connected');
    }

    const sensor = this.client.sensorClient(this.sensorName);
    const readings = await sensor.getReadings();

    return {
      fx: (readings.fx as number) || 0,
      fy: (readings.fy as number) || 0,
      fz: (readings.fz as number) || 0,
      tx: (readings.tx as number) || 0,
      ty: (readings.ty as number) || 0,
      tz: (readings.tz as number) || 0,
      trial_id: (readings.trial_id as string) || '',
      cycle_count: (readings.cycle_count as number) || 0,
      capture_state: (readings.capture_state as string) || 'idle',
      should_sync: (readings.should_sync as boolean) || false,
    };
  }

  async getTrialStatus(): Promise<TrialStatus> {
    if (!this.client) {
      throw new Error('Not connected');
    }

    const controller = this.client.genericClient(this.controllerName);
    const result = await controller.doCommand({ command: 'status' });

    return {
      active: (result.active as boolean) || false,
      trial_id: (result.trial_id as string) || '',
      cycle_count: (result.cycle_count as number) || 0,
    };
  }

  async startTrial(): Promise<void> {
    if (!this.client) {
      throw new Error('Not connected');
    }

    const controller = this.client.genericClient(this.controllerName);
    await controller.doCommand({ command: 'start' });
  }

  async stopTrial(): Promise<TrialStatus> {
    if (!this.client) {
      throw new Error('Not connected');
    }

    const controller = this.client.genericClient(this.controllerName);
    const result = await controller.doCommand({ command: 'stop' });

    return {
      active: false,
      trial_id: (result.trial_id as string) || '',
      cycle_count: (result.cycle_count as number) || 0,
    };
  }

  async executeSingleCycle(): Promise<void> {
    if (!this.client) {
      throw new Error('Not connected');
    }

    const controller = this.client.genericClient(this.controllerName);
    await controller.doCommand({ command: 'execute_cycle' });
  }
}
