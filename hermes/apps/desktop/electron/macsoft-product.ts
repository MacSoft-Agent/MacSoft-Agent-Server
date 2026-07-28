import fs from 'node:fs'
import path from 'node:path'

export interface MacSoftProductMetadata {
  build_date: string
  build_id: string
  channel: string
  data_schema_version: number
  product: 'MacSoft Agent'
  product_version: string
  protected_resource_version: number
  runtime_base_commit: string
  runtime_base_version: string
  runtime_contract_version: number
  runtime_metadata_schema_version: number
  update_manifest_url: null | string
}

export interface MacSoftProductPaths {
  backupRoot: string
  configRoot: string
  dataRoot: string
  development: boolean
  hostControlFile: string
  logsRoot: string
  programRoot: string
  runtimeRoot: string
  serverConfig: string
  serverDataRoot: string
  templatesRoot: string
}

interface ResolveOptions {
  configuredDataRoot?: null | string
  configuredProgramRoot?: null | string
  packaged: boolean
  programData?: null | string
  resourcesPath?: null | string
  sourceRepoRoot?: null | string
}

function existingProductRoot(candidate: null | string | undefined): string | null {
  if (!candidate) return null
  const resolved = path.resolve(candidate)
  return fs.existsSync(path.join(resolved, 'product.json')) ? resolved : null
}

export function resolveMacSoftProductPaths(options: ResolveOptions): MacSoftProductPaths {
  if (!options.packaged) {
    const root =
      existingProductRoot(options.configuredProgramRoot) ||
      existingProductRoot(options.sourceRepoRoot && path.basename(options.sourceRepoRoot).toLowerCase() === 'hermes'
        ? path.dirname(options.sourceRepoRoot)
        : options.sourceRepoRoot)
    if (!root) throw new Error('MacSoft Agent development root could not be located.')
    return {
      backupRoot: path.join(root, 'backup'),
      configRoot: path.join(root, 'server'),
      dataRoot: root,
      development: true,
      hostControlFile: path.join(root, 'server', 'data', 'host', 'host-control.json'),
      logsRoot: path.join(root, 'logs'),
      programRoot: root,
      runtimeRoot: path.join(root, 'runtime'),
      serverConfig: path.join(root, 'server', 'macsoft-server.yaml'),
      serverDataRoot: path.join(root, 'server'),
      templatesRoot: path.join(root, 'packaging', 'templates')
    }
  }

  const inferredProgramRoot = options.resourcesPath
    ? path.resolve(options.resourcesPath, '..', '..')
    : null
  const programRoot = path.resolve(options.configuredProgramRoot || inferredProgramRoot || 'C:\\Program Files\\MacSoft Agent')
  const dataRoot = path.resolve(
    options.configuredDataRoot || path.join(options.programData || 'C:\\ProgramData', 'MacSoft Agent')
  )
  return {
    backupRoot: path.join(dataRoot, 'backup'),
    configRoot: path.join(dataRoot, 'config'),
    dataRoot,
    development: false,
    hostControlFile: path.join(dataRoot, 'config', 'host', 'host-control.json'),
    logsRoot: path.join(dataRoot, 'logs'),
    programRoot,
    runtimeRoot: path.join(dataRoot, 'runtime'),
    serverConfig: path.join(dataRoot, 'server', 'macsoft-server.yaml'),
    serverDataRoot: path.join(dataRoot, 'server'),
    templatesRoot: path.join(programRoot, 'templates')
  }
}

export function resolvePackagedRuntimeHome(configuredDataRoot?: null | string, programData?: null | string): string {
  return path.join(
    path.resolve(configuredDataRoot || path.join(programData || 'C:\\ProgramData', 'MacSoft Agent')),
    'runtime'
  )
}

export function loadMacSoftProductMetadata(paths: MacSoftProductPaths, resourcesPath?: string): MacSoftProductMetadata {
  const candidates = [
    resourcesPath ? path.join(resourcesPath, 'product.json') : null,
    path.join(paths.programRoot, 'product.json')
  ].filter((candidate): candidate is string => Boolean(candidate))
  for (const candidate of candidates) {
    try {
      const value = JSON.parse(fs.readFileSync(candidate, 'utf8')) as MacSoftProductMetadata
      if (value.product === 'MacSoft Agent' && typeof value.product_version === 'string') return value
    } catch {
      continue
    }
  }
  throw new Error('MacSoft Agent product metadata is unavailable.')
}
