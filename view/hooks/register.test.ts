import { expect, test } from 'claude-code/testing'

test('/forged prints exactly the text it is given', async ($, on) => {
  on('command.register', () => ({ value: { command: 'forged' } }))
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const text = 'OUTCOME: keep <b>this</b> as text\n\nWHY: line two'
  const r: any = await $.command.run({ command: 'forged', args: text })
  expect(r.text).toBe(text)
})
