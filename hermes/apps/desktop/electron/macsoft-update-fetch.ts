export type MacSoftUpdateFetch = (url: string, init: RequestInit) => Promise<Response>

function trustedHttpsUrl(value: string): URL {
  const parsed = new URL(value)
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password) {
    throw new Error('MacSoft update resources must use trusted HTTPS URLs.')
  }
  return parsed
}

export async function fetchTrustedMacSoftUpdateResource(
  url: string,
  init: RequestInit,
  fetcher: MacSoftUpdateFetch
): Promise<Response> {
  const trusted = trustedHttpsUrl(url)
  return fetcher(trusted.href, { ...init, redirect: 'follow' })
}
