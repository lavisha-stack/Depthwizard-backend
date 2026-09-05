# DepthWizard team guide — retained template contract

## Template provenance

- Selected template: `Experiment Analysis`
- Reference file: `C:/Users/preet/.codex/plugins/cache/openai-curated-remote/openai-templates/0.1.1/skills/artifact-template-experiment-analysis/assets/reference.docx`
- Reference SHA-256 before authoring: `D823CD0115186B34C01C6E4B4DA3BE28B64EE73CAC849DBD62D6F4BB6385B0FB`
- Reference size: 204,643 bytes
- The reference is read-only. The deliverable is created from a copied package, never by editing the reference in place.

## Retained visual DNA

- Letter portrait pages, one-inch margins, single-column editorial report layout.
- Georgia typography throughout.
- Dark green display headings and title accents; black body text.
- Small green document label and page number in the footer.
- Thin horizontal green rules as restrained visual anchors.
- Light-gray table headers and understated borders.
- Large, left-aligned section openers with generous white space.
- Minimal ornament: diagrams use the same green/gray/white palette and remain information-first.

## Audited reference evidence

- 1 section, 8.5 × 11 inch page size, 1 inch margins.
- Heading styles present and used; footer contains a PAGE field.
- 2 anchored horizontal-rule images are present in the package.
- No footnotes or endnotes.
- One footer content control stores the report label.
- The reference rendered to seven pages through Microsoft Word because LibreOffice is not installed in the environment.
- All seven reference pages were visually inspected. No clipping, overlap, broken fields, or malformed tables were observed.
- Machine-readable evidence: `template-style-evidence.json`; rendered evidence: `template-reference.pdf` and `template-reference-render/page-*.png` in this task-local temporary directory.

## Content replacement plan

The user requested a complete DepthWizard team technical and judge-preparation guide, not an experiment report. Therefore the reference body content is replaced in full while its page geometry, typography, palette, hierarchy, footer system, table grammar, and restrained rule motifs are preserved. The result must remain recognizably derived from the selected template rather than becoming a generic blank document.

Planned sections:

1. Cover, document control, and table of contents.
2. Executive summary, problem definition, why it matters, and conceptual foundations.
3. Intended architecture versus the implementation verified in the repository.
4. Six major person chapters, each covering role, inputs, internal workflow, outputs, interfaces, limitations, judge questions, and a 30-second explanation.
5. End-to-end integration, data contracts, validation strategy, limitations, demo runbook, and troubleshooting.
6. Forty possible judge questions with suggested answers.
7. Six person-specific revision cheat sheets, each with a 30-second and two-minute explanation.
8. Glossary, verified build status, references, and file map.

## Grounding and honesty rules

- Describe the current default model as `depth-anything/Depth-Anything-V2-Base-hf` and its output as relative inverse-depth/disparity-like values, not metres.
- Absolute DSM output is only claimed when trustworthy GeoTIFF georeferencing and SRTM and/or GCP calibration are supplied.
- SRTM and GCP support are implemented locally; SRTM is not downloaded by the application.
- Non-georeferenced or uncalibrated jobs remain relative and must be labelled `rel`.
- The viewer’s smoothing and relief controls are display-only; the point HUD samples the unmodified field.
- The project is a hackathon prototype, not survey-grade photogrammetry, LiDAR replacement, or operational disaster/defence software.
- As verified on 5 September 2026: 32 automated tests passed (4 + 5 + 7 + 8 + 8) and the Vite production build completed successfully. Warnings are documented as dependency deprecations, not test failures.

## Rendering and quality requirements

- Build an editable DOCX by cloning the reference package, then export the final PDF through Word.
- Update the table of contents and all fields before export.
- Render the complete PDF to PNG pages and inspect every page.
- Run DOCX structural validation, PDF page-count/text checks, and reference-hash verification after authoring.
- Keep tables within margins, avoid split rows where practical, and use hard page breaks for major chapter openers and one-page cheat sheets.
