import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { documents, docsRoot, extractSection, repository, root } from './docs.mjs';

const project = await readFile(path.join(root, 'pyproject.toml'), 'utf8');
const cliVersion = project.match(/^version\s*=\s*"([^"]+)"/m)?.[1];
if (!cliVersion) throw new Error('Missing root CLI version');
await mkdir(path.join(root, 'website/.generated'), { recursive: true });
await writeFile(
  path.join(root, 'website/.generated/runtime.json'),
  JSON.stringify({ cliVersion }) + '\n',
);

for (const [route, source, title, section] of documents) {
  let body = await readFile(path.join(root, source), 'utf8');
  if (section === 'contracts') {
    const beforeCommands = body.slice(0, body.indexOf('\n## Command index'));
    const match = beforeCommands.match(/^## .*(?:[Oo]utput|[Rr]esponse).*$/m);
    if (!match) throw new Error('Missing output contract heading');
    body = beforeCommands.slice(match.index);
  } else if (section) {
    body = extractSection(body, section);
  } else {
    body = body.replace(/^# [^\n]+\n/, '');
  }
  const output = path.join(docsRoot, `${route}.md`);
  const editUrl = `${repository}/edit/main/${source}`;
  const frontmatter = [
    '---',
    `title: ${JSON.stringify(title)}`,
    `description: ${JSON.stringify(`Watt ${title}，来自项目维护的权威文档。`)}`,
    `editUrl: ${JSON.stringify(editUrl)}`,
    '---',
  ].join('\n');
  const note = `> 本页由[仓库原文](${repository}/blob/main/${source})构建生成。技术正文保留原文；版本要求、授权与限制以正文为准。\n`;
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, `${frontmatter}\n\n${note}\n${body.trim()}\n`);
}

console.log(`Prepared ${documents.length} source-backed documentation pages.`);
