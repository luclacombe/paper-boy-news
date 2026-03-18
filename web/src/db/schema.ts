import {
  pgTable,
  uuid,
  text,
  integer,
  boolean,
  timestamp,
  jsonb,
  real,
} from "drizzle-orm/pg-core";

// ── User profiles (extends Supabase auth.users) ──

export const userProfiles = pgTable("user_profiles", {
  id: uuid("id").primaryKey().defaultRandom(),
  authId: uuid("auth_id").notNull().unique(),

  // Newspaper settings
  title: text("title").notNull().default("Morning Digest"),
  language: text("language").notNull().default("en"),
  totalArticleBudget: integer("total_article_budget").notNull().default(7),
  readingTime: text("reading_time").notNull().default("20 min"),
  includeImages: boolean("include_images").notNull().default(true),

  // Device + delivery
  device: text("device").notNull().default("kobo"),
  deliveryMethod: text("delivery_method").notNull().default("local"),
  googleDriveFolder: text("google_drive_folder")
    .notNull()
    .default("Rakuten Kobo"),
  recipientEmail: text("recipient_email").default(""),

  // Schedule
  deliveryTime: text("delivery_time").notNull().default("06:00"),
  timezone: text("timezone").notNull().default("UTC"),

  // OAuth tokens (encrypted JSON)
  googleTokens: jsonb("google_tokens"),

  // OPDS wireless sync (KOReader)
  opdsToken: text("opds_token"),
  opdsTokenExpiresAt: timestamp("opds_token_expires_at", { withTimezone: true }),

  // Onboarding
  onboardingComplete: boolean("onboarding_complete").notNull().default(false),

  // Timestamps
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

// ── User feeds (normalized from the feeds array) ──

export const userFeeds = pgTable("user_feeds", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id")
    .notNull()
    .references(() => userProfiles.id, { onDelete: "cascade" }),
  name: text("name").notNull(),
  url: text("url").notNull(),
  category: text("category").notNull().default("Custom"),
  position: integer("position").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

// ── Delivery history ──

export const deliveryHistory = pgTable("delivery_history", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id")
    .notNull()
    .references(() => userProfiles.id, { onDelete: "cascade" }),

  status: text("status").notNull(), // building | built | delivered | failed
  editionNumber: integer("edition_number"),
  editionDate: text("edition_date").notNull(),
  articleCount: integer("article_count").default(0),
  sourceCount: integer("source_count").default(0),
  fileSize: text("file_size").default("0 KB"),
  fileSizeBytes: integer("file_size_bytes").default(0),
  deliveryMethod: text("delivery_method").default(""),
  deliveryMessage: text("delivery_message").default(""),
  errorMessage: text("error_message"),

  // Supabase Storage path
  epubStoragePath: text("epub_storage_path"),

  // Sections + headlines JSON (for dashboard display)
  sections: jsonb("sections"), // [{ name, headlines: [string] }]

  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

// ── Feed stats (global, not per-user) ──

export const feedStats = pgTable("feed_stats", {
  url: text("url").primaryKey(),
  name: text("name").notNull(),
  observedAt: timestamp("observed_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  sampleCount: integer("sample_count").notNull().default(1),

  // Latest observation
  totalEntries: integer("total_entries").notNull().default(0),
  fresh24h: integer("fresh_24h").notNull().default(0),
  fresh48h: integer("fresh_48h").notNull().default(0),
  attempted: integer("attempted").notNull().default(0),
  extracted: integer("extracted").notNull().default(0),
  avgWordCount: real("avg_word_count").notNull().default(0),
  medianWordCount: real("median_word_count").notNull().default(0),
  avgImages: real("avg_images").notNull().default(0),

  // Derived rolling averages
  articlesPerDay: real("articles_per_day").notNull().default(0),
  estimatedReadMin: real("estimated_read_min").notNull().default(0),
  dailyReadMin: real("daily_read_min").notNull().default(0),

  // Last 30 daily observations
  history: jsonb("history").notNull().default([]),
});
