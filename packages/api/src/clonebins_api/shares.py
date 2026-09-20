"""Fetch images from a local network share into a cache directory.

Credentials are never logged. Callers should drop ShareSpec secrets after use.
SMB uses ``smbprotocol`` (no root CIFS mount). SFTP uses Paramiko. FTP uses
the stdlib. The clustering pipeline then scans the cache with the normal
from-path / upload flow.
"""

from __future__ import annotations

import io
import stat
from dataclasses import dataclass, field
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path
from typing import Callable, Iterable, Literal

from clonebins_core.scan import IMAGE_EXTENSIONS

__all__ = [
    "ShareError",
    "ShareSpec",
    "default_port",
    "fetch_share",
    "probe_share",
    "redact",
]

ProtocolName = Literal["smb", "sftp", "ftp"]
MAX_SHARE_FILES = 500
MAX_SHARE_FILE_BYTES = 40 * 1024 * 1024

LogFn = Callable[[str], None]


class ShareError(Exception):
    """Safe to show in the UI — messages must not include secrets."""


@dataclass
class ShareSpec:
    protocol: ProtocolName
    host: str
    path: str = ""
    username: str = ""
    password: str | None = field(default=None, repr=False)
    private_key: str | None = field(default=None, repr=False)
    port: int | None = None
    timeout: float = 20.0

    def __post_init__(self) -> None:
        proto = str(self.protocol).lower().strip()
        if proto not in {"smb", "sftp", "ftp"}:
            raise ShareError("Protocol must be smb, sftp, or ftp")
        self.protocol = proto  # type: ignore[assignment]
        self.host = (self.host or "").strip()
        if not self.host:
            raise ShareError("Host is required")
        self.path = (self.path or "").strip()
        self.username = (self.username or "").strip()
        if self.port is not None:
            port = int(self.port)
            if port <= 0 or port > 65535:
                raise ShareError("Port must be 1–65535")
            self.port = port

    @property
    def effective_port(self) -> int:
        return int(self.port or default_port(self.protocol))

    def location(self) -> str:
        path = self.path if self.path.startswith("/") else f"/{self.path}" if self.path else ""
        return f"{self.protocol}://{self.host}:{self.effective_port}{path}"

    def clear_secrets(self) -> None:
        self.password = None
        self.private_key = None


def default_port(protocol: str) -> int:
    return {"smb": 445, "sftp": 22, "ftp": 21}[protocol]


def redact(value: str | None) -> str:
    if not value:
        return ""
    return "***"


def _is_image_name(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def _safe_rel(relative: str) -> Path:
    rel = Path(relative.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise ShareError(f"Refusing unsafe remote path: {relative}")
    return rel


def probe_share(spec: ShareSpec, *, log: LogFn | None = None) -> dict:
    """Connect, count image files, disconnect. Does not keep files on disk."""
    count = 0
    try:
        for _rel, _size in _iter_images(spec, log=log):
            count += 1
            if count > MAX_SHARE_FILES:
                break
    finally:
        spec.clear_secrets()
    _emit(log, f"Found {count} image(s) on {spec.location()}")
    return {"ok": True, "location": spec.location(), "images": min(count, MAX_SHARE_FILES)}


def fetch_share(spec: ShareSpec, dest: Path, *, log: LogFn | None = None) -> int:
    """Download jpg/png/webp from the share into ``dest``. Returns file count."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    saved = 0
    try:
        _emit(log, f"Connecting to {spec.location()}")
        if spec.protocol == "sftp":
            saved = _fetch_sftp(spec, dest, log=log)
        elif spec.protocol == "ftp":
            saved = _fetch_ftp(spec, dest, log=log)
        else:
            saved = _fetch_smb(spec, dest, log=log)
    except ShareError:
        raise
    except Exception as exc:
        raise ShareError(f"Could not read {spec.location()}: {type(exc).__name__}") from exc
    finally:
        spec.clear_secrets()
    if saved == 0:
        raise ShareError(f"No jpg/jpeg/png/webp files found at {spec.location()}")
    _emit(log, f"Cached {saved} image(s) locally")
    return saved


def _iter_images(spec: ShareSpec, *, log: LogFn | None = None) -> Iterable[tuple[str, int]]:
    if spec.protocol == "sftp":
        yield from _list_sftp(spec, log=log)
    elif spec.protocol == "ftp":
        yield from _list_ftp(spec, log=log)
    else:
        yield from _list_smb(spec, log=log)


def _emit(log: LogFn | None, message: str) -> None:
    if log:
        log(message)


def _write_limited(
    dest: Path, chunks: Iterable[bytes], *, limit: int = MAX_SHARE_FILE_BYTES
) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with dest.open("wb") as handle:
        for chunk in chunks:
            written += len(chunk)
            if written > limit:
                handle.close()
                dest.unlink(missing_ok=True)
                raise ShareError(f"Remote file exceeds {limit} bytes; skipped {dest.name}")
            handle.write(chunk)
    return written


# ---------------------------------------------------------------------------
# SFTP (Paramiko)
# ---------------------------------------------------------------------------


def _sftp_connect(spec: ShareSpec):
    try:
        import paramiko
    except ImportError as exc:  # pragma: no cover - dependency declared on the API
        raise ShareError("SFTP support requires paramiko (install clonebins-api extras)") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": spec.host,
        "port": spec.effective_port,
        "username": spec.username or None,
        "timeout": spec.timeout,
        "allow_agent": False,
        "look_for_keys": False,
    }
    key_material = spec.private_key
    if key_material:
        kwargs["pkey"] = _load_pkey(paramiko, key_material, spec.password)
    else:
        kwargs["password"] = spec.password
    try:
        client.connect(**kwargs)
    except Exception as exc:
        raise ShareError(f"SFTP connect failed ({type(exc).__name__})") from exc
    return client


def _load_pkey(paramiko, material: str, password: str | None):
    text = material.strip()
    errors: list[str] = []
    if "BEGIN" not in text:
        path = Path(text).expanduser()
        if path.is_file():
            text = path.read_text(encoding="utf-8")
        else:
            raise ShareError("SFTP private key path was not a file")
    buf = io.StringIO(text)
    for loader in (
        paramiko.Ed25519Key.from_private_key,
        paramiko.ECDSAKey.from_private_key,
        paramiko.RSAKey.from_private_key,
    ):
        buf.seek(0)
        try:
            return loader(buf, password=password)
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise ShareError("Could not parse SFTP private key")


def _list_sftp(spec: ShareSpec, *, log: LogFn | None = None) -> Iterable[tuple[str, int]]:
    client = _sftp_connect(spec)
    try:
        sftp = client.open_sftp()
        root = spec.path or "."
        yield from _walk_sftp(sftp, root, prefix="")
    finally:
        client.close()


def _walk_sftp(sftp, remote: str, prefix: str) -> Iterable[tuple[str, int]]:
    try:
        entries = sftp.listdir_attr(remote)
    except FileNotFoundError as exc:
        raise ShareError("Remote SFTP path not found") from exc
    for entry in entries:
        name = entry.filename
        if name in {".", ".."}:
            continue
        rel = f"{prefix}/{name}".lstrip("/") if prefix else name
        full = f"{remote.rstrip('/')}/{name}" if remote not in {"", "."} else name
        mode = int(entry.st_mode or 0)
        if stat.S_ISDIR(mode):
            yield from _walk_sftp(sftp, full, rel)
        elif _is_image_name(name):
            yield rel, int(entry.st_size or 0)


def _fetch_sftp(spec: ShareSpec, dest: Path, *, log: LogFn | None = None) -> int:
    client = _sftp_connect(spec)
    saved = 0
    try:
        sftp = client.open_sftp()
        root = spec.path or "."
        for rel, size in _walk_sftp(sftp, root, prefix=""):
            if saved >= MAX_SHARE_FILES:
                _emit(log, f"Stopped at {MAX_SHARE_FILES} files")
                break
            if size > MAX_SHARE_FILE_BYTES:
                _emit(log, f"Skip {rel} (too large)")
                continue
            remote = f"{root.rstrip('/')}/{rel}" if root not in {"", "."} else rel
            target = dest / _safe_rel(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(remote, str(target))
            saved += 1
            _emit(log, f"Cached {rel}")
    finally:
        client.close()
    return saved


# ---------------------------------------------------------------------------
# FTP
# ---------------------------------------------------------------------------


def _ftp_connect(spec: ShareSpec) -> FTP:
    ftp: FTP
    try:
        ftp = FTP_TLS()
        ftp.connect(spec.host, spec.effective_port, timeout=spec.timeout)
        ftp.login(spec.username or "anonymous", spec.password or "")
        try:
            ftp.prot_p()
        except Exception:
            pass
    except Exception:
        ftp = FTP()
        try:
            ftp.connect(spec.host, spec.effective_port, timeout=spec.timeout)
            ftp.login(spec.username or "anonymous", spec.password or "")
        except Exception as exc:
            raise ShareError(f"FTP connect failed ({type(exc).__name__})") from exc
    ftp.set_pasv(True)
    if spec.path:
        try:
            ftp.cwd(spec.path)
        except error_perm as exc:
            raise ShareError("Remote FTP path not found") from exc
    return ftp


def _ftp_entries(ftp: FTP) -> list[tuple[str, bool]]:
    """Return (name, is_dir) pairs for the current directory."""
    rows: list[tuple[str, bool]] = []
    try:
        for name, facts in ftp.mlsd():
            if name in {".", ".."}:
                continue
            kind = str(facts.get("type", "file")).lower()
            rows.append((name, kind == "dir"))
        return rows
    except Exception:
        pass
    try:
        names = ftp.nlst()
    except Exception:
        return []
    out: list[tuple[str, bool]] = []
    here = ftp.pwd()
    for raw in names:
        name = raw.rstrip("/").split("/")[-1]
        if name in {".", ".."}:
            continue
        is_dir = False
        try:
            ftp.cwd(name)
            ftp.cwd(here)
            is_dir = True
        except Exception:
            is_dir = False
        out.append((name, is_dir))
    return out


def _walk_ftp(ftp: FTP, prefix: str) -> Iterable[tuple[str, str]]:
    here = ftp.pwd()
    for name, is_dir in _ftp_entries(ftp):
        rel = f"{prefix}/{name}".lstrip("/") if prefix else name
        if is_dir:
            try:
                ftp.cwd(name)
            except Exception:
                continue
            try:
                yield from _walk_ftp(ftp, rel)
            finally:
                ftp.cwd(here)
        elif _is_image_name(name):
            yield rel, name


def _list_ftp(spec: ShareSpec, *, log: LogFn | None = None) -> Iterable[tuple[str, int]]:
    ftp = _ftp_connect(spec)
    try:
        for rel, _name in _walk_ftp(ftp, ""):
            yield rel, 0
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


def _fetch_ftp(spec: ShareSpec, dest: Path, *, log: LogFn | None = None) -> int:
    ftp = _ftp_connect(spec)
    saved = 0
    try:
        root = ftp.pwd()
        listing = list(_walk_ftp(ftp, ""))
        ftp.cwd(root)
        for rel, name in listing:
            if saved >= MAX_SHARE_FILES:
                _emit(log, f"Stopped at {MAX_SHARE_FILES} files")
                break
            target = dest / _safe_rel(rel)
            chunks: list[bytes] = []

            def _collect(chunk: bytes, bucket: list[bytes] = chunks) -> None:
                bucket.append(chunk)

            try:
                ftp.retrbinary(f"RETR {rel}", _collect)
            except Exception:
                ftp.cwd(root)
                ftp.retrbinary(f"RETR {name}", _collect)
            _write_limited(target, chunks)
            saved += 1
            _emit(log, f"Cached {rel}")
            ftp.cwd(root)
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return saved


# ---------------------------------------------------------------------------
# SMB
# ---------------------------------------------------------------------------


def _smb_unc(spec: ShareSpec) -> str:
    raw = spec.path.replace("/", "\\").lstrip("\\")
    if not raw:
        raise ShareError("SMB path must start with the share name, e.g. Photos/gens")
    return f"\\\\{spec.host}\\{raw}"


def _smb_register(spec: ShareSpec):
    try:
        import smbclient
    except ImportError as exc:  # pragma: no cover
        raise ShareError("SMB support requires smbprotocol (install clonebins-api extras)") from exc
    try:
        smbclient.register_session(
            spec.host,
            username=spec.username or None,
            password=spec.password,
            port=spec.effective_port,
            connection_timeout=spec.timeout,
        )
    except Exception as exc:
        raise ShareError(f"SMB connect failed ({type(exc).__name__})") from exc
    return smbclient


def _smb_join(unc: str, *parts: str) -> str:
    out = unc.rstrip("\\")
    for part in parts:
        chunk = str(part).replace("/", "\\").strip("\\")
        if chunk:
            out = out + "\\" + chunk
    return out


def _list_smb(spec: ShareSpec, *, log: LogFn | None = None) -> Iterable[tuple[str, int]]:
    smbclient = _smb_register(spec)
    root = _smb_unc(spec)
    yield from _walk_smb(smbclient, root, prefix="")


def _walk_smb(smbclient, unc: str, prefix: str) -> Iterable[tuple[str, int]]:
    try:
        entries = list(smbclient.scandir(unc))
    except Exception as exc:
        raise ShareError("SMB path not found or not listable") from exc
    for entry in entries:
        name = entry.name
        if name in {".", ".."}:
            continue
        rel = f"{prefix}/{name}".lstrip("/") if prefix else name
        child = _smb_join(unc, name)
        try:
            is_dir = entry.is_dir()
        except Exception:
            is_dir = False
        if is_dir:
            yield from _walk_smb(smbclient, child, rel)
        elif _is_image_name(name):
            try:
                size = int(entry.stat().st_size)
            except Exception:
                size = 0
            yield rel, size


def _fetch_smb(spec: ShareSpec, dest: Path, *, log: LogFn | None = None) -> int:
    smbclient = _smb_register(spec)
    root = _smb_unc(spec)
    saved = 0
    for rel, size in _walk_smb(smbclient, root, prefix=""):
        if saved >= MAX_SHARE_FILES:
            _emit(log, f"Stopped at {MAX_SHARE_FILES} files")
            break
        if size > MAX_SHARE_FILE_BYTES:
            _emit(log, f"Skip {rel} (too large)")
            continue
        remote = _smb_join(root, rel)
        target = dest / _safe_rel(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        with smbclient.open_file(remote, mode="rb") as handle:
            _write_limited(target, iter(lambda: handle.read(256 * 1024), b""))
        saved += 1
        _emit(log, f"Cached {rel}")
    try:
        smbclient.reset_connection_cache()
    except Exception:
        pass
    return saved
