export type ClusterMode = "face" | "face+body";

export type JobStatus = "ready" | "clustering" | "done" | "error" | "cancelled";

export type ClusterSettings = {
  threshold: number;
  min_images: number;
  mode: ClusterMode;
  subject_prefix: string;
  download_models: boolean;
  keep_names: boolean;
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
};
