/**
 * Authenticated fetch helpers used by the Website Admin pages.
 *
 * Reads the access token from the per-scope localStorage slot owned
 * by the AuthProvider (lib/auth.ts).
 */
import { loadSession } from "@/lib/auth";
import { env } from "@/lib/env";

export class AdminApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "AdminApiError";
  }
}

function authHeader(): Record<string, string> {
  const session = loadSession("admin");
  if (!session) throw new AdminApiError("Not authenticated", 401);
  return { Authorization: `Bearer ${session.accessToken}` };
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail[0].msg;
    } catch {
      /* swallow */
    }
    throw new AdminApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

async function postMultipart<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const session = loadSession("admin");
  if (!session) throw new AdminApiError("Not authenticated", 401);
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    headers: { Authorization: `Bearer ${session.accessToken}` },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Upload failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail[0].msg;
    } catch {
      /* swallow */
    }
    throw new AdminApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

/**
 * Trigger a binary download from an admin endpoint and save it to disk
 * via an anchor click. Used for database backups — the response body
 * may be hundreds of megabytes, so we stream it as a Blob instead of
 * trying to parse it as JSON. ``method`` defaults to POST since most
 * "generate + download" endpoints want a write-style verb.
 */
async function downloadFile(
  path: string,
  fallbackName: string,
  method: "GET" | "POST" = "POST"
): Promise<void> {
  const session = loadSession("admin");
  if (!session) throw new AdminApiError("Not authenticated", 401);
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    method,
    headers: { Authorization: `Bearer ${session.accessToken}` },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Download failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* swallow */
    }
    throw new AdminApiError(detail, response.status);
  }

  // Prefer the server-provided filename from Content-Disposition; fall
  // back to ``fallbackName`` if the header is missing or unparseable.
  let filename = fallbackName;
  const disposition = response.headers.get("content-disposition");
  if (disposition) {
    const match = /filename="?([^"]+)"?/i.exec(disposition);
    if (match?.[1]) filename = match[1];
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

export interface UploadedImage {
  url: string;
  filename: string;
  size: number;
  mime_type: string;
}

export const adminApi = {
  get<T>(path: string) {
    return request<T>(path);
  },
  post<T>(path: string, body?: unknown) {
    return request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  patch<T>(path: string, body?: unknown) {
    return request<T>(path, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  put<T>(path: string, body?: unknown) {
    return request<T>(path, {
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  delete<T = void>(path: string) {
    return request<T>(path, { method: "DELETE" });
  },
  /**
   * Upload an image to the CMS storage.
   *
   * ``folder`` routes the file under ``cms/<folder>/`` instead of
   * the flat ``cms/`` root — e.g. ``"hero"`` produces
   * ``cms/hero/<hash>.jpg``. Backend validates the shape
   * (lowercase letters / digits / hyphens / slashes only) so
   * arbitrary strings can't escape the prefix.
   */
  uploadImage(file: File, folder?: string): Promise<UploadedImage> {
    const fd = new FormData();
    fd.append("file", file);
    const path = folder
      ? `/admin/cms/uploads/image?folder=${encodeURIComponent(folder)}`
      : "/admin/cms/uploads/image";
    return postMultipart<UploadedImage>(path, fd);
  },
  uploadMedia<T>(file: File, folder?: string): Promise<T> {
    const fd = new FormData();
    fd.append("file", file);
    const path = folder
      ? `/admin/cms/media/upload?folder=${encodeURIComponent(folder)}`
      : "/admin/cms/media/upload";
    return postMultipart<T>(path, fd);
  },
  /**
   * Run pg_dump server-side and stream the resulting .dump file back
   * as a downloadable file. The browser saves it via an anchor click.
   */
  downloadFile,
  /** Generic JSON-returning multipart POST (e.g. restore upload). */
  postMultipart<T>(path: string, fd: FormData) {
    return postMultipart<T>(path, fd);
  },
};
