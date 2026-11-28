import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import starlight from '@astrojs/starlight';
import { remarkRepositoryLinks } from './scripts/docs.mjs';

export default defineConfig({
  site: 'https://shrek-abaper.github.io',
  base: '/sap-watt',
  trailingSlash: 'always',
  markdown: { processor: unified({ remarkPlugins: [remarkRepositoryLinks] }) },
  integrations: [
    starlight({
      title: 'Watt',
      description: '面向 SAP 开发与交付团队的 AI 工程工具链。以受控操作、场景工作流和可追溯证据，支持分析、变更与交付。',
      defaultLocale: 'root',
      locales: { root: { label: '简体中文', lang: 'zh-CN' } },
      logo: { src: './src/assets/watt.svg', replacesTitle: false },
      favicon: '/favicon.svg',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/shrek-abaper/sap-watt' },
      ],
      customCss: ['./src/styles/docs.css'],
      editLink: { baseUrl: 'https://github.com/shrek-abaper/sap-watt/edit/main/website/' },
      sidebar: [
        {
          label: '开始使用',
          items: [
            { label: '选择你的第一条路径', slug: 'guides/getting-started' },
            { label: '能力与 Skills', slug: 'guides/capabilities' },
            { label: '设计理念与工程边界', slug: 'principles' },
          ],
        },
        { label: '安装与配置', items: [{ autogenerate: { directory: 'installation' } }] },
        {
          label: '接入 AI Agent',
          items: [
            { label: 'Claude Code', slug: 'agents/claude-code' },
            { label: 'WorkBuddy', slug: 'agents/workbuddy' },
            { label: 'Codex 与其他 Agent', slug: 'agents/generic-skills' },
          ],
        },
        {
          label: 'CLI 与工作流',
          items: [
            { label: '完整 CLI 清单', slug: 'reference/commands' },
            { label: '输出与错误契约', slug: 'reference/contracts' },
            { label: '工作流参考', items: [{ autogenerate: { directory: 'reference/workflows' } }] },
          ],
        },
      ],
    }),
  ],
});
