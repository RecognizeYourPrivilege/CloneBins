import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "./api";
import { isTauriRuntime, pickDirectory } from "./desktop";
import type { ClusterSettings, Health, Job, JobCluster, JobImage } from "./types";

const DEFAULT_SETTINGS: ClusterSettings = {
  threshold: 0.45,
  min_images: 2,
  mode: "face+body",
  subject_prefix: "subject",
  download_models: true,
  keep_names: true,
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [settings, setSettings] = useState<ClusterSettings>(DEFAULT_SETTINGS);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localPath, setLocalPath] = useState("");
  const [desktop, setDesktop] = useState(false);
  const [selectedClusters, setSelectedClusters] = useState<Set<string>>(new Set());
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());

  useEffect(() => {
    setDesktop(isTauriRuntime());
  }, []);

  useEffect(() => {
    api.getHealth().then(setHealth).catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!job || job.status !== "clustering") return;
    const timer = window.setInterval(() => {
      api.getJob(job.id).then(setJob).catch((err: Error) => setError(err.message));
    }, 280);
    return () => window.clearInterval(timer);
  }, [job]);

  const imagesById = useMemo(() => {
    const map = new Map<string, JobImage>();
    for (const img of job?.images ?? []) map.set(img.id, img);
    return map;
  }, [job]);

  const skipped = job?.images.filter((i) => i.skipped) ?? [];
  const unmatched = job?.images.filter((i) => i.unmatched) ?? [];

  const run = useCallback(async (next: Promise<Job>) => {
    setBusy(true);
    setError(null);
    try {
      const result = await next;
      setJob(result);
      setSelectedClusters(new Set());
      setSelectedImages(new Set());
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  async function onFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    const created = await run(api.uploadFiles(Array.from(list)));
    if (created) await run(api.startCluster(created.id, settings));
  }

  async function onPath() {
    if (!localPath.trim()) return;
    const created = await run(api.jobFromPath(localPath.trim()));
    if (created) await run(api.startCluster(created.id, settings));
  }

  async function onBrowseFolder() {
    const path = await pickDirectory();
    if (!path) return;
    setLocalPath(path);
    const created = await run(api.jobFromPath(path));
    if (created) await run(api.startCluster(created.id, settings));
  }

  async function onDownloadZip() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      await api.downloadExportZip(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRecluster() {
    if (!job) return;
    await run(api.startCluster(job.id, settings));
  }

  function toggleCluster(id: string) {
    setSelectedClusters((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleImage(id: string) {
    setSelectedImages((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const clustering = job?.status === "clustering";
  const progress = job?.progress;
  const pct =
    clustering && progress && progress.total > 0
      ? Math.min(100, Math.round((progress.completed / progress.total) * 100))
      : clustering
        ? 15
        : 0;

  return (
    <div className="page">
      <header className="top">
        <div>
          <p className="eyebrow">LoRA dataset prep</p>
          <h1>CloneBins</h1>
        </div>
        <p className="privacy">
          Processing is <strong>local</strong> — this machine / self-hosted API. No cloud account,
          no upload to a vendor.
        </p>
      </header>

      {health && (
        <p className="health">
          API v{health.version}
          {health.models_ready ? " · face models ready" : " · appearance fallback (download YuNet/SFace for faces)"}
        </p>
      )}

      <section className="layout">
        <aside className="panel">
          <h2>1. Images</h2>
          <label className="drop">
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              multiple
              disabled={busy || clustering}
              onChange={(e) => void onFiles(e.target.files)}
            />
            <span>Drop jpg / png / webp or click to upload</span>
          </label>
          <div className="path-row">
            <input
              type="text"
              placeholder={desktop ? "Folder on this machine" : "Or a folder path on this machine"}
              value={localPath}
              onChange={(e) => setLocalPath(e.target.value)}
              disabled={busy || clustering}
            />
            {desktop && (
              <button type="button" className="secondary-inline" disabled={busy || clustering} onClick={() => void onBrowseFolder()}>
                Browse
              </button>
            )}
            <button type="button" disabled={busy || clustering || !localPath.trim()} onClick={() => void onPath()}>
              Use path
            </button>
          </div>

          <h2>2. Settings</h2>
          <label className="field">
            Mode
            <select
              value={settings.mode}
              onChange={(e) =>
                setSettings({ ...settings, mode: e.target.value as ClusterSettings["mode"] })
              }
            >
              <option value="face">face</option>
              <option value="face+body">face+body</option>
            </select>
          </label>
          <label className="field">
            Similarity threshold ({settings.threshold.toFixed(2)})
            <input
              type="range"
              min={0.15}
              max={0.9}
              step={0.01}
              value={settings.threshold}
              onChange={(e) => setSettings({ ...settings, threshold: Number(e.target.value) })}
            />
          </label>
          <label className="field">
            Min images per bin
            <input
              type="number"
              min={1}
              value={settings.min_images}
              onChange={(e) => setSettings({ ...settings, min_images: Number(e.target.value) })}
            />
          </label>
          <label className="field">
            Subject prefix
            <input
              type="text"
              value={settings.subject_prefix}
              onChange={(e) => setSettings({ ...settings, subject_prefix: e.target.value })}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={settings.keep_names}
              onChange={(e) => setSettings({ ...settings, keep_names: e.target.checked })}
            />
            Keep original filenames in the zip
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={settings.download_models}
              onChange={(e) => setSettings({ ...settings, download_models: e.target.checked })}
            />
            Download face models if missing
          </label>
          <button type="button" className="secondary" disabled={!job || busy || clustering} onClick={() => void onRecluster()}>
            Re-cluster with these settings
          </button>
        </aside>

        <main className="panel results">
          <div className="results-head">
            <h2>3. Bins</h2>
            <div className="actions">
              <button
                type="button"
                disabled={selectedClusters.size < 2 || clustering}
                onClick={() => job && void run(api.mergeClusters(job.id, [...selectedClusters]))}
              >
                Merge selected bins
              </button>
              <button
                type="button"
                disabled={selectedImages.size === 0 || clustering}
                onClick={() => {
                  if (!job) return;
                  const cluster = job.clusters.find((c) =>
                    c.image_ids.some((id) => selectedImages.has(id)),
                  );
                  if (!cluster) return;
                  const ids = cluster.image_ids.filter((id) => selectedImages.has(id));
                  void run(api.extractImages(job.id, cluster.id, ids));
                }}
              >
                Split selected images
              </button>
              <button
                type="button"
                className="danger"
                disabled={selectedImages.size === 0 || clustering}
                onClick={() => job && void run(api.excludeImages(job.id, [...selectedImages]))}
              >
                Exclude selected
              </button>
              {job && clustering && (
                <button type="button" className="danger" onClick={() => void run(api.cancelJob(job.id))}>
                  Cancel
                </button>
              )}
              {job && job.status === "done" && (
                <button type="button" className="download" disabled={busy} onClick={() => void onDownloadZip()}>
                  {desktop ? "Save zip…" : "Download zip"}
                </button>
              )}
            </div>
          </div>

          {clustering && progress && (
            <div className="progress" role="status">
              <div className="bar" style={{ width: `${pct}%` }} />
              <p>
                {progress.phase || "working"} · {progress.completed}
                {progress.total ? `/${progress.total}` : ""} {progress.detail}
              </p>
            </div>
          )}

          {error && <p className="error">{error}</p>}
          {job?.error && <p className="error">{job.error}</p>}
          {job?.notes.map((note) => (
            <p key={note} className="note">
              {note}
            </p>
          ))}

          {job && (
            <p className="meta">
              Job {job.id} · {job.status} · scanned {job.scanned}
              {job.backend_name ? ` · ${job.backend_name}` : ""}
              {skipped.length ? ` · skipped ${skipped.length}` : ""}
              {unmatched.length ? ` · unmatched ${unmatched.length}` : ""}
            </p>
          )}

          <div className="bins">
            {(job?.clusters ?? []).map((cluster) => (
              <ClusterCard
                key={cluster.id}
                jobId={job!.id}
                cluster={cluster}
                imagesById={imagesById}
                selected={selectedClusters.has(cluster.id)}
                selectedImages={selectedImages}
                disabled={clustering}
                onToggle={() => toggleCluster(cluster.id)}
                onToggleImage={toggleImage}
                onRename={(name) => void run(api.renameCluster(job!.id, cluster.id, name))}
                onInclude={(included) => void run(api.setIncluded(job!.id, cluster.id, included))}
              />
            ))}
          </div>

          {skipped.length > 0 && (
            <p className="meta">
              Skipped corrupt/unreadable: {skipped.map((s) => `${s.filename} (${s.skip_reason})`).join("; ")}
            </p>
          )}
        </main>
      </section>
    </div>
  );
}

function ClusterCard({
  jobId,
  cluster,
  imagesById,
  selected,
  selectedImages,
  disabled,
  onToggle,
  onToggleImage,
  onRename,
  onInclude,
}: {
  jobId: string;
  cluster: JobCluster;
  imagesById: Map<string, JobImage>;
  selected: boolean;
  selectedImages: Set<string>;
  disabled: boolean;
  onToggle: () => void;
  onToggleImage: (id: string) => void;
  onRename: (name: string) => void;
  onInclude: (included: boolean) => void;
}) {
  const [draft, setDraft] = useState(cluster.name);
  useEffect(() => setDraft(cluster.name), [cluster.name]);

  return (
    <article className={`bin ${cluster.included ? "" : "dim"} ${selected ? "picked" : ""}`}>
      <header>
        <label className="check">
          <input type="checkbox" checked={selected} disabled={disabled} onChange={onToggle} />
          select
        </label>
        <input
          className="name"
          value={draft}
          disabled={disabled}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => {
            if (draft.trim() && draft !== cluster.name) onRename(draft);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.currentTarget.blur();
            }
          }}
        />
        <span className="count">{cluster.image_ids.length}</span>
        <label className="check">
          <input
            type="checkbox"
            checked={cluster.included}
            disabled={disabled}
            onChange={(e) => onInclude(e.target.checked)}
          />
          in zip
        </label>
      </header>
      {cluster.below_min && <p className="warn">Below min-images — off by default, toggle “in zip” or merge.</p>}
      <ul className="thumbs">
        {cluster.image_ids.map((id) => {
          const img = imagesById.get(id);
          return (
            <li key={id} className={selectedImages.has(id) ? "picked" : ""}>
              <button type="button" disabled={disabled} onClick={() => onToggleImage(id)}>
                <img src={api.thumbUrl(jobId, id)} alt={img?.filename ?? id} />
                <span>{img?.filename ?? id}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </article>
  );
}
