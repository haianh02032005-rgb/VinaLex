/**
 * VinaLex - API Configuration Resolver
 * Tu dong phan giai URL API chuan xac cho ca moi truong Localhost,
 * mang noi bo (LAN IP) va moi truong Internet (Cloudflare Tunnel / Vercel / Domain).
 * 
 * Phong thu da tang (Defense-in-depth):
 * - Neu chay tren Client (trinh duyet) voi HTTPS hoac domain ben ngoai,
 *   bat buoc tra ve duong dan tuong doi '/api/v1' de Next.js Reverse Proxy xu ly,
 *   loai bo triet de loi Mixed Content Security.
 */

export function getApiBaseUrl(): string {
  // 1. Uu tien NEXT_PUBLIC_BACKEND_URL neu duoc cau hinh (vi du: Render, Cloudflare Tunnel...)
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (backendUrl && backendUrl.startsWith('http')) {
    const cleanBackend = backendUrl.replace(/\/$/, '');
    return cleanBackend.endsWith('/api/v1') ? cleanBackend : `${cleanBackend}/api/v1`;
  }

  // 2. Neu co NEXT_PUBLIC_API_URL dang URL tuyet doi
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl && envUrl.startsWith('http')) {
    return envUrl.replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const isHttps = window.location.protocol === 'https:';
    const isExternalHost = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';

    if (isHttps || isExternalHost) {
      return '/api/v1';
    }
  }

  if (envUrl && envUrl.startsWith('/')) {
    return envUrl;
  }

  return 'http://127.0.0.1:8000/api/v1';
}

/**
 * Xay dung duong dan day du cho mot endpoint API
 */
export function buildApiUrl(path: string): string {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${cleanPath}`;
}
