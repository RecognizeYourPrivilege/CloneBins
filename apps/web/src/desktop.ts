/** Desktop (Tauri) helpers. Safe to import from the browser; native APIs are dynamic. */

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function pickDirectory(): Promise<string | null> {
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    directory: true,
    multiple: false,
    title: "Choose a folder of images",
  });
  if (Array.isArray(selected)) return selected[0] ?? null;
  return selected;
}

export async function saveZipBytes(bytes: Uint8Array): Promise<boolean> {
  const { save } = await import("@tauri-apps/plugin-dialog");
  const { writeFile } = await import("@tauri-apps/plugin-fs");
  const path = await save({
    defaultPath: "clonebins.zip",
    filters: [{ name: "Zip archive", extensions: ["zip"] }],
  });
  if (!path) return false;
  await writeFile(path, bytes);
  return true;
}
