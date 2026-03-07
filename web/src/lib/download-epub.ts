import { createClient } from "@/lib/supabase/client";

export async function downloadEpub(
  storagePath: string,
  filename: string
): Promise<void> {
  const supabase = createClient();
  const { data, error } = await supabase.storage
    .from("epubs")
    .download(storagePath);

  if (error || !data) {
    throw new Error(error?.message ?? "Download failed");
  }

  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
