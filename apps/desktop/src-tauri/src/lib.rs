//! Tauri shell: spawn the local clonebins-api sidecar and load apps/web.

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::Manager;

const API_HOST: &str = "127.0.0.1";
const API_PORT: u16 = 8765;

pub struct ApiSidecar(pub Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(ApiSidecar(Mutex::new(None)))
        .setup(|app| {
            if api_port_open() {
                eprintln!("CloneBins API already listening on {API_HOST}:{API_PORT}");
                return Ok(());
            }
            match spawn_sidecar() {
                Ok(child) => {
                    *app.state::<ApiSidecar>().0.lock().expect("sidecar lock") = Some(child);
                    if wait_for_api(Duration::from_secs(25)) {
                        eprintln!("Started clonebins-api sidecar on {API_HOST}:{API_PORT}");
                    } else {
                        eprintln!(
                            "clonebins-api did not become ready on {API_HOST}:{API_PORT}. \
                             Install: pip install -e packages/core -e packages/api"
                        );
                    }
                }
                Err(err) => eprintln!("{err}"),
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building CloneBins desktop")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(mut child) = app_handle
                    .state::<ApiSidecar>()
                    .0
                    .lock()
                    .ok()
                    .and_then(|mut guard| guard.take())
                {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        });
}

fn api_port_open() -> bool {
    TcpStream::connect_timeout(
        &format!("{API_HOST}:{API_PORT}")
            .parse()
            .expect("API addr"),
        Duration::from_millis(200),
    )
    .is_ok()
}

fn wait_for_api(timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if api_port_open() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(150));
    }
    false
}

fn spawn_sidecar() -> Result<Child, String> {
    let mut cmd = if let Some(bin) = bundled_api_bin() {
        eprintln!("Using bundled clonebins-api at {}", bin.display());
        Command::new(bin)
    } else if let Some(bin) = resolve_in_path("clonebins-api") {
        Command::new(bin)
    } else {
        let py = python_bin()?;
        let mut c = Command::new(py);
        c.args(["-m", "clonebins_api"]);
        c
    };
    cmd.env("CLONEBINS_API_HOST", API_HOST)
        .env("CLONEBINS_API_PORT", API_PORT.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn().map_err(|err| {
        format!(
            "Failed to start clonebins-api sidecar ({err}). \
             pip install -e packages/core -e packages/api \
             (or set CLONEBINS_PYTHON to a Python that has those packages)."
        )
    })
}

/// Sidecar next to the executable (`CloneBins.app/Contents/MacOS/clonebins-api`,
/// `/usr/bin/clonebins-api` on Linux, or `clonebins-api.exe` beside `CloneBins.exe`).
fn bundled_api_bin() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    for name in ["clonebins-api", "clonebins-api.exe"] {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn python_bin() -> Result<PathBuf, String> {
    if let Ok(explicit) = std::env::var("CLONEBINS_PYTHON") {
        return Ok(PathBuf::from(explicit));
    }
    for name in ["python3", "python"] {
        if let Some(path) = resolve_in_path(name) {
            return Ok(path);
        }
    }
    Err("No python3 on PATH. Set CLONEBINS_PYTHON to your interpreter.".into())
}

fn resolve_in_path(name: &str) -> Option<PathBuf> {
    let path_var = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path_var) {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
        #[cfg(windows)]
        {
            let exe = dir.join(format!("{name}.exe"));
            if exe.is_file() {
                return Some(exe);
            }
        }
    }
    None
}
