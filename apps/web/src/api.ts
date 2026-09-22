import type { ClusterSettings, Health, Job, ShareRequest } from "./types";

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function apiBase(): string {
  const fromEnv = import.meta.env.VITE_CLONEBINS_API as string | undefined;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  // Packaged Tauri loads UI from a custom protocol; talk to the sidecar directly.
  if (isTauriRuntime() && !import.meta.env.DEV) return "http://127.0.0.1:8765";
  return "";
}

function apiUrl(path: string): string {
  return `${apiBase()}${path}`;
}

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
  return parse<Health>(await fetch(apiUrl("/api/health")));
}

export async function uploadFiles(files: File[]): Promise<Job> {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return parse<Job>(await fetch(apiUrl("/api/jobs/upload"), { method: "POST", body }));
}

export async function jobFromPath(path: string): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl("/api/jobs/from-path"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),
  );
}

export async function getJob(id: string): Promise<Job> {
  return parse<Job>(await fetch(apiUrl(`/api/jobs/${id}`)));
}

export async function startCluster(id: string, settings: ClusterSettings): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${id}/cluster`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    }),
  );
}

export async function cancelJob(id: string): Promise<Job> {
  return parse<Job>(await fetch(apiUrl(`/api/jobs/${id}/cancel`), { method: "POST" }));
}

export async function renameCluster(jobId: string, clusterId: string, name: string): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${jobId}/clusters/${clusterId}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function setIncluded(jobId: string, clusterId: string, included: boolean): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${jobId}/clusters/${clusterId}/include`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ included }),
    }),
  );
}

export async function setIncludedAll(jobId: string, included: boolean): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${jobId}/include-all`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ included }),
    }),
  );
}

export async function mergeClusters(jobId: string, clusterIds: string[]): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${jobId}/merge`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cluster_ids: clusterIds }),
    }),
  );
}

export async function extractImages(jobId: string, clusterId: string, imageIds: string[]): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${jobId}/clusters/${clusterId}/extract`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: imageIds }),
    }),
  );
}

export async function excludeImages(jobId: string, imageIds: string[]): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl(`/api/jobs/${jobId}/exclude`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: imageIds }),
    }),
  );
}

export function thumbUrl(jobId: string, imageId: string): string {
  return apiUrl(`/api/jobs/${jobId}/thumbs/${imageId}`);
}

export function imageUrl(jobId: string, imageId: string): string {
  return apiUrl(`/api/jobs/${jobId}/images/${imageId}`);
}

export function exportUrl(jobId: string): string {
  return apiUrl(`/api/jobs/${jobId}/export.zip`);
}

export async function downloadExportZip(jobId: string): Promise<void> {
  const { isTauriRuntime, saveZipBytes } = await import("./desktop");
  if (isTauriRuntime()) {
    const res = await fetch(exportUrl(jobId));
    if (!res.ok) throw new Error("Zip export failed");
    const bytes = new Uint8Array(await res.arrayBuffer());
    await saveZipBytes(bytes);
    return;
  }
  window.location.assign(exportUrl(jobId));
}

function sharePayload(share: ShareRequest): Record<string, unknown> {
  const port = share.port.trim() ? Number(share.port) : undefined;
  return {
    protocol: share.protocol,
    host: share.host.trim(),
    path: share.path.trim(),
    username: share.username.trim(),
    password: share.password || null,
    private_key: share.private_key.trim() || null,
    port: Number.isFinite(port) ? port : null,
  };
}

export async function probeShare(share: ShareRequest): Promise<{ ok: boolean; location: string; images: number }> {
  return parse(
    await fetch(apiUrl("/api/shares/probe"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sharePayload(share)),
    }),
  );
}

export async function jobFromShare(share: ShareRequest): Promise<Job> {
  return parse<Job>(
    await fetch(apiUrl("/api/jobs/from-share"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sharePayload(share)),
    }),
  );
}
