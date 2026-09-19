import type { ClusterSettings, Health, Job } from "./types";

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function getHealth(): Promise<Health> {
  return parse<Health>(await fetch("/api/health"));
}

export async function uploadFiles(files: File[]): Promise<Job> {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return parse<Job>(await fetch("/api/jobs/upload", { method: "POST", body }));
}

export async function jobFromPath(path: string): Promise<Job> {
  return parse<Job>(
    await fetch("/api/jobs/from-path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),
  );
}

export async function getJob(id: string): Promise<Job> {
  return parse<Job>(await fetch(`/api/jobs/${id}`));
}

export async function startCluster(id: string, settings: ClusterSettings): Promise<Job> {
  return parse<Job>(
    await fetch(`/api/jobs/${id}/cluster`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    }),
  );
}

export async function cancelJob(id: string): Promise<Job> {
  return parse<Job>(await fetch(`/api/jobs/${id}/cancel`, { method: "POST" }));
}

export async function renameCluster(jobId: string, clusterId: string, name: string): Promise<Job> {
  return parse<Job>(
    await fetch(`/api/jobs/${jobId}/clusters/${clusterId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function setIncluded(jobId: string, clusterId: string, included: boolean): Promise<Job> {
  return parse<Job>(
    await fetch(`/api/jobs/${jobId}/clusters/${clusterId}/include`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ included }),
    }),
  );
}

export async function mergeClusters(jobId: string, clusterIds: string[]): Promise<Job> {
  return parse<Job>(
    await fetch(`/api/jobs/${jobId}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cluster_ids: clusterIds }),
    }),
  );
}

export async function extractImages(jobId: string, clusterId: string, imageIds: string[]): Promise<Job> {
  return parse<Job>(
    await fetch(`/api/jobs/${jobId}/clusters/${clusterId}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: imageIds }),
    }),
  );
}

export async function excludeImages(jobId: string, imageIds: string[]): Promise<Job> {
  return parse<Job>(
    await fetch(`/api/jobs/${jobId}/exclude`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: imageIds }),
    }),
  );
}

export function thumbUrl(jobId: string, imageId: string): string {
  return `/api/jobs/${jobId}/thumbs/${imageId}`;
}

export function exportUrl(jobId: string): string {
  return `/api/jobs/${jobId}/export.zip`;
}
