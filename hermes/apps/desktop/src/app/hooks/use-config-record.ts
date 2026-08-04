import { useStore } from '@nanostores/react'
import { useQuery } from '@tanstack/react-query'

import { getHermesConfigRecord } from '@/hermes'
import { queryClient, writeCache } from '@/lib/query-client'
import { $activeGatewayProfile, normalizeProfileKey } from '@/store/profile'
import type { HermesConfigRecord } from '@/types/hermes'

// One shared cache for the whole profile config record (`GET /api/config`).
// Every settings surface (MCP, model, config) reads and writes through this key
// so a save in one shows in the others, and revisiting a tab paints the cache
// instead of blanking on a fresh fetch.
//
// Distinct from session/hooks/use-hermes-config.ts, which is side-effecting —
// it pushes personality/cwd/voice/… into the session stores for live chat.
export const HERMES_CONFIG_KEY = ['hermes-config-record'] as const

const hermesConfigKey = (profile: string) => [...HERMES_CONFIG_KEY, normalizeProfileKey(profile)] as const

// staleTime 0 → serve cache instantly, background-revalidate on every mount.
export const useHermesConfigRecord = () => {
  const profile = useStore($activeGatewayProfile)

  return useQuery({ queryKey: hermesConfigKey(profile), queryFn: getHermesConfigRecord, staleTime: 0 })
}

export const setHermesConfigCache = (
  next:
    | HermesConfigRecord
    | undefined
    | ((prev: HermesConfigRecord | undefined) => HermesConfigRecord | undefined)
) => writeCache<HermesConfigRecord>(hermesConfigKey($activeGatewayProfile.get()))(next)

export const invalidateHermesConfig = () => queryClient.invalidateQueries({ queryKey: HERMES_CONFIG_KEY })
