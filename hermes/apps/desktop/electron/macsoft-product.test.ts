import assert from 'node:assert/strict'
import { createPublicKey } from 'node:crypto'
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
  const source = JSON.parse(fs.readFileSync(path.join(root, 'product.json'), 'utf8'))
  const paths = resolveMacSoftProductPaths({ packaged: false, configuredProgramRoot: root })
  const metadata = loadMacSoftProductMetadata(paths)
  assert.equal(metadata.product, 'MacSoft Agent')
  assert.equal(source.product_version, '0.1.4')
  assert.equal(source.build_id, 'macsoft-agent-0.1.4-stable.20260803.1')
  assert.equal(source.runtime_base_version, 'v2026.7.7.2')
  assert.equal(source.runtime_base_commit, '79f12748022817a7c4f3fee747e45e9e6979214a')
  assert.equal(source.data_schema_version, 1)
  assert.equal(metadata.product_version, source.product_version)
  assert.equal(metadata.build_id, source.build_id)
  assert.equal(metadata.runtime_contract_version, 1)
  assert.equal(metadata.runtime_metadata_schema_version, 1)
  assert.equal(
    metadata.update_manifest_url,
    'https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/latest/download/macsoft-agent-stable-manifest-v1.json'
  )
  assert.equal(
    metadata.update_manifest_public_key,
    'MCowBQYDK2VwAyEANuklnSpzDv32q5qf+JtDKlIOD1hvADK0GX9yo5cgddg='
  )
  const publicKey = createPublicKey({ key: Buffer.from(metadata.update_manifest_public_key, 'base64'), format: 'der', type: 'spki' })
  assert.equal(publicKey.asymmetricKeyType, 'ed25519')
})

test('packaged runtime home is ProgramData and never LocalAppData', () => {
  const home = resolvePackagedRuntimeHome(null, 'D:\\ProgramData')
  assert.equal(home, path.resolve('D:\\ProgramData', 'MacSoft Agent', 'runtime'))
  assert.doesNotMatch(home, /localappdata|\\hermes$/i)
})
