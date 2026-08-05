# Email Provider Panel Design QA

## Evidence

- Source visual truth: `/home/lijunjie/.codex/attachments/6690ee9d-ad3c-4cd1-b606-9a9f4698b8c3/codex-clipboard-8e74316d-8051-4a49-8a79-f00623213760.png`
- Implementation: `http://127.0.0.1:8793/` with isolated configuration and the email-service view open
- Primary screenshot: `/tmp/grok-email-preview.CIwuy6/email-provider-desktop-light.png`
- Side-by-side comparison: `/tmp/grok-email-preview.CIwuy6/email-provider-comparison.png`
- Additional states: `/tmp/grok-email-preview.CIwuy6/email-provider-desktop-dark.png`, `/tmp/grok-email-preview.CIwuy6/email-provider-desktop-advanced.png`, `/tmp/grok-email-preview.CIwuy6/email-provider-mobile-390.png`, `/tmp/grok-email-preview.CIwuy6/email-provider-mobile-320.png`
- Source pixels: `1917 x 813`; implementation pixels and CSS viewport: `1917 x 781`; `deviceScaleFactor: 1`. The 32 px source-height difference is outside the compared primary form region, so no density normalization was required.
- State: Cloudflare selected, saved configuration present, secret masked, successful connectivity result visible; light theme for the primary comparison.

## Findings

No actionable P0, P1, or P2 differences remain.

- Fonts and typography: Geist and Geist Mono preserve the existing console language, with clear label, field, state, and action hierarchy. Text does not wrap or truncate incorrectly at the tested widths.
- Spacing and layout: the provider selector, dynamic form grid, action row, and advanced domain rotation follow the reference grouping. The implementation intentionally keeps the existing console's `1280px` content rail instead of copying the reference's nearly full-width shell.
- Colors and tokens: light and dark themes use the existing neutral and red accent tokens with readable success, warning, and error states. No gradients or decorative surfaces were introduced.
- Image and icon fidelity: the source contains no required product imagery. The implementation uses native form affordances and does not substitute CSS art, custom SVG, emoji, or placeholder assets.
- Copy and content: the source's unsupported Apple Mail API fields were replaced by the six providers and settings implemented by this repository. “邮箱服务” is the primary task; “域名轮换” is correctly demoted to advanced settings.
- Responsiveness: `390px` and `320px` captures have no horizontal overflow or overlap. Action buttons remain at least `129px` wide.
- Accessibility and states: labels are associated with controls; status and messages use live regions; provider selection, save, secret preserve/clear, test success, validation error, theme switching, and advanced expand/collapse were exercised.

## Focused Evidence

The native-resolution desktop capture was sufficient to inspect labels, field borders, controls, status badges, action buttons, and copy. Separate mobile captures were used for the dense toolbar and one-column form because those details were too small in the side-by-side full-view comparison.

## Comparison History

1. Initial interaction pass found a functional issue outside the visual comparison: Cloudflare direct-mode connectivity ignored a custom URL port and probed only 80/443.
2. The probe now uses the parsed URL port, with a regression test for `http://mail.example.com:8793`.
3. Post-fix browser evidence confirms a successful custom-port test, all six provider schemas, secret preservation and explicit clearing, inline validation, advanced settings, light/dark themes, and both mobile widths. The deliberate invalid-URL test produced one expected HTTP 400 console entry; there were no unexpected page or console errors.

## Follow-up Polish

No P3 follow-up is required for this release.

final result: passed
