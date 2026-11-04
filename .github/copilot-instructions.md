# Repository Instructions

## Home Assistant Translations

- Never include literal Jinja delimiters (`{{` or `}}`) in `strings.json` or `translations/*.json`. Home Assistant may interpret them as translation-format arguments and display `Translation error: MALFORMED_ARGUMENT`.
- Explain template variables in translation text without embedding a full Jinja expression. Put copyable expressions in the README or other non-translation documentation.
- Add or keep a regression test that asserts translated help strings do not contain literal Jinja delimiters.

## Documentation

- Before making any implementation or behavior change, read `REQUIREMENTS_TEMPLATE.md` in full and treat it as the normative project contract. If it conflicts with the requested change, surface the conflict before proceeding.
- At the end of every change, always review both `README.md` and `REQUIREMENTS_TEMPLATE.md` for consistency with the implementation.
- Update either document whenever behavior, configuration, supported profiles, or project requirements change. Do not leave stale or contradictory descriptions; if a document needs no edit, confirm that it was reviewed in the completion summary.

## Releases

- Do not create a release commit, tag, push, or GitHub Release until the complete unit and component test suite passes with the CI coverage threshold.
- Before release, run `python3 -m pytest -q tests/unit tests/component --cov=custom_components.home_activity_manager --cov-report= --cov-fail-under=95` and stop to fix any failures before committing or publishing.
- Include regression tests for user-visible translation and config-flow behavior; passing tests must verify the intended behavior, not preserve a broken implementation detail.