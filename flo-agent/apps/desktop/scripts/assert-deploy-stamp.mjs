import { readFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

export function validateDeployStamp({ stamp, head, canonicalHead, trackedChanges }) {
  if (!stamp || stamp.schemaVersion !== 1 || typeof stamp.commit !== 'string') {
    return 'missing or invalid install-stamp.json'
  }
  if (stamp.dirty !== false) {
    return 'build stamp is marked dirty'
  }
  if (!head || stamp.commit !== head) {
    return `build commit ${stamp.commit} does not match source HEAD ${head || '(unavailable)'}`
  }
  if (!canonicalHead || head !== canonicalHead) {
    return `source HEAD ${head} does not match origin/flo/codex-polish ${canonicalHead || '(unavailable)'}`
  }
  if (trackedChanges) {
    return 'source worktree has tracked modifications'
  }
  return null
}

function git(repoRoot, ...args) {
  return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
}

function main(argv = process.argv.slice(2)) {
  const sourceIndex = argv.indexOf('--source-dir')
  const repoIndex = argv.indexOf('--repo-root')
  const sourceDir = sourceIndex >= 0 ? argv[sourceIndex + 1] : null
  const repoRoot = repoIndex >= 0 ? argv[repoIndex + 1] : null
  if (!sourceDir || !repoRoot) {
    console.error('Usage: node assert-deploy-stamp.mjs --source-dir <win-unpacked> --repo-root <git-root>')
    return 2
  }

  let stamp
  try {
    stamp = JSON.parse(readFileSync(join(resolve(sourceDir), 'resources', 'install-stamp.json'), 'utf8'))
  } catch (error) {
    console.error(`[deploy-stamp] cannot read package stamp: ${error.message}`)
    return 1
  }

  let head
  let canonicalHead
  let trackedChanges
  try {
    head = git(repoRoot, 'rev-parse', 'HEAD')
    canonicalHead = git(repoRoot, 'rev-parse', 'origin/flo/codex-polish')
    trackedChanges = Boolean(git(repoRoot, 'status', '--porcelain', '-uno'))
  } catch (error) {
    console.error(`[deploy-stamp] cannot verify canonical source revision: ${error.message}`)
    return 1
  }

  const problem = validateDeployStamp({ stamp, head, canonicalHead, trackedChanges })
  if (problem) {
    console.error(`[deploy-stamp] HARD STOP: ${problem}`)
    return 1
  }

  console.log(`[deploy-stamp] verified ${stamp.commit} from clean canonical source`)
  return 0
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : ''
if (invokedPath === fileURLToPath(import.meta.url)) {
  process.exitCode = main()
}
