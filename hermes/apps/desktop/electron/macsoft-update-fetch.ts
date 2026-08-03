const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308])
const MAX_REDIRECTS = 5

export type MacSoftUpdateFetch = (url: string, init: RequestInit) => Promise<Response>

function trustedHttpsUrl(value: string, base?: URL): URL {
  const parsed = base ? new URL(value, base) : new URL(value)
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
  let current = trustedHttpsUrl(url)

  for (let redirects = 0; redirects <= MAX_REDIRECTS; redirects += 1) {
    const response = await fetcher(current.href, { ...init, redirect: 'manual' })
    if (!REDIRECT_STATUSES.has(response.status)) return response

    if (redirects === MAX_REDIRECTS) {
      throw new Error('MacSoft update resource exceeded the redirect limit.')
    }
    const location = response.headers.get('location')
    if (!location) {
      throw new Error('MacSoft update redirect did not provide a destination.')
    }
    current = trustedHttpsUrl(location, current)
  }

  throw new Error('MacSoft update resource could not be resolved.')
}
