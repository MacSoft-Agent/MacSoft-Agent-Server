import { execFile } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

import type { MacSoftProductPaths } from './macsoft-product'

const INITIALIZATION_TIMEOUT_MS = 120_000

export interface MacSoftProductInitializationResult {
  firstRun: boolean
  initialized: true
}

interface InitializerProcessOptions {
  cwd: string
  env: NodeJS.ProcessEnv
  timeout: number
  windowsHide: boolean
}

export type InitializerProcessRunner = (
  executable: string,
  args: string[],
  options: InitializerProcessOptions
) => Promise<void>

function defaultProcessRunner(
  executable: string,
  args: string[],
  options: InitializerProcessOptions
): Promise<void> {
  return new Promise((resolve, reject) => {
    execFile(executable, args, { ...options, maxBuffer: 256 * 1024 }, error => {
      if (error) {
        reject(error)
        return
      }
      resolve()
    })
  })
}

function initializerEnvironment(): NodeJS.ProcessEnv {
  return {
    PATHEXT: process.env.PATHEXT,
    SystemRoot: process.env.SystemRoot,
    TEMP: process.env.TEMP,
    TMP: process.env.TMP,
    WINDIR: process.env.WINDIR,
    PYTHONNOUSERSITE: '1'
  }
}

export function initializationMarker(paths: MacSoftProductPaths): string {
  return path.join(paths.configRoot, 'initialization.json')
}

export function requiredInitializedFiles(paths: MacSoftProductPaths): string[] {
  return [
    paths.dataRoot,
    paths.serverDataRoot,
    paths.configRoot,
    paths.logsRoot,
    paths.backupRoot,
    path.dirname(paths.hostControlFile),
    paths.runtimeRoot,
    initializationMarker(paths),
    paths.serverConfig,
    path.join(paths.serverDataRoot, 'data', 'macsoft-server.db'),
    path.join(paths.runtimeRoot, 'config.yaml'),
    path.join(paths.runtimeRoot, 'plugins', 'macsoft-autocount', 'config.json')
  ]
}

export async function initializePackagedProductData(
  paths: MacSoftProductPaths,
  runProcess: InitializerProcessRunner = defaultProcessRunner
): Promise<MacSoftProductInitializationResult> {
  if (paths.development) {
    return { firstRun: false, initialized: true }
  }

  const marker = initializationMarker(paths)
  const firstRun = !fs.existsSync(marker)
  const executable = path.join(paths.programRoot, 'python', 'python.exe')

  if (!fs.existsSync(executable)) {
    throw new Error('MacSoft Agent product initialization is unavailable because the bundled runtime is missing.')
  }

  try {
    await runProcess(
      executable,
      [
        '-m',
        'macsoft_runtime',
        '--mode',
        'packaged',
        '--program-root',
        paths.programRoot,
        '--data-root',
        paths.dataRoot,
        '--initialize-only'
      ],
      {
        cwd: paths.programRoot,
        env: initializerEnvironment(),
        timeout: INITIALIZATION_TIMEOUT_MS,
        windowsHide: true
      }
    )
  } catch {
    throw new Error('MacSoft Agent could not initialize its product data. Check folder permissions and try again.')
  }

  const missing = requiredInitializedFiles(paths).filter(filePath => !fs.existsSync(filePath))
  if (missing.length > 0) {
    throw new Error('MacSoft Agent product initialization did not create all required configuration files.')
  }

  return { firstRun, initialized: true }
}
