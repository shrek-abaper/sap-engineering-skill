# Watt website

Astro + Starlight static product homepage and documentation. No SAP connection,
credential collection, backend or embedded LLM.

Requires Node.js 22.23.4+ (Node.js 24 LTS recommended) and Python 3 for the
built-link check. This is the website build requirement, not the CLI runtime
requirement.

```bash
cd website
npm ci
npm run dev
```

The local URL includes the project base: `http://localhost:4321/sap-watt/`.

```bash
npm test
npm run build
npm run check:links
npm run preview
```

## Content ownership

- `src/pages/index.astro` and `src/styles/home.css`: product homepage.
- `src/content/docs/guides/`: authored introductory pages.
- `scripts/docs.mjs`: curated source-to-route map and repository-link handling.
- `scripts/prepare-docs.mjs`: generates ignored documentation pages at build
  time from existing installation guides, engineering principles and CLI
  references. Edit the original files, not these generated pages.
- The complete CLI index and output/error contracts come from
  `skills/sap-adt-cli/SKILL.md`. Installation requirements come from the shared
  runtime guide and `compatibility.json`; the displayed CLI version comes from
  root `pyproject.toml`.
- Technical reference bodies retain their original language. Chinese navigation
  does not imply a complete Chinese translation.

Published documentation links stay on-site when the destination is included;
other repository files link back to GitHub. Historical development archives
and standalone archived Skill READMEs are not imported.

## Deployment

`.github/workflows/website.yml` checks pull requests and deploys relevant pushes
to `main` using GitHub Pages Actions. Enable Pages with **GitHub Actions** as
the source in repository Settings > Pages.

Canonical URL: `https://shrek-abaper.github.io/sap-watt/`.
No CLI package, runtime or plugin release is produced by this workflow.
