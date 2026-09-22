export type ClusterMode = "face" | "face+body";

export type JobStatus = "ready" | "clustering" | "done" | "error" | "cancelled";

export type ShareProtocol = "smb" | "sftp" | "ftp";

export type ClusterSettings = {
  threshold: number;
  min_images: number;
  mode: ClusterMode;
  subject_prefix: string;
  download_models: boolean;
  keep_names: boolean;
  yunet: "2023mar" | "2023mar_int8" | "2023mar_int8bq" | "2026may";
  sface: "2021dec" | "2021dec_int8" | "2021dec_int8bq";
};

export type ShareRequest = {
  protocol: ShareProtocol;
  host: string;
  port: string;
  path: string;
  username: string;
  password: string;
  private_key: string;
};

export type JobImage = {
  id: string;
  filename: string;
  skipped: boolean;
  skip_reason: string | null;
  unmatched: boolean;
  unmatched_reason: string | null;
};

export type JobCluster = {
  id: string;
  name: string;
  image_ids: string[];
  included: boolean;
  below_min: boolean;
};

export type JobProgress = {
  phase: string;
  completed: number;
  total: number;
  detail: string;
  logs: string[];
};

export type Job = {
  id: string;
  status: JobStatus;
  source: string;
  settings: ClusterSettings | null;
  progress: JobProgress;
  clusters: JobCluster[];
  images: JobImage[];
  notes: string[];
  backend_name: string;
  scanned: number;
  error: string | null;
};

export type Health = {
  ok: boolean;
  version: string;
  privacy: string;
  models_dir: string;
  models_ready: boolean;
  models?: {
    models_dir: string;
    yunet: ModelSpec[];
    sface: ModelSpec[];
    default_yunet: string;
    default_sface: string;
  };
};

export type ModelSpec = {
  id: string;
  filename: string;
  label: string;
  notes: string;
  ready: boolean;
  bundled?: boolean;
  bytes: number;
  family?: string;
  path?: string;
  source?: string;
};

export type ModelStatus = {
  models_dir: string;
  home?: string;
  yunet: ModelSpec[];
  sface: ModelSpec[];
  default_yunet: string;
  default_sface: string;
  expected?: number;
  yunet_count?: number;
  sface_count?: number;
  missing: ModelSpec[];
  missing_count: number;
  ready: boolean;
  catalog_ready?: boolean;
  all_ready?: boolean;
  install_command?: string;
  curl_script?: string;
};

export type ModelDownloadTask = {
  id: string;
  status: "running" | "done" | "error";
  logs: string[];
  error: string | null;
  missing: ModelSpec[];
  missing_count: number;
  models_dir?: string;
};
