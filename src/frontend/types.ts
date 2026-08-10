export type AnyRecord = Record<string, any> & { id: string };

export interface Status {
  configured: boolean;
  version: string;
  database_schema: number;
  export_schema: number;
  backup_format: number;
  ai: AIStatus;
}

export interface AIStatus {
  available: boolean;
  provider: string;
  selected_model?: string | null;
  models: Array<{ name: string; size: number }>;
  message?: string;
}

export interface BackupHealth {
  score: number;
  label: string;
  warnings: string[];
  last_successful?: AnyRecord | null;
  last_verified?: AnyRecord | null;
  destinations: AnyRecord[];
  runs: AnyRecord[];
}

export interface DashboardData {
  profiles: AnyRecord[];
  appointments: AnyRecord[];
  reminders: AnyRecord[];
  follow_ups: AnyRecord[];
  recent: AnyRecord[];
  backup: BackupHealth;
}
