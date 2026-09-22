import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import { isTauriRuntime, pickDirectory } from "./desktop";
import type {
  ClusterSettings,
  Health,
  Job,
  JobCluster,
  JobImage,
  ModelDownloadTask,
  ShareProtocol,
  ShareRequest,
} from "./types";

const DEFAULT_SETTINGS: ClusterSettings = {
  threshold: 0.45,
  min_images: 2,
  mode: "face+body",
  subject_prefix: "subject",
  download_models: false,
  keep_names: true,
  yunet: "2023mar",
  sface: "2021dec",
};

const EMPTY_SHARE: ShareRequest = {
  protocol: "sftp",
  host: "",
  port: "",
  path: "",
  username: "",
  password: "",
  private_key: "",
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
  const [share, setShare] = useState<ShareRequest>(EMPTY_SHARE);
  const [modelLog, setModelLog] = useState<string[]>([
    "Face models ship inside the desktop app. Verify copies them into the cache and downloads only missing files.",
    "CLI fallback: clonebins models download --force",
  ]);
  const [modelTask, setModelTask] = useState<ModelDownloadTask | null>(null);
  const [modelsDir, setModelsDir] = useState("~/.cache/clonebins/models");
  const logBox = useRef<HTMLPreElement | null>(null);

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

  useEffect(() => {
    if (!modelTask || modelTask.status !== "running") return;
    const timer = window.setInterval(() => {
      api
        .getModelDownload(modelTask.id)
        .then((next) => {
          setModelTask(next);
          setModelLog(next.logs.length ? next.logs : ["Downloading…"]);
          if (next.models_dir) setModelsDir(next.models_dir);
          if (next.status === "done" || next.status === "error") {
            void api.getHealth().then(setHealth).catch(() => undefined);
          }
        })
        .catch((err: Error) => setError(err.message));
    }, 320);
    return () => window.clearInterval(timer);
  }, [modelTask]);

  useEffect(() => {
    if (logBox.current) logBox.current.scrollTop = logBox.current.scrollHeight;
  }, [modelLog]);

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

  async function onProbeShare() {
    if (!share.host.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.probeShare(share);
      setModelLog((prev) => [
        ...prev,
        `Share probe ${result.location}: ${result.images} image(s). Credentials were not stored.`,
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onUseShare() {
    if (!share.host.trim()) return;
    const created = await run(api.jobFromShare(share));
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

  async function onVerifyModels() {
    setError(null);
    setModelLog([
      "Verify: checking cache, copying baked models, downloading only missing files…",
    ]);
    try {
      const task = await api.startModelVerify(settings);
      setModelTask(task);
      setModelLog(task.logs.length ? task.logs : ["Verifying…"]);
      if (task.models_dir) setModelsDir(task.models_dir);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setModelLog((prev) => [
        ...prev,
        `Verify failed: ${message}`,
        "CLI fallback: clonebins models verify",
      ]);
    }
  }

  async function onDownloadModels() {
    setError(null);
    setModelLog([
      "Download: copying baked models, then fetching only files still missing. Verify is not required.",
    ]);
    try {
      const task = await api.startModelDownload(settings, { force: false });
      setModelTask(task);
      setModelLog(task.logs.length ? task.logs : ["Downloading…"]);
      if (task.models_dir) setModelsDir(task.models_dir);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setModelLog((prev) => [
        ...prev,
        `Download failed: ${message}`,
        "CLI fallback: clonebins models download --force",
      ]);
    }
  }

  async function onOpenModelsFolder() {
    setError(null);
    try {
      const result = await api.openModelsFolder();
      setModelsDir(result.models_dir);
      setModelLog((prev) => [
        ...prev,
        `Models folder: ${result.models_dir}`,
        result.ok ? "Opened in Finder / file manager." : "Could not open the folder automatically.",
      ]);
    } catch (err) {
      setModelLog((prev) => [
        ...prev,
        `Open folder failed: ${err instanceof Error ? err.message : String(err)}`,
        `Path: ${modelsDir}`,
      ]);
    }
  }

  async function onCopyInstallCommand() {
    const command = "clonebins models download --force";
    try {
      await navigator.clipboard.writeText(command);
      setModelLog((prev) => [...prev, `Copied: ${command}`]);
    } catch {
      setModelLog((prev) => [...prev, `Install command: ${command}`]);
    }
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
  const downloadingModels = modelTask?.status === "running";
  const anyIncluded = Boolean(job?.clusters.some((c) => c.included));
  const progress = job?.progress;
  const pct =
    clustering && progress && progress.total > 0
      ? Math.min(100, Math.round((progress.completed / progress.total) * 100))
      : clustering
        ? 15
        : 0;
  const downloadEnabled = !downloadingModels;

  return (
    <div className="page">
      <div className="aurora" aria-hidden="true" />
      <header className="top">
        <div>
          <p className="eyebrow">Local LoRA dataset prep</p>
          <h1>CloneBins</h1>
          <p className="tagline">Cluster faces &amp; looks into identity bins — offline, on this machine.</p>
        </div>
        <p className="privacy">
          Processing is <strong>local</strong>. No cloud account, no vendor upload, no training. Share passwords never
          leave this API host and are not logged.
        </p>
      </header>

      {health && (
        <p className="health">
          API v{health.version}
          {health.models_ready
            ? " · face models ready"
            : " · appearance fallback until YuNet/SFace are downloaded"}
        </p>
      )}

      <section className="layout">
        <aside className="panel stack">
          <h2>
            <span className="step">01</span> Images
          </h2>
          <label className="drop">
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              multiple
              disabled={busy || clustering}
              onChange={(e) => void onFiles(e.target.files)}
            />
            <span>
              Drop jpg / png / webp
              <em>or click to upload</em>
            </span>
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
              <button type="button" className="ghost" disabled={busy || clustering} onClick={() => void onBrowseFolder()}>
                Browse
              </button>
            )}
            <button type="button" disabled={busy || clustering || !localPath.trim()} onClick={() => void onPath()}>
              Use path
            </button>
          </div>

          <h3>Network share</h3>
          <p className="hint">
            SMB, SFTP, or FTP. Files are copied into a local cache, then clustered with the same pipeline. Credentials
            stay on this host.
          </p>
          <label className="field">
            Protocol
            <select
              value={share.protocol}
              onChange={(e) => setShare({ ...share, protocol: e.target.value as ShareProtocol })}
              disabled={busy || clustering}
            >
              <option value="sftp">SFTP</option>
              <option value="smb">SMB</option>
              <option value="ftp">FTP</option>
            </select>
          </label>
          <div className="pair">
            <label className="field">
              Host
              <input
                value={share.host}
                onChange={(e) => setShare({ ...share, host: e.target.value })}
                placeholder="nas.local"
                disabled={busy || clustering}
                autoComplete="off"
              />
            </label>
            <label className="field">
              Port
              <input
                value={share.port}
                onChange={(e) => setShare({ ...share, port: e.target.value })}
                placeholder={share.protocol === "smb" ? "445" : share.protocol === "ftp" ? "21" : "22"}
                disabled={busy || clustering}
                autoComplete="off"
              />
            </label>
          </div>
          <label className="field">
            Path {share.protocol === "smb" ? "(Share/folder)" : "(remote directory)"}
            <input
              value={share.path}
              onChange={(e) => setShare({ ...share, path: e.target.value })}
              placeholder={share.protocol === "smb" ? "Photos/gens" : "/data/gens"}
              disabled={busy || clustering}
              autoComplete="off"
            />
          </label>
          <label className="field">
            Username
            <input
              value={share.username}
              onChange={(e) => setShare({ ...share, username: e.target.value })}
              disabled={busy || clustering}
              autoComplete="username"
            />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              value={share.password}
              onChange={(e) => setShare({ ...share, password: e.target.value })}
              disabled={busy || clustering}
              autoComplete="current-password"
            />
          </label>
          {share.protocol === "sftp" && (
            <label className="field">
              Private key (PEM or path)
              <textarea
                rows={3}
                value={share.private_key}
                onChange={(e) => setShare({ ...share, private_key: e.target.value })}
                disabled={busy || clustering}
                placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                autoComplete="off"
              />
            </label>
          )}
          <div className="btn-row">
            <button type="button" className="ghost" disabled={busy || clustering || !share.host.trim()} onClick={() => void onProbeShare()}>
              Probe share
            </button>
            <button type="button" disabled={busy || clustering || !share.host.trim()} onClick={() => void onUseShare()}>
              Cache &amp; cluster
            </button>
          </div>

          <h2>
            <span className="step">02</span> Face models
          </h2>
          <p className="hint">
            Download is always enabled. Packaged apps ship all 7 ONNX files. Verify checks{" "}
            <code>{modelsDir}</code>, copies models baked into the app, then downloads only what is
            still missing. Terminal fallback: <code>clonebins models download --force</code>.
          </p>
          <div className="btn-row">
            <button type="button" className="ghost" disabled={downloadingModels} onClick={() => void onVerifyModels()}>
              Verify
            </button>
            <button type="button" disabled={!downloadEnabled} onClick={() => void onDownloadModels()}>
              Download
            </button>
            <button type="button" className="ghost" disabled={downloadingModels} onClick={() => void onOpenModelsFolder()}>
              Open models folder
            </button>
            <button type="button" className="ghost" disabled={downloadingModels} onClick={() => void onCopyInstallCommand()}>
              Copy install command
            </button>
          </div>
          <pre className="logbox" ref={logBox} role="log" aria-live="polite">
            {modelLog.join("\n")}
          </pre>

          <h2>
            <span className="step">03</span> Settings
          </h2>
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
            Face detector (YuNet)
            <select
              value={settings.yunet}
              onChange={(e) =>
                setSettings({ ...settings, yunet: e.target.value as ClusterSettings["yunet"] })
              }
            >
              {(health?.models?.yunet ?? [
                { id: "2023mar", label: "YuNet 2023 FP32", notes: "" },
                { id: "2023mar_int8", label: "YuNet 2023 INT8", notes: "" },
                { id: "2023mar_int8bq", label: "YuNet 2023 INT8-BQ", notes: "" },
                { id: "2026may", label: "YuNet 2026 dynamic", notes: "" },
              ]).map((spec) => (
                <option key={spec.id} value={spec.id}>
                  {spec.label}
                  {"ready" in spec && spec.ready === false ? " (not downloaded)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Face recognizer (SFace)
            <select
              value={settings.sface}
              onChange={(e) =>
                setSettings({ ...settings, sface: e.target.value as ClusterSettings["sface"] })
              }
            >
              {(health?.models?.sface ?? [
                { id: "2021dec", label: "SFace 2021 FP32", notes: "" },
                { id: "2021dec_int8", label: "SFace 2021 INT8", notes: "" },
                { id: "2021dec_int8bq", label: "SFace 2021 INT8-BQ", notes: "" },
              ]).map((spec) => (
                <option key={spec.id} value={spec.id}>
                  {spec.label}
                  {"ready" in spec && spec.ready === false ? " (not downloaded)" : ""}
                </option>
              ))}
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
          <button type="button" className="secondary" disabled={!job || busy || clustering} onClick={() => void onRecluster()}>
            Re-cluster with these settings
          </button>
        </aside>

        <main className="panel results">
          <div className="results-head">
            <h2>
              <span className="step">04</span> Bins
            </h2>
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
              <button
                type="button"
                className="ghost"
                disabled={!job || clustering || job.clusters.length === 0}
                onClick={() => job && void run(api.setIncludedAll(job.id, true))}
              >
                Include all in zip
              </button>
              <button
                type="button"
                className="ghost"
                disabled={!job || clustering || job.clusters.length === 0}
                onClick={() => job && void run(api.setIncludedAll(job.id, false))}
              >
                Include none
              </button>
              {job && clustering && (
                <button type="button" className="danger" onClick={() => void run(api.cancelJob(job.id))}>
                  Cancel
                </button>
              )}
              {job && job.status === "done" && (
                <button
                  type="button"
                  className="download"
                  disabled={busy || !anyIncluded}
                  onClick={() => void onDownloadZip()}
                >
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
              Job {job.id} · {job.status} · {job.source} · scanned {job.scanned}
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
      {cluster.below_min && (
        <p className="warn">Below min-images. Off by default — check “in zip” or Include all if you want it.</p>
      )}
      {!cluster.included && !cluster.below_min && (
        <p className="meta">Not in the zip until you check “in zip” or Include all.</p>
      )}
      <ul className="thumbs">
        {cluster.image_ids.map((id) => {
          const img = imagesById.get(id);
          const fullUrl = api.imageUrl(jobId, id);
          return (
            <li key={id} className={selectedImages.has(id) ? "picked" : ""}>
              <a
                className="thumb-link"
                href={fullUrl}
                target="_blank"
                rel="noopener noreferrer"
                title="Open original in a new window. Click to select for split/exclude."
                onClick={(e) => {
                  if (!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {
                    e.preventDefault();
                    onToggleImage(id);
                  }
                }}
              >
                <img src={api.thumbUrl(jobId, id)} alt={img?.filename ?? id} />
                <span>{img?.filename ?? id}</span>
              </a>
              <a className="open-full" href={fullUrl} target="_blank" rel="noopener noreferrer">
                open ↗
              </a>
            </li>
          );
        })}
      </ul>
    </article>
  );
}
