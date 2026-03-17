/**
 * AES-256-GCM field-level encryption for sensitive data (SMTP passwords).
 *
 * Requires SMTP_ENCRYPTION_KEY env var (64 hex chars = 32 bytes).
 * Gracefully degrades: no key → passthrough (dev mode compatible).
 * Handles pre-existing plaintext values via try/catch fallback.
 *
 * Storage format: base64(iv[12] + ciphertext + tag[16])
 */

import crypto from "crypto";

const ALGORITHM = "aes-256-gcm" as const;
const IV_LENGTH = 12;
const TAG_LENGTH = 16;

function getEncryptionKey(): Buffer | null {
  const key = process.env.SMTP_ENCRYPTION_KEY;
  if (!key || key.length !== 64) return null;
  return Buffer.from(key, "hex");
}

export function encryptField(plaintext: string): string {
  if (!plaintext) return plaintext;
  const key = getEncryptionKey();
  if (!key) return plaintext;

  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([iv, encrypted, tag]).toString("base64");
}

export function decryptField(ciphertext: string): string {
  if (!ciphertext) return ciphertext;
  const key = getEncryptionKey();
  if (!key) return ciphertext;

  try {
    const data = Buffer.from(ciphertext, "base64");
    if (data.length < IV_LENGTH + TAG_LENGTH + 1) return ciphertext;

    const iv = data.subarray(0, IV_LENGTH);
    const tag = data.subarray(data.length - TAG_LENGTH);
    const encrypted = data.subarray(IV_LENGTH, data.length - TAG_LENGTH);

    const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
    decipher.setAuthTag(tag);
    return (
      decipher.update(encrypted).toString("utf8") + decipher.final("utf8")
    );
  } catch {
    return ciphertext; // Decryption failed — return as-is (pre-existing plaintext)
  }
}
