import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: vi.fn(),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock DB
const mockDbRows: unknown[] = [];
const mockInsertValues = vi.fn().mockResolvedValue(undefined);
const mockCountResult = [{ value: 0 }];

vi.mock("@/db", () => ({
  db: {
    select: vi.fn().mockImplementation((fields?: unknown) => ({
      from: vi.fn().mockReturnValue({
        where: vi.fn().mockImplementation(() => {
          // If selecting count, return count result
          if (fields && typeof fields === "object" && "value" in (fields as Record<string, unknown>)) {
            return mockCountResult;
          }
          return {
            orderBy: vi.fn().mockReturnValue({
              limit: vi.fn().mockImplementation(() => mockDbRows),
            }),
          };
        }),
      }),
    })),
    insert: vi.fn().mockReturnValue({
      values: mockInsertValues,
    }),
  },
}));

const FAKE_PROFILE = { id: "profile-1", authId: "auth-1" };

const FAKE_HISTORY_ROW = {
  id: "hist-1",
  userId: "profile-1",
  status: "delivered",
  editionNumber: 1,
  editionDate: "2025-01-15",
  articleCount: 12,
  sourceCount: 3,
  fileSize: "45 KB",
  fileSizeBytes: 46000,
  deliveryMethod: "local",
  deliveryMessage: "Available for download",
  errorMessage: null,
  epubStoragePath: null,
  sections: [{ name: "Tech", headlines: ["Article 1"] }],
  createdAt: new Date("2025-01-15"),
};

describe("getDeliveryHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDbRows.length = 0;
  });

  it("returns empty array when not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { getDeliveryHistory } = await import("@/actions/delivery-history");
    const result = await getDeliveryHistory();
    expect(result).toEqual([]);
  });

  it("returns mapped records for authenticated user", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockDbRows.push(FAKE_HISTORY_ROW);
    const { getDeliveryHistory } = await import("@/actions/delivery-history");
    const result = await getDeliveryHistory();
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe("delivered");
    expect(result[0].articleCount).toBe(12);
    expect(result[0].createdAt).toBe("2025-01-15T00:00:00.000Z");
  });
});

describe("getEditionCount", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 0 when not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { getEditionCount } = await import("@/actions/delivery-history");
    const result = await getEditionCount();
    expect(result).toBe(0);
  });

  it("returns count from DB", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockCountResult[0] = { value: 5 };
    const { getEditionCount } = await import("@/actions/delivery-history");
    const result = await getEditionCount();
    expect(result).toBe(5);
  });
});
