// === Device & Delivery Types ===

export type Device = "kobo" | "kindle" | "remarkable" | "other";
export type DeliveryMethod = "local" | "google_drive" | "email" | "koreader";
export type EmailMethod = "gmail" | "smtp";

// === User Config (mirrors user_profiles table) ===

export interface UserConfig {
  id: string;
  authId: string;

  // Newspaper settings
  title: string;
  language: string;
  totalArticleBudget: number;
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

  // OPDS wireless sync
  opdsToken: string | null;

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
  status: "delivered" | "failed" | "building" | "built";
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
  building?: boolean;
  editionDate: string;
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

// === Setup Status ===

export interface SetupStatus {
  isFirstVisit: boolean;
  needsDriveAuth: boolean;
  needsGmailAuth: boolean;
  needsSmtpConfig: boolean;
  needsKindleEmail: boolean;
  isFullyConfigured: boolean;
}

// === Onboarding ===

export interface OnboardingData {
  device: Device;
  deliveryMethod: DeliveryMethod;
  feeds: { name: string; url: string; category: string }[];
  title: string;
  readingTime: string;
  totalArticleBudget: number;
  includeImages: boolean;
  deliveryTime: string;
  timezone: string;
  googleDriveFolder: string;
  kindleEmail: string;
  emailMethod: EmailMethod;
}

// === Feed Stats ===

export interface FeedStat {
  url: string;
  name: string;
  observedAt: string;
  sampleCount: number;
  totalEntries: number;
  fresh24h: number;
  fresh48h: number;
  attempted: number;
  extracted: number;
  avgWordCount: number;
  medianWordCount: number;
  avgImages: number;
  articlesPerDay: number;
  estimatedReadMin: number;
  dailyReadMin: number;
}

// === API Types (Next.js API route responses) ===

export interface ApiSmtpTestResponse {
  success: boolean;
  message: string;
}

export interface ApiFeedValidateResponse {
  valid: boolean;
  name: string | null;
  error: string | null;
}
