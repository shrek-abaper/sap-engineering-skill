import { readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = fileURLToPath(new URL('../../', import.meta.url));
export const docsRoot = path.join(root, 'website/src/content/docs');
export const base = '/sap-watt/';
export const repository = 'https://github.com/shrek-abaper/sap-watt';

export const documents = [
  ['installation/runtime', 'docs/installation/runtime-setup.md', '安装与运行准备'],
  ['installation/windows', 'docs/installation/windows.md', 'Windows 安装'],
  ['installation/npm', 'docs/installation/npm.md', 'npm 安装'],
  ['installation/python', 'docs/installation/python-source.md', 'Python 与源码安装'],
  ['installation/portable', 'docs/installation/portable.md', '便携运行时'],
  ['agents/claude-code', 'docs/agents/claude-code.md', 'Claude Code'],
  ['agents/generic-skills', 'docs/agents/generic-skills.md', 'Codex 与其他 Agent'],
  ['principles', 'docs/design-principles.md', '设计理念与工程边界'],
  ['reference/commands', 'skills/sap-adt-cli/SKILL.md', '完整 CLI 清单', 'Command index'],
  ['reference/contracts', 'skills/sap-adt-cli/SKILL.md', '输出与错误契约', 'contracts'],
  ...readdirSync(path.join(root, 'skills/sap-adt-cli/references'))
    .filter((name) => name.endsWith('.md') && name !== 'setup.md')
    .sort()
    .map((name) => [
      `reference/workflows/${name.slice(0, -3)}`,
      `skills/sap-adt-cli/references/${name}`,
      ({
        adt_api: 'ADT 端点与协议',
        credentials: '凭据与 keystore',
        profiles: '连接 Profiles',
        development: '受控开发与 RAP',
        'core-workflows': '开发、回归与执行工作流',
        executor: '原子执行器与交付证据',
        execution: '受控 ABAP 执行',
        debugging: '实验性调试',
        'diagnostics-history': '诊断、历史与差异',
        'test-failure-diagnosis': '测试失败诊断',
        examples: 'CLI 使用示例',
        updating: 'CLI 更新',
      })[name.slice(0, -3)] ?? name.slice(0, -3).replaceAll('-', ' '),
    ]),
];

const sourceRoutes = new Map(
  documents.filter(([, , , section]) => !section).map(([route, source]) => [source, route]),
);
sourceRoutes.set('skills/sap-adt-cli/references/setup.md', 'installation/runtime');

export function repositoryUrl(url, source) {
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(url)) return url;
  const [, pathname, suffix] = url.match(/^([^?#]*)(.*)$/s);
  if (!pathname) {
    if (source === 'skills/sap-adt-cli/SKILL.md') {
      return `${repository}/blob/main/${source}${url}`;
    }
    return url;
  }
  const target = path.posix.normalize(path.posix.join(path.posix.dirname(source), pathname));
  if (target === 'skills/sap-adt-cli/SKILL.md' && suffix === '#command-index') {
    return `${base}reference/commands/`;
  }
  const route = sourceRoutes.get(target);
  if (route) return `${base}${route}/${suffix}`;
  if (target.startsWith('../') || pathname.startsWith('/')) return url;
  return `${repository}/blob/main/${target}${suffix}`;
}

export function remarkRepositoryLinks() {
  return (tree, file) => {
    const relative = path.relative(docsRoot, file.path).split(path.sep).join('/').replace(/\.md$/, '');
    const document = documents.find(([route]) => route === relative);
    if (!document) return;
    const visit = (node) => {
      if (['link', 'image', 'definition'].includes(node.type)) {
        node.url = repositoryUrl(node.url, document[1]);
      }
      for (const child of node.children ?? []) visit(child);
    };
    visit(tree);
  };
}

export function extractSection(markdown, heading) {
  const lines = markdown.split('\n');
  const start = lines.indexOf(`## ${heading}`);
  if (start < 0) throw new Error(`Missing section: ${heading}`);
  const next = lines.findIndex((line, index) => index > start && line.startsWith('## '));
  return lines.slice(start + 1, next < 0 ? undefined : next).join('\n').trim();
}
