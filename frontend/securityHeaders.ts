/** The browser security policy, defined once and written out for each kind of static host. */

export function securityHeaders(apiBaseUrl: string): Record<string, string> {
  const api = new URL(apiBaseUrl)
  const socket = `${api.protocol === 'https:' ? 'wss:' : 'ws:'}//${api.host}`
  const policy = [
    "default-src 'self'",
    "script-src 'self'",
    // Animations set style attributes at run time.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    `connect-src 'self' ${api.origin} ${socket}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ')
  return {
    'Content-Security-Policy': policy,
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  }
}

/** The `_headers` file read by Cloudflare Pages and Netlify. */
export function pagesHeadersFile(headers: Record<string, string>): string {
  const lines = Object.entries(headers).map(([name, value]) => `  ${name}: ${value}`)
  return ['/*', ...lines, ''].join('\n')
}

/** An include for nginx, used by the Docker image. */
export function nginxHeadersFile(headers: Record<string, string>): string {
  return Object.entries(headers)
    .map(([name, value]) => `add_header ${name} "${value}" always;\n`)
    .join('')
}
