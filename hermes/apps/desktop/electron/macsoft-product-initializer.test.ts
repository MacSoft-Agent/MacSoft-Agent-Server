import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import type { MacSoftProductPaths } from './macsoft-product'
import { initializePackagedProductData, type InitializerProcessRunner } from './macsoft-product-initializer'

function productPaths(root: string): MacSoftProductPaths {
  const programRoot = path.join(root, 'program')
  const dataRoot = path.join(root, 'data')
  fs.mkdirSync(path.join(programRoot, 'python'), { recursive: true })
  fs.writeFileSync(path.join(programRoot, 'python', 'python.exe'), '')

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

function initializeFiles(paths: MacSoftProductPaths): void {
  fs.mkdirSync(paths.configRoot, { recursive: true })
  fs.mkdirSync(paths.logsRoot, { recursive: true })
  fs.mkdirSync(paths.backupRoot, { recursive: true })
  fs.mkdirSync(path.dirname(paths.hostControlFile), { recursive: true })
  fs.mkdirSync(path.dirname(paths.serverConfig), { recursive: true })
  fs.mkdirSync(path.join(paths.serverDataRoot, 'data'), { recursive: true })
  fs.mkdirSync(paths.runtimeRoot, { recursive: true })
  fs.mkdirSync(path.join(paths.runtimeRoot, 'plugins', 'macsoft-autocount'), { recursive: true })
  fs.writeFileSync(path.join(paths.configRoot, 'initialization.json'), '{}')
  fs.writeFileSync(paths.serverConfig, 'server:\n  port: 8787\n')
  fs.writeFileSync(path.join(paths.serverDataRoot, 'data', 'macsoft-server.db'), '')
  fs.writeFileSync(path.join(paths.runtimeRoot, 'config.yaml'), 'platforms: {}\n')
  fs.writeFileSync(path.join(paths.runtimeRoot, 'plugins', 'macsoft-autocount', 'config.json'), '{}\n')
}

test('packaged initialization invokes the authoritative product runtime for an empty data root', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-initializer-'))
  t.after(() => fs.rmSync(root, { force: true, recursive: true }))
  const paths = productPaths(root)
  let invocation: Parameters<InitializerProcessRunner> | null = null
  const runner: InitializerProcessRunner = async (...args) => {
    invocation = args
    initializeFiles(paths)
  }

  const result = await initializePackagedProductData(paths, runner)

  assert.equal(result.firstRun, true)
  assert.ok(invocation)
  assert.equal(invocation[0], path.join(paths.programRoot, 'python', 'python.exe'))
  assert.deepEqual(invocation[1], [
    '-m',
    'macsoft_runtime',
    '--mode',
    'packaged',
    '--program-root',
    paths.programRoot,
    '--data-root',
    paths.dataRoot,
    '--initialize-only'
  ])
  assert.equal(invocation[2].cwd, paths.programRoot)
  assert.equal(invocation[2].env.HERMES_HOME, undefined)
  assert.equal(fs.existsSync(path.join(paths.serverDataRoot, 'data', 'macsoft-server.db')), true)
})

test('an initialized data root is not marked as first run and customized configuration remains untouched', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-initializer-'))
  t.after(() => fs.rmSync(root, { force: true, recursive: true }))
  const paths = productPaths(root)
  initializeFiles(paths)
  const customized = 'server:\n  port: 9988 # administrator value\n'
  fs.writeFileSync(paths.serverConfig, customized)

  const result = await initializePackagedProductData(paths, async () => undefined)

  assert.equal(result.firstRun, false)
  assert.equal(fs.readFileSync(paths.serverConfig, 'utf8'), customized)
})

test('initialization failures are sanitized for the renderer', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-initializer-'))
  t.after(() => fs.rmSync(root, { force: true, recursive: true }))
  const paths = productPaths(root)

  await assert.rejects(
    initializePackagedProductData(paths, async () => {
      throw new Error(`ENOENT C:\\developer\\secret\\config.yaml`)
    }),
    error => error instanceof Error && /could not initialize its product data/.test(error.message) && !/developer/.test(error.message)
  )
})
