import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import type { MacSoftProductPaths } from './macsoft-product'

const DEFAULT_SERVER_PORT = 8787
const DEFAULT_AI_SERVICE_PORT = 8642
const DEV_RENDERER_PORT = 5174
const REQUEST_TIMEOUT_MS = 10_000

export interface NetworkAddress {
  address: string
  id: string
  interfaceName: string
  kind: 'ethernet' | 'other' | 'vpn' | 'virtual' | 'wifi'
  recommended: boolean
}

export interface ReadableCheckResult {
  action?: string
  details?: string
  fields?: Array<{ label: string; value: string }>
  ok: boolean
  summary: string
  title: string
}

export interface ServerAutoCountSettings {
  aiService: {
    port: number
    status: ReadableCheckResult
    url: string
  }
  autoCount: {
    apiKeyConfigured: boolean
    cloudUrl: string
    companyId: string
    connectorId: string
  }
  clientUrl: string
  localOnlyAddress: string
  networkAddresses: NetworkAddress[]
  projectRoot: string
  recommendedAddress: string | null
  server: {
    port: number
    status: ReadableCheckResult
  }
  warnings: string[]
}

export interface SaveServerAutoCountInput {
  aiServicePort: number
  aiServiceUrl: string
  apiKey?: string
  cloudUrl: string
  companyId: string
  connectorId: string
  serverPort: number
}

export interface SaveServerAutoCountResult {
  backups: string[]
  changedFiles: string[]
  restartRequired: boolean
  servicesToRestart: string[]
  settings: ServerAutoCountSettings
}

export interface MacSoftModelSettings {
  model: string
  provider: string
}

export interface SaveMacSoftModelSettingsResult {
  backups: string[]
  changedFiles: string[]
  settings: MacSoftModelSettings
}

export interface AutoCountTestInput {
  apiKey?: string
  cloudUrl: string
  companyId: string
  connectorId: string
}

interface ConfigPaths {
  plugin: string
  runtime: string
  server: string
}

interface FetchResponseLike {
  json: () => Promise<unknown>
  ok: boolean
  status: number
}

type FetchLike = (url: string, init?: Record<string, unknown>) => Promise<FetchResponseLike>
type NetworkInterfacesLike = ReturnType<typeof os.networkInterfaces>

interface ServiceDependencies {
  ensureProductData?: () => Promise<void>
  fetchImpl?: FetchLike
  networkInterfaces?: () => NetworkInterfacesLike
  now?: () => Date
  productPaths?: MacSoftProductPaths
  projectRoot?: string
}

type ConfigurationReadFailure = 'filesystem' | 'malformed' | 'missing' | 'permission'

class ConfigurationReadError extends Error {
  readonly failure: ConfigurationReadFailure

  constructor(failure: ConfigurationReadFailure, message: string) {
    super(message)
    this.name = 'ConfigurationReadError'
    this.failure = failure
  }
}

function stripBom(value: string): string {
  return value.charCodeAt(0) === 0xfeff ? value.slice(1) : value
}

function splitYamlValueAndComment(value: string): { comment: string; value: string } {
  let quote: "'" | '"' | null = null

  for (let index = 0; index < value.length; index += 1) {
    const char = value[index]

    if ((char === "'" || char === '"') && value[index - 1] !== '\\') {
      quote = quote === char ? null : quote || char
    }

    if (char === '#' && quote === null && (index === 0 || /\s/.test(value[index - 1]))) {
      return { comment: value.slice(index), value: value.slice(0, index).trimEnd() }
    }
  }

  return { comment: '', value: value.trimEnd() }
}

function parseYamlScalar(value: string): string {
  const trimmed = splitYamlValueAndComment(value).value.trim()

  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return String(JSON.parse(trimmed))
  }

  if (trimmed.startsWith("'") && trimmed.endsWith("'")) {
    return trimmed.slice(1, -1).replace(/''/g, "'")
  }

  return trimmed
}

function yamlScalarLocation(text: string, targetPath: string[]): { index: number; match: RegExpMatchArray } {
  const lines = text.split(/\r?\n/)
  const parents: Array<{ indent: number; key: string }> = []

  for (let index = 0; index < lines.length; index += 1) {
    const cleanLine = index === 0 ? stripBom(lines[index]) : lines[index]
    const match = cleanLine.match(/^(\s*)([A-Za-z0-9_-]+)(\s*:\s*)(.*)$/)

    if (!match) {
      continue
    }

    const indent = match[1].replace(/\t/g, '  ').length

    while (parents.length && parents[parents.length - 1].indent >= indent) {
      parents.pop()
    }

    const currentPath = [...parents.map(item => item.key), match[2]]

    if (currentPath.join('.') === targetPath.join('.')) {
      return { index, match }
    }

    if (!splitYamlValueAndComment(match[4]).value.trim()) {
      parents.push({ indent, key: match[2] })
    }
  }

  throw new Error(`Required configuration field is missing: ${targetPath.join('.')}`)
}

export function readYamlScalar(text: string, targetPath: string[]): string {
  return parseYamlScalar(yamlScalarLocation(text, targetPath).match[4])
}

export function patchYamlScalar(text: string, targetPath: string[], nextValue: number | string): string {
  const newline = text.includes('\r\n') ? '\r\n' : '\n'
  const trailingNewline = /\r?\n$/.test(text)
  const lines = text.split(/\r?\n/)

  if (trailingNewline) {
    lines.pop()
  }

  const { index, match } = yamlScalarLocation(text, targetPath)
  const old = splitYamlValueAndComment(match[4])
  const encoded = typeof nextValue === 'number' ? String(nextValue) : JSON.stringify(nextValue)
  const separator = old.comment ? ' ' : ''
  const bom = index === 0 && text.charCodeAt(0) === 0xfeff ? '\ufeff' : ''
  lines[index] = `${bom}${match[1]}${match[2]}${match[3]}${encoded}${separator}${old.comment}`

  return lines.join(newline) + (trailingNewline ? newline : '')
}

function configPaths(projectRoot: string): ConfigPaths {
  return {
    plugin: path.join(projectRoot, 'runtime', 'plugins', 'macsoft-autocount', 'config.json'),
    runtime: path.join(projectRoot, 'runtime', 'config.yaml'),
    server: path.join(projectRoot, 'server', 'macsoft-server.yaml')
  }
}

export function resolveMacSoftProjectRoot(options: {
  configuredRoot?: null | string
  hermesHome?: null | string
  sourceRepoRoot?: null | string
}): string {
  const candidates = [
    options.configuredRoot,
    options.hermesHome && path.basename(options.hermesHome).toLowerCase() === 'runtime'
      ? path.dirname(options.hermesHome)
      : null,
    options.sourceRepoRoot && path.basename(options.sourceRepoRoot).toLowerCase() === 'hermes'
      ? path.dirname(options.sourceRepoRoot)
      : null
  ].filter((candidate): candidate is string => Boolean(candidate))

  for (const candidate of candidates) {
    const resolved = path.resolve(candidate)
    const paths = configPaths(resolved)

    if (fs.existsSync(paths.server) && fs.existsSync(paths.runtime) && fs.existsSync(paths.plugin)) {
      return resolved
    }
  }

  throw new Error('MacSoft Agent project configuration could not be located.')
}

function validatePort(value: unknown, label: string): number {
  const port = typeof value === 'number' ? value : Number(value)

  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error(`${label} must be a whole number between 1 and 65535.`)
  }

  return port
}

function validateHttpUrl(value: unknown, label: string): string {
  let url: URL

  try {
    url = new URL(String(value || '').trim())
  } catch {
    throw new Error(`${label} must be a valid http:// or https:// URL.`)
  }

  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error(`${label} must be a plain http:// or https:// URL without credentials, a query, or a fragment.`)
  }

  return url.toString().replace(/\/$/, '')
}

function validateId(value: unknown, label: string): string {
  const id = String(value || '').trim()

  const hasControlCharacters = Array.from(id).some(character => {
    const code = character.charCodeAt(0)

    return code < 32 || code === 127
  })

  if (!id || id.length > 200 || hasControlCharacters) {
    throw new Error(`${label} is required and must be 200 characters or fewer.`)
  }

  return id
}

function readOptionalId(value: unknown, label: string): string {
  const id = String(value || '').trim()
  return id ? validateId(id, label) : ''
}

function validateApiKey(value: unknown, allowEmpty = true): string {
  const key = String(value || '').trim()

  if (!key && allowEmpty) {
    return ''
  }

  if (!key || key.length > 4096) {
    throw new Error('API Key is required and must be 4096 characters or fewer.')
  }

  if (/^bearer\s+/i.test(key)) {
    throw new Error('Enter the API Key only. Remove the "Bearer " prefix.')
  }

  return key
}

function validateModelSetting(value: unknown, label: string): string {
  const setting = String(value || '').trim()
  const hasControlCharacters = Array.from(setting).some(character => {
    const code = character.charCodeAt(0)

    return code < 32 || code === 127
  })

  if (!setting || setting.length > 256 || hasControlCharacters) {
    throw new Error(`${label} is required and must be 256 characters or fewer.`)
  }

  return setting
}

function interfaceKind(name: string): NetworkAddress['kind'] {
  if (/vpn|wireguard|openvpn|tailscale|zerotier/i.test(name)) {
    return 'vpn'
  }

  if (/virtual|vmware|vbox|hyper-v|vethernet|docker|wsl|loopback|tunnel|pseudo/i.test(name)) {
    return 'virtual'
  }

  if (/wi-?fi|wireless|wlan/i.test(name)) {
    return 'wifi'
  }

  if (/ethernet|\beth\d*\b|local area connection/i.test(name)) {
    return 'ethernet'
  }

  return 'other'
}

function networkScore(item: Omit<NetworkAddress, 'recommended'>): number {
  const kindScore = { ethernet: 500, wifi: 480, other: 300, vpn: 100, virtual: 50 }[item.kind]
  const privateScore = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(item.address) ? 40 : 0

  return kindScore + privateScore
}

export function detectNetworkAddresses(interfaces: NetworkInterfacesLike): {
  addresses: NetworkAddress[]
  recommendedAddress: string | null
} {
  const candidates: Array<Omit<NetworkAddress, 'recommended'>> = []

  for (const [interfaceName, addresses] of Object.entries(interfaces)) {
    for (const address of addresses || []) {
      const family = String(address.family)

      if (family !== 'IPv4' && family !== '4') {
        continue
      }

      if (address.internal || address.address === '127.0.0.1' || address.address.startsWith('169.254.')) {
        continue
      }

      const kind = interfaceKind(interfaceName)
      candidates.push({
        address: address.address,
        id: `${interfaceName}:${address.address}`,
        interfaceName,
        kind
      })
    }
  }

  candidates.sort((left, right) => networkScore(right) - networkScore(left) || left.interfaceName.localeCompare(right.interfaceName))
  const recommendedAddress = candidates.find(item => item.kind !== 'virtual' && item.kind !== 'vpn')?.address || candidates[0]?.address || null

  return {
    addresses: candidates.map(item => ({ ...item, recommended: item.address === recommendedAddress })),
    recommendedAddress
  }
}

function timestamp(date: Date): string {
  return date.toISOString().replace(/[-:TZ.]/g, '').slice(0, 17)
}

function atomicWrite(filePath: string, contents: string): void {
  const tempPath = path.join(path.dirname(filePath), `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`)
  const mode = fs.statSync(filePath).mode
  let descriptor: number | null = null

  try {
    descriptor = fs.openSync(tempPath, 'wx', mode)
    fs.writeFileSync(descriptor, contents, 'utf8')
    fs.fsyncSync(descriptor)
    fs.closeSync(descriptor)
    descriptor = null
    fs.renameSync(tempPath, filePath)
  } finally {
    if (descriptor !== null) {
      fs.closeSync(descriptor)
    }

    if (fs.existsSync(tempPath)) {
      fs.rmSync(tempPath, { force: true })
    }
  }
}

function writeTransaction(changes: Map<string, string>, now: Date): string[] {
  if (!changes.size) {
    return []
  }

  const originals = new Map<string, string>()
  const backups: string[] = []
  const suffix = timestamp(now)

  for (const filePath of changes.keys()) {
    const original = fs.readFileSync(filePath, 'utf8')
    const backupPath = `${filePath}.backup-${suffix}`
    originals.set(filePath, original)
    fs.copyFileSync(filePath, backupPath, fs.constants.COPYFILE_EXCL)
    backups.push(backupPath)
  }

  try {
    for (const [filePath, contents] of changes) {
      atomicWrite(filePath, contents)
    }
  } catch (error) {
    for (const [filePath, original] of originals) {
      try {
        atomicWrite(filePath, original)
      } catch {
        // Keep the timestamped backup for manual recovery if rollback also fails.
      }
    }

    throw error
  }

  return backups
}

function readConfigText(filePath: string): string {
  try {
    return fs.readFileSync(filePath, 'utf8')
  } catch (error) {
    const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : ''
    const fileName = path.basename(filePath)

    if (code === 'ENOENT') {
      throw new ConfigurationReadError(
        'missing',
        `MacSoft Agent configuration is incomplete because ${fileName} is missing. Product initialization is required.`
      )
    }
    if (code === 'EACCES' || code === 'EPERM') {
      throw new ConfigurationReadError(
        'permission',
        `MacSoft Agent cannot read ${fileName}. Check the product data folder permissions and try again.`
      )
    }
    throw new ConfigurationReadError(
      'filesystem',
      `MacSoft Agent could not read ${fileName}. Check the product data drive and try again.`
    )
  }
}

function readJsonObject(filePath: string): { object: Record<string, unknown>; raw: string } {
  const raw = readConfigText(filePath)
  let parsed: unknown

  try {
    parsed = JSON.parse(stripBom(raw))
  } catch {
    throw new ConfigurationReadError(
      'malformed',
      `${path.basename(filePath)} contains invalid JSON. The existing file was preserved; correct it and try again.`
    )
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new ConfigurationReadError(
      'malformed',
      `${path.basename(filePath)} must contain a JSON object. The existing file was preserved; correct it and try again.`
    )
  }

  return { object: parsed as Record<string, unknown>, raw }
}

function encodeJsonLikeOriginal(original: string, object: Record<string, unknown>): string {
  const newline = original.includes('\r\n') ? '\r\n' : '\n'
  const bom = original.charCodeAt(0) === 0xfeff ? '\ufeff' : ''

  return bom + JSON.stringify(object, null, 2).replace(/\n/g, newline) + newline
}

async function jsonRequest(fetchImpl: FetchLike, url: string, init: Record<string, unknown> = {}): Promise<FetchResponseLike> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    return await fetchImpl(url, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

function failedCheck(title: string, summary: string, action: string, details?: string): ReadableCheckResult {
  return { action, details, ok: false, summary, title }
}

function objectAt(value: unknown, pathParts: string[]): unknown {
  let current = value

  for (const part of pathParts) {
    if (!current || typeof current !== 'object' || Array.isArray(current)) {
      return undefined
    }

    current = (current as Record<string, unknown>)[part]
  }

  return current
}

function firstValue(value: unknown, paths: string[][]): unknown {
  for (const candidate of paths) {
    const found = objectAt(value, candidate)

    if (found !== undefined && found !== null && found !== '') {
      return found
    }
  }

  return undefined
}

function displayValue(value: unknown, fallback = 'Unavailable'): string {
  if (typeof value === 'boolean') {
    return value ? 'Confirmed' : 'Unavailable'
  }

  return value === undefined || value === null || value === '' ? fallback : String(value)
}

export class ServerAutoCountConfigService {
  readonly projectRoot: string
  private readonly ensureProductData?: () => Promise<void>
  private readonly fetchImpl: FetchLike
  private readonly networkInterfaces: () => NetworkInterfacesLike
  private readonly now: () => Date
  private readonly paths: ConfigPaths

  constructor({ ensureProductData, fetchImpl, networkInterfaces, now, productPaths, projectRoot }: ServiceDependencies) {
    if (!productPaths && !projectRoot) {
      throw new Error('MacSoft Agent product paths are required.')
    }
    this.projectRoot = path.resolve(productPaths?.programRoot || projectRoot!)
    this.paths = productPaths
      ? {
          plugin: path.join(productPaths.runtimeRoot, 'plugins', 'macsoft-autocount', 'config.json'),
          runtime: path.join(productPaths.runtimeRoot, 'config.yaml'),
          server: productPaths.serverConfig
        }
      : configPaths(this.projectRoot)
    this.fetchImpl = fetchImpl || (globalThis.fetch as unknown as FetchLike)
    this.ensureProductData = ensureProductData
    this.networkInterfaces = networkInterfaces || os.networkInterfaces
    this.now = now || (() => new Date())
  }

  refreshNetworkAddresses() {
    return detectNetworkAddresses(this.networkInterfaces())
  }

  async loadModelSettings(): Promise<MacSoftModelSettings> {
    let runtimeText: string

    try {
      runtimeText = readConfigText(this.paths.runtime)
    } catch (error) {
      if (error instanceof ConfigurationReadError && error.failure === 'missing' && this.ensureProductData) {
        await this.ensureProductData()
        runtimeText = readConfigText(this.paths.runtime)
      } else {
        throw error
      }
    }

    try {
      return {
        model: validateModelSetting(readYamlScalar(runtimeText, ['model', 'default']), 'Model'),
        provider: validateModelSetting(readYamlScalar(runtimeText, ['model', 'provider']), 'Provider')
      }
    } catch {
      throw new ConfigurationReadError(
        'malformed',
        'MacSoft Agent model configuration is unavailable. Check the configured provider and model, then try again.'
      )
    }
  }

  async saveModelSettings(input: MacSoftModelSettings): Promise<SaveMacSoftModelSettingsResult> {
    const provider = validateModelSetting(input?.provider, 'Provider')
    const model = validateModelSetting(input?.model, 'Model')
    const runtimeOriginal = readConfigText(this.paths.runtime)
    let runtimeNext = runtimeOriginal

    try {
      const currentProvider = readYamlScalar(runtimeOriginal, ['model', 'provider'])
      const currentModel = readYamlScalar(runtimeOriginal, ['model', 'default'])

      if (currentProvider !== provider) {
        runtimeNext = patchYamlScalar(runtimeNext, ['model', 'provider'], provider)
      }
      if (currentModel !== model) {
        runtimeNext = patchYamlScalar(runtimeNext, ['model', 'default'], model)
      }
    } catch {
      throw new ConfigurationReadError(
        'malformed',
        'MacSoft Agent model configuration is unavailable. Check the configured provider and model, then try again.'
      )
    }

    const changes = new Map<string, string>()

    if (runtimeNext !== runtimeOriginal) {
      changes.set(this.paths.runtime, runtimeNext)
    }

    let backups: string[]

    try {
      backups = writeTransaction(changes, this.now())
    } catch {
      throw new Error('MacSoft Agent could not save model settings. Check the product data permissions and try again.')
    }

    return {
      backups,
      changedFiles: [...changes.keys()],
      settings: { model, provider }
    }
  }

  async testServer(serverPort: unknown): Promise<ReadableCheckResult> {
    const port = validatePort(serverPort, 'Server port')

    try {
      const response = await jsonRequest(this.fetchImpl, `http://127.0.0.1:${port}/health`)
      const body = await response.json().catch(() => null)

      if (!response.ok || objectAt(body, ['ok']) !== true) {
        return failedCheck(
          'MacSoft Server is not ready',
          `The health check returned HTTP ${response.status}.`,
          'Confirm the Server is running on this port, then try again.',
          `HTTP ${response.status}`
        )
      }

      return {
        fields: [
          { label: 'Port', value: String(port) },
          { label: 'Connection', value: 'Available on this computer' }
        ],
        ok: true,
        summary: 'The Client-facing service is responding normally.',
        title: 'MacSoft Server running'
      }
    } catch (error) {
      return failedCheck(
        'MacSoft Server is not reachable',
        `Nothing responded on port ${port}.`,
        'Start or restart MacSoft Server and verify the configured port.',
        error instanceof Error && error.name === 'AbortError' ? 'Request timed out' : 'Connection failed'
      )
    }
  }

  async testAiService(rawUrl: unknown): Promise<ReadableCheckResult> {
    const url = validateHttpUrl(rawUrl, 'AI Service URL')

    try {
      const response = await jsonRequest(this.fetchImpl, `${url}/health`)

      if (!response.ok) {
        return failedCheck(
          'AI Service is not ready',
          `The health check returned HTTP ${response.status}.`,
          'Restart the AI Service and verify its URL.',
          `HTTP ${response.status}`
        )
      }

      return {
        fields: [{ label: 'Service URL', value: url }],
        ok: true,
        summary: 'The internal AI Service is responding normally.',
        title: 'AI Service running'
      }
    } catch (error) {
      return failedCheck(
        'AI Service is not reachable',
        'The internal service did not answer its health check.',
        'Start or restart the AI Service and verify the configured URL.',
        error instanceof Error && error.name === 'AbortError' ? 'Request timed out' : 'Connection failed'
      )
    }
  }

  async loadSettings(): Promise<ServerAutoCountSettings> {
    let serverText: string
    let runtimeText: string
    let plugin: Record<string, unknown>

    try {
      serverText = readConfigText(this.paths.server)
      runtimeText = readConfigText(this.paths.runtime)
      plugin = readJsonObject(this.paths.plugin).object
    } catch (error) {
      if (error instanceof ConfigurationReadError && error.failure === 'missing' && this.ensureProductData) {
        await this.ensureProductData()
        serverText = readConfigText(this.paths.server)
        runtimeText = readConfigText(this.paths.runtime)
        plugin = readJsonObject(this.paths.plugin).object
      } else {
        throw error
      }
    }

    let serverPort: number
    let aiServiceUrl: string
    let runtimeAiPort: number
    let urlPort: number
    let cloudUrl: string
    let companyId: string
    let connectorId: string

    try {
      serverPort = validatePort(readYamlScalar(serverText, ['server', 'port']), 'Server port')
      aiServiceUrl = validateHttpUrl(readYamlScalar(serverText, ['hermes', 'api_base_url']), 'AI Service URL')

      runtimeAiPort = validatePort(
        readYamlScalar(runtimeText, ['platforms', 'api_server', 'extra', 'port']),
        'AI Service port'
      )
      urlPort = validatePort(
        new URL(aiServiceUrl).port || (aiServiceUrl.startsWith('https:') ? 443 : 80),
        'AI Service port'
      )
      cloudUrl = validateHttpUrl(plugin.baseUrl, 'Cloud URL')
      companyId = readOptionalId(plugin.companyId, 'Company ID')
      connectorId = readOptionalId(plugin.connectorId, 'Connector ID')
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'A required value is invalid.'
      throw new ConfigurationReadError(
        'malformed',
        `MacSoft Agent configuration is malformed. The existing files were preserved. ${detail}`
      )
    }

    const network = this.refreshNetworkAddresses()
    const warnings: string[] = []

    if (urlPort !== runtimeAiPort) {
      warnings.push('AI Service port differs between Server and runtime configuration.')
    }

    const [serverStatus, aiServiceStatus] = await Promise.all([
      this.testServer(serverPort),
      this.testAiService(aiServiceUrl)
    ])

    return {
      aiService: { port: runtimeAiPort, status: aiServiceStatus, url: aiServiceUrl },
      autoCount: {
        apiKeyConfigured: Boolean(String(plugin.apiKey || '').trim()),
        cloudUrl,
        companyId,
        connectorId
      },
      clientUrl: network.recommendedAddress ? `http://${network.recommendedAddress}:${serverPort}` : `http://127.0.0.1:${serverPort}`,
      localOnlyAddress: '127.0.0.1',
      networkAddresses: network.addresses,
      projectRoot: this.projectRoot,
      recommendedAddress: network.recommendedAddress,
      server: { port: serverPort, status: serverStatus },
      warnings
    }
  }

  async saveSettings(input: SaveServerAutoCountInput): Promise<SaveServerAutoCountResult> {
    const serverPort = validatePort(input.serverPort, 'Server port')
    const aiServicePort = validatePort(input.aiServicePort, 'AI Service port')

    if (aiServicePort === DEV_RENDERER_PORT) {
      throw new Error('Port 5174 is reserved for development and cannot be used as the AI Service port.')
    }

    if (serverPort === aiServicePort) {
      throw new Error('MacSoft Server and AI Service must use different ports.')
    }

    const rawAiUrl = validateHttpUrl(input.aiServiceUrl, 'AI Service URL')
    const aiUrl = new URL(rawAiUrl)
    aiUrl.port = String(aiServicePort)
    const normalizedAiUrl = aiUrl.toString().replace(/\/$/, '')
    const cloudUrl = validateHttpUrl(input.cloudUrl, 'Cloud URL')
    const connectorId = validateId(input.connectorId, 'Connector ID')
    const companyId = validateId(input.companyId, 'Company ID')
    const replacementKey = validateApiKey(input.apiKey, true)
    const serverOriginal = fs.readFileSync(this.paths.server, 'utf8')
    const runtimeOriginal = fs.readFileSync(this.paths.runtime, 'utf8')
    const pluginSource = readJsonObject(this.paths.plugin)
    const plugin = { ...pluginSource.object }
    let serverNext = patchYamlScalar(serverOriginal, ['server', 'port'], serverPort)
    serverNext = patchYamlScalar(serverNext, ['hermes', 'api_base_url'], normalizedAiUrl)
    const runtimeNext = patchYamlScalar(runtimeOriginal, ['platforms', 'api_server', 'extra', 'port'], aiServicePort)
    plugin.baseUrl = cloudUrl
    plugin.connectorId = connectorId
    plugin.companyId = companyId

    if (replacementKey) {
      plugin.apiKey = replacementKey
    } else if (!String(plugin.apiKey || '').trim()) {
      throw new Error('API Key is required because no existing key is configured.')
    }

    const pluginNext = encodeJsonLikeOriginal(pluginSource.raw, plugin)
    const changes = new Map<string, string>()

    if (serverNext !== serverOriginal) {
      changes.set(this.paths.server, serverNext)
    }

    if (runtimeNext !== runtimeOriginal) {
      changes.set(this.paths.runtime, runtimeNext)
    }

    if (pluginNext !== pluginSource.raw) {
      changes.set(this.paths.plugin, pluginNext)
    }

    const backups = writeTransaction(changes, this.now())
    const servicesToRestart: string[] = []

    if (changes.has(this.paths.server)) {
      servicesToRestart.push('MacSoft Server')
    }

    if (changes.has(this.paths.runtime)) {
      servicesToRestart.push('AI Service')
    }

    return {
      backups,
      changedFiles: [...changes.keys()],
      restartRequired: servicesToRestart.length > 0,
      servicesToRestart,
      settings: await this.loadSettings()
    }
  }

  async testAutoCount(input: AutoCountTestInput): Promise<ReadableCheckResult> {
    const cloudUrl = validateHttpUrl(input.cloudUrl, 'Cloud URL')
    const connectorId = validateId(input.connectorId, 'Connector ID')
    const companyId = validateId(input.companyId, 'Company ID')
    const replacementKey = validateApiKey(input.apiKey, true)
    const { object: plugin } = readJsonObject(this.paths.plugin)
    const apiKey = replacementKey || validateApiKey(plugin.apiKey, false)
    const url = `${cloudUrl}/v1/connectors/${encodeURIComponent(connectorId)}/status`

    try {
      const response = await jsonRequest(this.fetchImpl, url, {
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${apiKey}`,
          'User-Agent': 'MacSoft-Agent-Desktop/0.17.0'
        },
        method: 'GET'
      })

      const body = await response.json().catch(() => null)

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          return failedCheck(
            'AutoCount authentication failed',
            'The configured API key was rejected.',
            'Check that the key is an App/Tenant API key and has not expired or been revoked.',
            `HTTP ${response.status}`
          )
        }

        if (response.status === 404) {
          return failedCheck(
            'AutoCount Connector was not found',
            'The configured Connector ID is not available for this account.',
            'Verify the Connector ID and confirm that the Local Connector is registered.',
            'HTTP 404'
          )
        }

        return failedCheck(
          'AutoCount connection failed',
          `AutoCount Cloud returned HTTP ${response.status}.`,
          'Verify the Cloud URL and try again. If the problem continues, check the cloud service status.',
          `HTTP ${response.status}`
        )
      }

      const online = firstValue(body, [['online'], ['data', 'online'], ['connector', 'online'], ['data', 'connector', 'online']])

      if (online === false) {
        return failedCheck(
          'AutoCount Connector is not online',
          'AutoCount Cloud can see the connector, but the Local Connector is offline.',
          'Start the Local Connector and verify the selected Connector ID.'
        )
      }

      const responseCompany = firstValue(body, [
        ['companyName'], ['company'], ['data', 'companyName'], ['data', 'company'], ['accountBook', 'companyName']
      ])

      const database = firstValue(body, [
        ['database'], ['databaseName'], ['data', 'database'], ['data', 'databaseName'], ['accountBook', 'database']
      ])

      const sqlServer = firstValue(body, [
        ['sqlServer'], ['serverName'], ['data', 'sqlServer'], ['data', 'serverName'], ['accountBook', 'sqlServer']
      ])

      const connectorVersion = firstValue(body, [
        ['connectorVersion'], ['version'], ['data', 'connectorVersion'], ['data', 'version']
      ])

      const updateRequired = firstValue(body, [
        ['updateRequired'], ['data', 'updateRequired'], ['connector', 'updateRequired']
      ])

      const writeAuthorized = firstValue(body, [
        ['writeAuthorized'], ['writeAuthorization'], ['data', 'writeAuthorized'], ['data', 'writeAuthorization']
      ])

      return {
        fields: [
          { label: 'Connector', value: 'Online' },
          { label: 'Connector ID', value: connectorId },
          { label: 'Company', value: displayValue(responseCompany, companyId) },
          { label: 'Database', value: displayValue(database) },
          { label: 'SQL Server', value: displayValue(sqlServer) },
          { label: 'Connector version', value: displayValue(connectorVersion) },
          { label: 'Update', value: updateRequired === true ? 'Required' : updateRequired === false ? 'Up to date' : 'Unknown' },
          { label: 'Write authorization', value: displayValue(writeAuthorized, 'Unknown') }
        ],
        ok: true,
        summary: 'AutoCount Cloud and the Local Connector are responding.',
        title: 'AutoCount connected'
      }
    } catch (error) {
      return failedCheck(
        'AutoCount Cloud is not reachable',
        'The connection test could not reach AutoCount Cloud.',
        'Check the Cloud URL and network connection, then try again.',
        error instanceof Error && error.name === 'AbortError' ? 'Request timed out' : 'Connection failed'
      )
    }
  }
}

export { DEFAULT_AI_SERVICE_PORT, DEFAULT_SERVER_PORT }
