import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const store = path.join(root, 'frontend', 'node_modules', '.pnpm')
const packages = new Map()
function read(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue
    const location = path.join(dir, entry.name)
    if (entry.name.startsWith('@')) { read(location); continue }
    const manifest = path.join(location, 'package.json')
    if (!fs.existsSync(manifest)) continue
    const pkg = JSON.parse(fs.readFileSync(manifest, 'utf8'))
    if (pkg.name && pkg.version) packages.set(`${pkg.name}@${pkg.version}`, { ...pkg, location })
  }
}
for (const entry of fs.readdirSync(store, { withFileTypes: true })) {
  const modules = path.join(store, entry.name, 'node_modules')
  if (entry.isDirectory() && fs.existsSync(modules)) read(modules)
}
const all = [...packages.values()].sort((a, b) => a.name.localeCompare(b.name))
fs.mkdirSync(path.join(root, 'notices'), { recursive: true })
const rows = all.map(pkg => `| ${pkg.name} | ${pkg.version} | ${typeof pkg.license === 'string' ? pkg.license : JSON.stringify(pkg.license) || 'See package LICENSE'} |`)
fs.writeFileSync(path.join(root, 'notices/frontend-dependencies.md'), '# Installed frontend dependencies\n\nGenerated from the installed pnpm tree (including build/type dependencies and platform-specific packages).\n\n| Package | Version | Declared license |\n| --- | --- | --- |\n' + rows.join('\n') + '\n')
const texts = []
for (const pkg of all) {
  for (const filename of fs.readdirSync(pkg.location)) {
    if (!/^(license|licence|copying|notice)([.\-_]|$)/i.test(filename)) continue
    const file = path.join(pkg.location, filename)
    if (fs.statSync(file).isFile()) texts.push(`\n${'='.repeat(72)}\n${pkg.name}@${pkg.version} — ${filename}\n${'='.repeat(72)}\n${fs.readFileSync(file, 'utf8')}`)
  }
}
fs.writeFileSync(path.join(root, 'notices/frontend-licenses.txt'), texts.join('\n'))
fs.writeFileSync(path.join(root, 'frontend/public/THIRD_PARTY_LICENSES.txt'), texts.join('\n'))
console.log(`Exported metadata for ${all.length} frontend packages and ${texts.length} license files.`)
