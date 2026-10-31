import type { Register } from 'claude-code'

// prompt-forge cannot answer a command it runs itself, so this companion answers it. Command
// output is drawn by every client (the desktop app included) as its own chat row.
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'forged', description: 'prompt-forge: show a forged prompt (run by prompt-forge)' })
    return next(e)
  })
  on('command.run', { command: 'forged' }, async ($, e) => ({
    text: e.args.trim() === '' ? 'prompt-forge: nothing to show.' : e.args,
  }))
}
