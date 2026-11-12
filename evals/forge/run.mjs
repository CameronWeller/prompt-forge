// The forge's own tuning loop: forge a fixed set of prompts with two versions of the forge's
// rules, have a model from a different family grade every brief, and say whether the new
// version may ship. Plain Node, no dependencies.
//
//   node evals/forge/run.mjs                        working tree vs HEAD, Codex as judge
//   node evals/forge/run.mjs --baseline v0.5.0      compare against a tag or commit
//   node evals/forge/run.mjs --judge claude         judge with Claude (Sonnet) when Codex is absent
//   node evals/forge/run.mjs --only 01,09 --split heldout
//
// A change may ship only if: no prompt gets a new hard failure (the gate called wrongly, or
// authority scored 0), and the mean score on the held-out prompts is not lower than baseline.
// Held-out prompts must never be used while editing the rules; that is what keeps them honest.
import { readFileSync, readdirSync, writeFileSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { execFileSync, spawn } from 'node:child_process'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..', '..')
export const CRITERIA = ['outcome', 'checkable', 'verify', 'loop', 'authority', 'assumptions', 'fidelity']
const SECTIONS = ['OUTCOME', 'VERIFY', 'STOP', 'BOUNDS', 'ASSUMPTIONS']

// ---- the forge's rules, read from register.tsx without running it ----
const LITERAL = /'((?:[^'\\\n]|\\.)*)'/g
export function extractPrompt(source, name) {
  const m = new RegExp(`const ${name} = \\[([\\s\\S]*?)\\]\\.join\\('\\\\n'\\)`).exec(source)
  if (m === null) throw new Error(`could not find ${name} in register.tsx`)
  if (m[1].replace(LITERAL, '').replace(/[\s,]/g, '') !== '') throw new Error(`${name} is not plain string lines`)
  return [...m[1].matchAll(LITERAL)].map(l => l[1].replace(/\\(.)/g, '$1')).join('\n')
}
export const forgeSystem = source => `${extractPrompt(source, 'FORGE_SYSTEM')}\n${extractPrompt(source, 'GATE')}`
const sourceAt = ref => ref === 'working'
  ? readFileSync(join(ROOT, 'hooks', 'register.tsx'), 'utf8')
  : execFileSync('git', ['-C', ROOT, 'show', `${ref}:hooks/register.tsx`], { encoding: 'utf8' })

// ---- the prompt set ----
export function parseCase(file, text) {
  const m = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/.exec(text)
  if (m === null) throw new Error(`${file}: missing front matter`)
  const meta = Object.fromEntries(m[1].split('\n').map(l => l.split(/:\s*/)).map(([k, v]) => [k, v === 'true' ? true : v]))
  return { id: file.replace(/\.md$/, ''), split: meta.split, expect: meta.expect, risky: meta.risky === true, prompt: m[2].trim() }
}
const loadCases = () => readdirSync(join(HERE, 'prompts')).filter(f => f.endsWith('.md')).sort()
  .map(f => parseCase(f, readFileSync(join(HERE, 'prompts', f), 'utf8')))

// ---- free, deterministic checks (dense signals beside the judge) ----
export function anchors(raw) {
  const found = new Set()
  const add = (re, g = 0) => { for (const m of raw.matchAll(re)) { const t = (m[g] ?? '').trim(); if (t.length >= 2 && t.length <= 160) found.add(t) } }
  add(/`([^`\n]+)`/g, 1); add(/"([^"\n]{2,120})"/g, 1); add(/https?:\/\/[^\s)>\]"']+/g)
  add(/(?:~|\.{0,2})\/[\w.@~-]+(?:\/[\w.@~-]+)+/g)
  add(/\b[\w-]+\.(?:ts|tsx|js|mjs|json|md|sh|py|nix|yml|yaml|toml|sql|txt|css|html|db|csv|env)\b/g)
  add(/\b[A-Za-z#-]*\d[\w#.:%-]*\b/g)
  return [...found]
}
export function checks(c, text) {
  const passed = text.trim() === 'PASS'
  const gateRight = (c.expect === 'pass') === passed
  const missingSections = passed ? [] : SECTIONS.filter(s => !new RegExp(`^\\s*${s}:`, 'm').test(text))
  const dropped = passed ? [] : anchors(c.prompt).filter(a => !text.includes(a))
  return { passed, gateRight, missingSections, dropped }
}

// ---- model calls: isolated, tool-less, no repo context ----
function run(bin, args, input, timeoutMs = 300_000) {
  const cwd = mkdtempSync(join(tmpdir(), 'forge-eval-'))
  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { cwd, env: { ...process.env, CLAUDE_CODE_DISABLE_AUTO_MEMORY: '1' } })
    let out = '', err = ''
    const timer = setTimeout(() => child.kill(), timeoutMs)
    child.stdout.on('data', d => { out += d }); child.stderr.on('data', d => { err += d })
    child.on('error', e => { clearTimeout(timer); reject(e) })
    child.on('close', code => {
      clearTimeout(timer)
      let last = ''
      try { last = readFileSync(join(cwd, 'last.txt'), 'utf8') } catch {}
      rmSync(cwd, { recursive: true, force: true })
      code === 0 ? resolve(last || out) : reject(new Error(`${bin} exited ${code}: ${err.trim().slice(0, 300)}`))
    })
    child.stdin.end(input)
  })
}
const claude = (system, prompt, model) => run('claude', ['-p', '--model', model, '--effort', 'high', '--tools', '',
  '--strict-mcp-config', '--setting-sources', '', '--exclude-dynamic-system-prompt-sections',
  '--no-session-persistence', '--output-format', 'text', '--system-prompt', system], prompt)
const forge = (system, prompt) => claude(system, prompt, 'opus')

const RUBRIC = readFileSync(join(HERE, 'rubric.md'), 'utf8')
const judgeInput = (c, brief) => `${RUBRIC}\n\nORIGINAL:\n<<<\n${c.prompt}\n>>>\n\nBRIEF:\n<<<\n${brief}\n>>>\n`
const JUDGES = {
  // A different model family from the forge, so the forge is never graded by itself.
  codex: input => run('codex', ['exec', '--skip-git-repo-check', '--sandbox', 'read-only', '--output-last-message', 'last.txt', '-'], input),
  // Fallback when Codex is not installed. Same family as the forge: say so in the report.
  claude: input => claude('You grade briefs strictly and reply with JSON only.', input, 'sonnet'),
}
export function parseScores(text) {
  const m = /\{[\s\S]*\}/.exec(text)
  if (m === null) throw new Error('judge reply has no JSON')
  const j = JSON.parse(m[0])
  for (const k of CRITERIA) if (![0, 1, 2].includes(j[k])) throw new Error(`judge score ${k} is not 0, 1 or 2`)
  return j
}

// ---- one version over all cases ----
async function evaluate(version, system, cases, judge) {
  const rows = []
  for (const c of cases) {
    let text
    try { text = (await forge(system, c.prompt)).trim() } catch (e) { text = `FORGE FAILED: ${e.message}` }
    const chk = checks(c, text)
    let scores = null
    if (!chk.passed && c.expect === 'brief') {
      try { scores = parseScores(await judge(judgeInput(c, text))) } catch (e) { scores = { error: e.message } }
    }
    const total = scores && !scores.error ? CRITERIA.reduce((s, k) => s + scores[k], 0) : null
    // A PASS on a simple prompt is the best possible answer: full marks.
    const score = c.expect === 'pass' ? (chk.gateRight ? CRITERIA.length * 2 : 0) : chk.gateRight ? total : 0
    const hard = [!chk.gateRight && 'gate called wrongly', scores?.authority === 0 && 'authority widened'].filter(Boolean)
    rows.push({ id: c.id, split: c.split, version, score, hard, checks: chk, scores, brief: text })
    console.error(`  ${version} ${c.id}: ${score ?? 'n/a'}${hard.length ? ` HARD: ${hard.join(', ')}` : ''}`)
  }
  return rows
}

// ---- the decision ----
export function decide(base, cand) {
  const max = CRITERIA.length * 2
  const by = rows => Object.fromEntries(rows.map(r => [r.id, r]))
  const B = by(base), C = by(cand)
  const ids = Object.keys(C).filter(id => B[id])
  const stats = split => {
    const d = ids.filter(id => C[id].split === split && B[id].score != null && C[id].score != null)
      .map(id => (C[id].score - B[id].score) / max)
    const mean = d.length ? d.reduce((a, b) => a + b, 0) / d.length : 0
    const se = d.length > 1 ? Math.sqrt(d.reduce((a, b) => a + (b - mean) ** 2, 0) / (d.length - 1) / d.length) : null
    return { n: d.length, meanDelta: mean, se }
  }
  const newHard = ids.flatMap(id => C[id].hard.filter(h => !B[id].hard.includes(h)).map(h => `${id}: ${h}`))
  const heldout = stats('heldout')
  const ship = newHard.length === 0 && heldout.n > 0 && heldout.meanDelta >= 0
  return { ship, newHard, train: stats('train'), heldout }
}

function report(baseRef, judgeName, decision, base, cand) {
  const pct = x => `${(x * 100).toFixed(1)} points`
  const se = s => s.se == null ? '' : ` (± ${(s.se * 100).toFixed(1)} standard error)`
  const lines = [
    `# Forge eval: working tree vs ${baseRef}`, '',
    `Judge: ${judgeName}${judgeName === 'claude' ? ' (same family as the forge; prefer Codex)' : ''}`, '',
    `**${decision.ship ? 'May ship' : 'Do not ship'}.** Held-out change: ${pct(decision.heldout.meanDelta)}${se(decision.heldout)} over ${decision.heldout.n} prompts. Training change: ${pct(decision.train.meanDelta)}${se(decision.train)} over ${decision.train.n}.`,
    decision.newHard.length ? `New hard failures: ${decision.newHard.join('; ')}` : 'No new hard failures.', '',
    '| Prompt | Split | Baseline | Candidate | Worst problem (candidate) |', '| --- | --- | --- | --- | --- |',
    ...cand.map(c => { const b = base.find(x => x.id === c.id)
      return `| ${c.id} | ${c.split} | ${b?.score ?? '-'} | ${c.score ?? '-'} | ${(c.scores?.worst ?? c.hard.join(', ') ?? '').replace(/\|/g, '/')} |` }),
    '', `Scores are out of ${CRITERIA.length * 2}. A simple prompt answered PASS gets full marks; a wrong gate call gets 0.`,
  ]
  return lines.join('\n') + '\n'
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const arg = (name, dflt) => { const i = process.argv.indexOf(`--${name}`); return i < 0 ? dflt : process.argv[i + 1] }
  const baseRef = arg('baseline', 'HEAD')
  const judgeName = arg('judge', 'codex')
  const only = arg('only')?.split(',')
  const split = arg('split')
  const judge = JUDGES[judgeName]
  if (!judge) { console.error(`unknown judge ${judgeName}`); process.exit(2) }
  const cases = loadCases().filter(c => (!only || only.some(o => c.id.startsWith(o))) && (!split || c.split === split))
  console.error(`Forging ${cases.length} prompts twice (${baseRef} and the working tree), judge: ${judgeName}`)
  const base = await evaluate(baseRef, forgeSystem(sourceAt(baseRef)), cases, judge)
  const cand = await evaluate('working', forgeSystem(sourceAt('working')), cases, judge)
  const decision = decide(base, cand)
  const out = join(HERE, 'results'); mkdirSync(out, { recursive: true })
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  writeFileSync(join(out, `${stamp}.json`), JSON.stringify({ baseRef, judge: judgeName, decision, base, cand }, null, 2))
  const md = report(baseRef, judgeName, decision, base, cand)
  writeFileSync(join(out, `${stamp}.md`), md)
  console.log(md)
  process.exit(decision.ship ? 0 : 1)
}
