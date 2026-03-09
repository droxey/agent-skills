---
id: "readme"
name: "README Improver"
description: "Analyse and improve a repository README following documentation best practices."
version: "0.1.0"
tags: ["documentation", "readme", "best-practices"]
inputs:
  - name: "readme_path"
    type: "string"
    description: "Path to the README file to improve."
    required: true
outputs:
  - name: "improved_readme"
    type: "string"
    description: "The improved README content."
verification: "Verify the improved README contains all required sections, renders correctly as Markdown, and preserves existing accurate information."
---

# README Improver

Analyse and improve a repository README so that it is clear, complete, and
follows widely-accepted documentation best practices.

## Best-Practice Checklist

When reviewing or writing a README, ensure it includes the following:

1. **Title & Description** — A top-level heading with the project name followed
   by a one- or two-sentence overview of what the project does.
2. **Badges** — CI status, version, license, and any other relevant status
   badges placed directly below the title.
3. **Table of Contents** — A linked table of contents for READMEs longer than
   three screen-lengths.
4. **Quick Start** — A short section showing the fastest path from zero to a
   working setup (install + first command).
5. **Installation** — Detailed installation instructions covering prerequisites
   and supported platforms.
6. **Usage / CLI Reference** — How to use the project, with concrete command
   examples and expected output.
7. **Configuration** — Environment variables, config files, or flags that alter
   behaviour.
8. **Architecture / Repository Layout** — A tree or description of the project
   structure to help newcomers orient themselves.
9. **Development** — How to set up a dev environment, run linters, and execute
   tests.
10. **Contributing** — Contribution guidelines or a link to CONTRIBUTING.md.
11. **License** — The project license or a link to the LICENSE file.

## Instructions

1. Read the target README carefully.
2. Walk through the Best-Practice Checklist above and note which items are
   missing or incomplete.
3. Preserve all existing accurate content — do not remove information that is
   correct and useful.
4. Add or improve sections to satisfy every checklist item.
5. Keep the tone consistent with the existing document.
6. Use Markdown best practices: fenced code blocks with language tags, tables
   where appropriate, and consistent heading hierarchy.

## Example

**Input:** A README that has installation instructions and a CLI reference but
is missing badges, a quick-start section, contributing guidelines, and a
license notice.

**Output:** The same README with the following additions:

- CI and license badges added below the title.
- A "Quick Start" section inserted before the detailed installation section.
- A "Contributing" section near the bottom.
- A "License" section at the very end.
