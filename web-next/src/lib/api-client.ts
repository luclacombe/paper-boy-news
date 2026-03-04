import type {
  ApiBuildRequest,
  ApiBuildResponse,
  ApiDeliverRequest,
  ApiDeliverResponse,
  ApiSmtpTestRequest,
  ApiSmtpTestResponse,
  ApiFeedValidateResponse,
} from "@/types";

const FASTAPI_URL =
  process.env.NEXT_PUBLIC_FASTAPI_URL ?? "http://localhost:8000";

async function apiRequest<T>(
  path: string,
  body: unknown,
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${FASTAPI_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error (${response.status}): ${error}`);
  }

  return response.json() as Promise<T>;
}

export async function buildNewspaper(
  request: ApiBuildRequest,
  token?: string
): Promise<ApiBuildResponse> {
  return apiRequest<ApiBuildResponse>("/build", request, token);
}

export async function deliverNewspaper(
  request: ApiDeliverRequest,
  token?: string
): Promise<ApiDeliverResponse> {
  return apiRequest<ApiDeliverResponse>("/deliver", request, token);
}

export async function testSmtpConnection(
  request: ApiSmtpTestRequest,
  token?: string
): Promise<ApiSmtpTestResponse> {
  return apiRequest<ApiSmtpTestResponse>("/smtp-test", request, token);
}

export async function validateFeedUrl(
  url: string,
  token?: string
): Promise<ApiFeedValidateResponse> {
  return apiRequest<ApiFeedValidateResponse>(
    "/feeds/validate",
    { url },
    token
  );
}
