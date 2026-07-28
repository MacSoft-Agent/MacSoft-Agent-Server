import { createHash, createPrivateKey, createPublicKey, sign } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { readFile, stat, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const VERSION_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/
const SCRIPT_DIRECTORY = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = path.resolve(SCRIPT_DIRECTORY, '..')

function required(values, name) {
  const value = values.get(name)
  if (!value) throw new Error(`${name} is required.`)
  return value
}

export function parseArguments(argv) {
  const values = new Map()
  const allowed = new Set([
    '--installer',
    '--installer-url',
    '--output',
    '--private-key',
    '--product'
  ])
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index]
    const value = argv[index + 1]
    if (!name?.startsWith('--') || !value || value.startsWith('--')) {
      throw new Error('Arguments must be provided as --name value pairs.')
    }
    if (!allowed.has(name)) throw new Error(`Unknown argument: ${name}`)
    if (values.has(name)) throw new Error(`${name} was provided more than once.`)
    values.set(name, value)
  }
  return {
    installer: path.resolve(required(values, '--installer')),
    installerUrl: required(values, '--installer-url'),
    output: path.resolve(required(values, '--output')),
    privateKey: path.resolve(required(values, '--private-key')),
    product: path.resolve(values.get('--product') ?? path.join(PROJECT_ROOT, 'product.json'))
  }
}

function trustedHttpsUrl(value) {
  const parsed = new URL(value)
  if (
    parsed.protocol !== 'https:' ||
    parsed.username ||
    parsed.password ||
    parsed.hash ||
    parsed.toString() !== value
  ) {
    throw new Error('Installer URL must be normalized HTTPS without credentials or a fragment.')
  }
  return value
}

async function fileSha256(filePath) {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(filePath)) {
    hash.update(chunk)
  }
  return hash.digest('hex')
}

export async function buildManifest(options) {
  const product = JSON.parse(await readFile(options.product, 'utf8'))
  if (product.product !== 'MacSoft Agent') throw new Error('Product metadata identifies another product.')
  if (!VERSION_PATTERN.test(product.product_version)) {
    throw new Error('Product version must use strict major.minor.patch format.')
  }
  if (typeof product.channel !== 'string' || !product.channel.trim()) {
    throw new Error('Product channel is missing.')
  }
  if (typeof product.build_id !== 'string' || !product.build_id.trim()) {
    throw new Error('Product build ID is missing.')
  }

  const privateKey = createPrivateKey(await readFile(options.privateKey))
  if (privateKey.asymmetricKeyType !== 'ed25519') {
    throw new Error('Update manifest private key must be Ed25519.')
  }
  const installerStat = await stat(options.installer)
  const payload = Buffer.from(
    JSON.stringify({
      schema_version: 1,
      product: 'MacSoft Agent',
      channel: product.channel,
      version: product.product_version,
      build_id: product.build_id,
      published_at: new Date().toISOString(),
      installer: {
        url: trustedHttpsUrl(options.installerUrl),
        sha256: await fileSha256(options.installer),
        bytes: installerStat.size
      }
    })
  )
  const envelope = {
    envelope_version: 1,
    algorithm: 'ed25519',
    payload: payload.toString('base64'),
    signature: sign(null, payload, privateKey).toString('base64')
  }
  return {
    envelope,
    publicKeySpkiBase64: createPublicKey(privateKey)
      .export({ format: 'der', type: 'spki' })
      .toString('base64')
  }
}

async function main() {
  const options = parseArguments(process.argv.slice(2))
  const result = await buildManifest(options)
  await writeFile(options.output, `${JSON.stringify(result.envelope, null, 2)}\n`, {
    encoding: 'utf8',
    flag: 'wx'
  })
  process.stdout.write(
    `${JSON.stringify({
      manifest: options.output,
      update_manifest_public_key: result.publicKeySpkiBase64
    })}\n`
  )
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`)
    process.exitCode = 1
  })
}
