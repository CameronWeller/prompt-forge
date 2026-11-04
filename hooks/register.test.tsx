import { expect, test } from 'claude-code/testing'

const BRIEF = 'OUTCOME: Ship the invite flow.\nWHY: teammates join.\nDO: build it.'
const ORIGINAL = 'ship the invite flow so teammates can join'
const LARGE = 'word '.repeat(60).trim()
const COMPOSER = { kind: 'composer' }

function stubs(on: any, appended: any[], complete: any = () => ({ value: { isAnswered: true, text: BRIEF } }), sent: string[] = [], logs: string[] = [], turns = 0) {
  const kept = new Map<string, unknown>()
  on('store.set', (_: any, e: any) => (kept.set(e.key, e.value), { value: undefined }))
  on('store.get', (_: any, e: any) => ({ value: kept.get(e.key) }))
  on('store.keys', () => ({ value: [...kept.keys()] }))
  on('store.delete', (_: any, e: any) => (kept.delete(e.key), { value: undefined }))
  on('session.turns', () => ({ value: turns }))
  on('model.complete', complete)
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.log', (_: any, e: any) => (logs.push(e.text), { value: undefined }))
  on('clock.after', () => ({ value: {} }))
  on('prompt.submit', (_: any, e: any) => (sent.push(e.text), { ...e }))
  on('session.append', (_: any, e: any, next: any) => (appended.push(e), next(e)))
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{`> ${e.props.text}`}</Text>
  })
}

const submit = ($: any, text: string, origin: unknown = COMPOSER, extra = {}) =>
  $.prompt.submit({ text, origin, ...extra } as any)

test('a forged prompt is held, and its original words are kept as a notice', async ($, on) => {
  const appended: any[] = []
  stubs(on, appended)
  const r: any = await submit($, ORIGINAL)
  expect(r.drop).toContain('the forged version follows')
  const notes = appended.filter(e => e.message.type === 'system').map(e => e.message.content[0].text)
  expect(notes.some(n => n.includes('your original prompt') && n.includes(ORIGINAL))).toBe(true)
})

test('the resent brief is not forged again', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  await submit($, `${BRIEF} ${LARGE}`, { kind: 'plugin', name: 'prompt-forge', asUser: true })
  expect(forged).toBe(0)
})

// Every origin the engine stamps on something the person did not personally submit.
for (const origin of [
  { kind: 'sdk' },
  { kind: 'task-notification' },
  { kind: 'scheduled-trigger' },
  { kind: 'peer' },
  { kind: 'peer-send-message' },
  { kind: 'projects-relay' },
  { kind: 'channel', server: 'chat' },
  { kind: 'coordinator' },
  { kind: 'observer' },
  { kind: 'observer-activity' },
  { kind: 'auto-continuation' },
  { kind: 'unclassified' },
  { kind: 'plugin', name: 'another-plugin', asUser: true },
]) {
  test(`a large prompt from ${origin.kind} goes through untouched, with no model call`, async ($, on) => {
    const appended: any[] = []
    let forged = 0
    stubs(on, appended, () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
    const r: any = await submit($, LARGE, origin)
    expect(forged).toBe(0)
    expect(r.drop).toBeUndefined()
    expect(r.text).toBe(LARGE)
    expect(appended.length).toBe(0)
  })
}

for (const origin of [COMPOSER, { kind: 'bridge' }, { kind: 'slack-ping' }]) {
  test(`a prompt the person sent through ${origin.kind} is forged`, async ($, on) => {
    stubs(on, [])
    const r: any = await submit($, LARGE, origin)
    expect(r.drop).toContain('the forged version follows')
  })
}

test('a large agent brief reaches the agent exactly as the model wrote it, with no model call', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  let seen = ''
  on('agent.spawn', (_: any, e: any) => ((seen = e.prompt), { model: 'haiku' }))
  await $.agent.spawn({ prompt: LARGE, description: 'test' } as any)
  expect(forged).toBe(0)
  expect(seen).toBe(LARGE)
})

test('a typed prompt the desktop app attached a reminder to is forged, and the reminder stays intact', async ($, on) => {
  const REMINDER = '<system-reminder>\nLinked sessions now: none\n</system-reminder>\n'
  const prompts: string[] = []
  const sent: string[] = []
  stubs(on, [], (_: any, e: any) => (prompts.push(e.prompt), { value: { isAnswered: true, text: BRIEF } }), sent)
  // With an attachment the prompt is forged inline, so what reaches the agent is visible here.
  await submit($, REMINDER + ORIGINAL, COMPOSER, { attachments: [] })
  expect(prompts).toEqual([ORIGINAL])
  expect(sent).toEqual([REMINDER + BRIEF])
})

test('a short reminder-carrying follow-up counts only the words the person typed', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: BRIEF } }), [], [], 3)
  const text = `<system-reminder>${' status'.repeat(80)}</system-reminder>\nMerge and restart`
  const r: any = await submit($, text)
  expect(forged).toBe(0)
  expect(r.text).toBe(text)
})

test('a bash-mode line typed in the app is not forged', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  const text = `<bash-input>echo ${LARGE}</bash-input>`
  const r: any = await submit($, text)
  expect(forged).toBe(0)
  expect(r.text).toBe(text)
})

test('a transient API error is retried once', async ($, on) => {
  let calls = 0
  const sent: string[] = []
  stubs(on, [], () => {
    calls++
    return { value: calls === 1 ? { isAnswered: false, reason: 'api-error', status: 529 } : { isAnswered: true, text: BRIEF } }
  }, sent)
  await submit($, ORIGINAL, COMPOSER, { attachments: [] })
  expect(calls).toBe(2)
  expect(sent).toEqual([BRIEF])
})

test('a prompt too large to forge goes through as typed', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: BRIEF } }))
  const big = 'word '.repeat(6000).trim()
  const r: any = await submit($, big)
  expect(forged).toBe(0)
  expect(r.drop).toBeUndefined()
})

test('a simple request the model passes goes through exactly as typed', async ($, on) => {
  const sent: string[] = []
  stubs(on, [], () => ({ value: { isAnswered: true, text: 'PASS\n' } }), sent)
  // With an attachment the prompt is judged inline, so the passed text is visible here.
  const r: any = await submit($, ORIGINAL, COMPOSER, { attachments: [] })
  expect(r.drop).toBeUndefined()
  expect(sent).toEqual([ORIGINAL])
})

test('the simple-request gate applies to typed prompts but not to forge:', async ($, on) => {
  const systems: string[] = []
  stubs(on, [], (_: any, e: any) => (systems.push(e.system), { value: { isAnswered: true, text: BRIEF } }))
  await submit($, ORIGINAL, COMPOSER, { attachments: [] })
  await submit($, `forge: ${ORIGINAL}`, COMPOSER, { attachments: [] })
  expect(systems.map(s => s.includes('output exactly PASS'))).toEqual([true, false])
})

test('each decision is logged to the debug log with its reason and origin, never the prompt', async ($, on) => {
  const logs: string[] = []
  stubs(on, [], undefined, [], logs)
  await submit($, ORIGINAL)
  await submit($, LARGE, { kind: 'peer' })
  const decisions = logs.filter(l => l.startsWith('prompt-forge decision'))
  expect(decisions).toEqual([
    'prompt-forge decision: forge (first prompt) origin=composer',
    'prompt-forge decision: skip (not sent by the person) origin=peer',
  ])
})

test('a /goal run by anything but the person is left alone', async ($, on) => {
  let forged = 0
  stubs(on, [], () => (forged++, { value: { isAnswered: true, text: 'the condition' } }))
  let seen = ''
  on('command.run', (_: any, e: any) => ((seen = e.args), { text: '' }))
  // A plugin's own $.command.run is the non-person origin the test can raise.
  await $.command.run({ command: 'goal', args: ORIGINAL } as any)
  expect(forged).toBe(0)
  expect(seen).toBe(ORIGINAL)
})

test('a typed prompt that opens with a path is forged, not mistaken for a slash command', async ($, on) => {
  stubs(on, [])
  const r: any = await submit($, '/home/me/x/foo.ts is broken and needs a look')
  expect(r.drop).toContain('the forged version follows')
})

test('if the forge call throws, the prompt still goes through, without its prefix', async ($, on) => {
  const sent: string[] = []
  stubs(on, [], () => { throw new Error('boom') }, sent)
  await submit($, `forge: ${ORIGINAL}`, COMPOSER, { attachments: [] })
  expect(sent).toEqual([ORIGINAL])
})

test('text above a //PROMPT FORGE: line reaches the agent byte for byte, and only the request is checked for tokens', async ($, on) => {
  const MATERIAL = 'TASK. Read /practice/a.jsonl and   keep   this spacing.\n//PROMPT FORGE: DO NOT EDIT ANYTHING ABOVE THIS LINE.'
  const sent: string[] = []
  const prompts: string[] = []
  stubs(on, [], (_: any, e: any) => (prompts.push(e.prompt), { value: { isAnswered: true, text: BRIEF } }), sent)
  await submit($, `${MATERIAL}\nuse it as a model for /work/new.md`, COMPOSER, { attachments: [] })
  expect(prompts[0]).toContain(MATERIAL)
  expect(sent[0]).toContain(`unchanged; do not edit it):\n${MATERIAL}`)
  const kept = sent[0].slice(0, sent[0].indexOf('MATERIAL ('))
  expect(kept).toContain('- /work/new.md')
  expect(kept).not.toContain('/practice/a.jsonl')
})

test('a prompt with no marker carries no MATERIAL section', async ($, on) => {
  const sent: string[] = []
  stubs(on, [], undefined, sent)
  await submit($, ORIGINAL, COMPOSER, { attachments: [] })
  expect(sent).toEqual([BRIEF])
})
