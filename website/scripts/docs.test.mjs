import assert from 'node:assert/strict';
import test from 'node:test';
import { extractSection, repository, repositoryUrl } from './docs.mjs';

test('repository documentation links retain the website base and anchors', () => {
  assert.equal(
    repositoryUrl('../installation/runtime-setup.md#watt-installation-and-migration-167', 'docs/agents/claude-code.md'),
    '/sap-watt/installation/runtime/#watt-installation-and-migration-167',
  );
  assert.equal(repositoryUrl('profiles.md', 'skills/sap-adt-cli/references/execution.md'),
    '/sap-watt/reference/workflows/profiles/');
  assert.equal(repositoryUrl('references/setup.md', 'skills/sap-adt-cli/SKILL.md'),
    '/sap-watt/installation/runtime/');
  assert.equal(repositoryUrl('profiles.md?source=docs#agent-rules', 'skills/sap-adt-cli/references/execution.md'),
    '/sap-watt/reference/workflows/profiles/?source=docs#agent-rules');
});

test('non-site resources resolve to their original repository locations', () => {
  assert.equal(repositoryUrl('../README.md', 'docs/design-principles.md'),
    `${repository}/blob/main/README.md`);
  assert.equal(repositoryUrl('diagnosis-report.schema.json', 'skills/sap-adt-cli/references/execution.md'),
    `${repository}/blob/main/skills/sap-adt-cli/references/diagnosis-report.schema.json`);
  assert.equal(repositoryUrl('https://example.com/doc#part', 'docs/design-principles.md'),
    'https://example.com/doc#part');
  assert.equal(repositoryUrl('#principles', 'docs/design-principles.md'), '#principles');
});

test('extracted command sections do not leave dangling same-page links', () => {
  assert.equal(repositoryUrl('#command-index', 'skills/sap-adt-cli/SKILL.md'),
    `${repository}/blob/main/skills/sap-adt-cli/SKILL.md#command-index`);
  assert.equal(repositoryUrl('../SKILL.md#command-index', 'skills/sap-adt-cli/references/execution.md'),
    '/sap-watt/reference/commands/');
  assert.equal(extractSection('# Title\n## Command index\ncommands\n### Nested\nmore\n## Next\nother', 'Command index'),
    'commands\n### Nested\nmore');
  assert.throws(() => extractSection('## Other\ntext', 'Command index'), /Missing section/);
});
