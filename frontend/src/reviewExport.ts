export function reviewMarkdown(date: string, content: string) {
  const body = content.trimEnd()
  if (!body.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null
  return {
    filename: `知己-每日回顾-${date}.md`,
    text: `# ${date} 每日回顾\n\n${body}\n`,
  }
}
