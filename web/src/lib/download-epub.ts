import { createClient } from "@/lib/supabase/client";

// ─── IndexedDB helpers (one key-value pair for device folder handle) ──

const IDB_NAME = "paper-boy-device";
const IDB_STORE = "handles";
const IDB_KEY = "device-folder";

function openHandleDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(IDB_STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function getSavedHandle(): Promise<FileSystemDirectoryHandle | null> {
  const db = await openHandleDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readonly");
    const req = tx.objectStore(IDB_STORE).get(IDB_KEY);
    req.onsuccess = () => resolve(req.result ?? null);
    req.onerror = () => reject(req.error);
  });
}

async function saveHandle(handle: FileSystemDirectoryHandle): Promise<void> {
  const db = await openHandleDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readwrite");
    tx.objectStore(IDB_STORE).put(handle, IDB_KEY);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function removeHandle(): Promise<void> {
  const db = await openHandleDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IDB_STORE, "readwrite");
    tx.objectStore(IDB_STORE).delete(IDB_KEY);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ─── Feature detection ────────────────────────────────────────────────

export function supportsDirectoryPicker(): boolean {
  return (
    typeof window !== "undefined" && typeof window.showDirectoryPicker === "function"
  );
}

// ─── Folder management ───────────────────────────────────────────────

export async function pickDeviceFolder(): Promise<void> {
  const handle = await window.showDirectoryPicker!({
    id: "ereader-device",
    mode: "readwrite",
  });
  await saveHandle(handle);
}

export async function hasDeviceFolder(): Promise<boolean> {
  const handle = await getSavedHandle();
  return handle !== null;
}

export async function getDeviceFolderName(): Promise<string | null> {
  const handle = await getSavedHandle();
  return handle?.name ?? null;
}

export async function clearDeviceFolder(): Promise<void> {
  await removeHandle();
}

// ─── Fetch blob from Supabase ─────────────────────────────────────────

async function fetchEpubBlob(storagePath: string): Promise<Blob> {
  const supabase = createClient();
  const { data, error } = await supabase.storage
    .from("epubs")
    .download(storagePath);

  if (error || !data) {
    throw new Error(error?.message ?? "Download failed");
  }
  return data;
}

// ─── Browser download (current behavior) ─────────────────────────────

export async function downloadEpub(
  storagePath: string,
  filename: string
): Promise<void> {
  const blob = await fetchEpubBlob(storagePath);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Send to device (File System Access API) ─────────────────────────

export async function sendToDevice(
  storagePath: string,
  filename: string
): Promise<void> {
  const handle = await getSavedHandle();
  if (!handle) {
    // No saved folder — fall back to regular download
    return downloadEpub(storagePath, filename);
  }

  // Check/request permission (must be called from user gesture — it is)
  const perm = await handle.queryPermission({ mode: "readwrite" });
  if (perm === "denied") {
    return downloadEpub(storagePath, filename);
  }
  if (perm === "prompt") {
    const result = await handle.requestPermission({ mode: "readwrite" });
    if (result !== "granted") {
      return downloadEpub(storagePath, filename);
    }
  }

  const blob = await fetchEpubBlob(storagePath);

  const fileHandle = await handle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(blob);
  await writable.close();
}
