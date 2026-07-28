import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { loadMacSoftProductMetadata, resolveMacSoftProductPaths, resolvePackagedRuntimeHome } from './macsoft-product'

test('development and packaged paths use one explicit model', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-product-'))
  fs.writeFileSync(path.join(root, 'product.json'), JSON.stringify({ product: 'MacSoft Agent', product_version: '0.1.0' }))
  const development = resolveMacSoftProductPaths({ packaged: false, configuredProgramRoot: root })
  assert.equal(development.runtimeRoot, path.join(root, 'runtime'))
  assert.equal(development.serverDataRoot, path.join(root, 'server'))

  const packaged = resolveMacSoftProductPaths({
    packaged: true,
    configuredProgramRoot: path.join(root, 'Program'),
    configuredDataRoot: path.join(root, 'Data')
  })
  assert.equal(packaged.runtimeRoot, path.join(root, 'Data', 'runtime'))
  assert.equal(packaged.serverConfig, path.join(root, 'Data', 'server', 'macsoft-server.yaml'))
  assert.ok(!packaged.runtimeRoot.startsWith(packaged.programRoot))
})

test('authoritative metadata is loaded from the product root', () => {
  const root = path.resolve(import.meta.dirname, '..', '..', '..', '..')
  const paths = resolveMacSoftProductPaths({ packaged: false, configuredProgramRoot: root })
  const metadata = loadMacSoftProductMetadata(paths)
  assert.equal(metadata.product, 'MacSoft Agent')
  assert.equal(metadata.product_version, '0.1.0')
  assert.equal(metadata.runtime_contract_version, 1)
  assert.equal(metadata.runtime_metadata_schema_version, 1)
  assert.equal(metadata.update_manifest_url, null)
  assert.equal(metadata.update_manifest_public_key, null)
})

test('packaged runtime home is ProgramData and never LocalAppData', () => {
  const home = resolvePackagedRuntimeHome(null, 'D:\\ProgramData')
  assert.equal(home, path.resolve('D:\\ProgramData', 'MacSoft Agent', 'runtime'))
  assert.doesNotMatch(home, /localappdata|\\hermes$/i)
})
