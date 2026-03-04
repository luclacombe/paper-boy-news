// === Device & Delivery Types ===

export type Device = "kobo" | "kindle" | "remarkable" | "other";
export type DeliveryMethod = "local" | "google_drive" | "email";
export type EmailMethod = "gmail" | "smtp";

// === User Config (mirrors user_profiles table) ===

export interface UserConfig {
  id: string;
  authId: string;

  // Newspaper settings
  title: string;
  language: string;
  maxArticlesPerFeed: number;
  readingTime: string;
  includeImages: boolean;

  // Device + delivery
  device: Device;
  deliveryMethod: DeliveryMethod;
  googleDriveFolder: string;
  kindleEmail: string;
  emailMethod: EmailMethod;
  emailSmtpHost: string;
  emailSmtpPort: number;
  emailSender: string;
  emailPassword: string;

  // Schedule
  deliveryTime: string;
  timezone: string;

  // OAuth
  googleTokens: GoogleTokens | null;

  // State
  onboardingComplete: boolean;
  createdAt: string;
  updatedAt: string;
}

// === Feed ===

export interface Feed {
  id: string;
  userId: string;
  name: string;
  url: string;
  category: string;
  position: number;
  createdAt: string;
}

// === Delivery History ===

export interface DeliveryRecord {
  id: string;
  userId: string;
  status: "delivered" | "failed" | "building";
  editionNumber: number;
  editionDate: string;
  articleCount: number;
  sourceCount: number;
  fileSize: string;
  fileSizeBytes: number;
  deliveryMethod: string;
  deliveryMessage: string;
  errorMessage: string | null;
  epubStoragePath: string | null;
  sections: SectionSummary[] | null;
  createdAt: string;
}

// === Build Types ===

export interface SectionSummary {
  name: string;
  headlines: string[];
}

export interface BuildResult {
  success: boolean;
  totalArticles: number;
  sections: SectionSummary[];
  fileSize: string;
  fileSizeBytes: number;
  epubStoragePath: string | null;
  error: string | null;
}

// === Google OAuth ===

export interface GoogleTokens {
  token: string;
  refreshToken: string;
  tokenUri: string;
  clientId: string;
  clientSecret: string;
  scopes: string[];
  expiry: string | null;
}

// === Feed Catalog ===

export interface CatalogFeed {
  id: string;
  name: string;
  url: string;
  description: string;
}

export interface CatalogCategory {
  name: string;
  feeds: CatalogFeed[];
}

export interface CatalogBundle {
  name: string;
  description: string;
  feeds: string[]; // Feed IDs
}

// === Onboarding ===

export interface OnboardingData {
  device: Device;
  deliveryMethod: DeliveryMethod;
  feeds: { name: string; url: string; category: string }[];
  title: string;
  readingTime: string;
  maxArticlesPerFeed: number;
  includeImages: boolean;
  deliveryTime: string;
  timezone: string;
  googleDriveFolder: string;
  kindleEmail: string;
  emailMethod: EmailMethod;
}

// === API Types (FastAPI request/response) ===

export interface ApiBuildRequest {
  title: string;
  language: string;
  max_articles_per_feed: number;
  include_images: boolean;
  feeds: { name: string; url: string }[];
  device: string;
}

export interface ApiBuildResponse {
  success: boolean;
  epub_base64: string | null;
  total_articles: number;
  sections: { name: string; headlines: string[] }[];
  file_size: string;
  file_size_bytes: number;
  error: string | null;
}

export interface ApiDeliverRequest {
  epub_base64: string;
  title: string;
  device: string;
  delivery_method: string;
  google_drive_folder: string;
  google_tokens: Record<string, unknown> | null;
  kindle_email: string;
  email_smtp_host: string;
  email_smtp_port: number;
  email_sender: string;
  email_password: string;
}

export interface ApiDeliverResponse {
  success: boolean;
  message: string;
}

export interface ApiSmtpTestRequest {
  smtp_host: string;
  smtp_port: number;
  sender: string;
  password: string;
}

export interface ApiSmtpTestResponse {
  success: boolean;
  message: string;
}

export interface ApiFeedValidateResponse {
  valid: boolean;
  name: string | null;
  error: string | null;
}
