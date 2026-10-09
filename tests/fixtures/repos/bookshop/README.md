# Bookshop (synthetic fixture)

This is a **synthetic** repository. Bookshop is not a real product; it uses invented names, and its only
outside hosts are reserved example domains (RFC 2606 `.example`). The code is never run.

It exists so the c4-diagrams skill has one small, polyglot system whose analysis is known:

- `c4-model.json` is the complete model of this repository. It is copied verbatim into
  `skills/c4-diagrams/assets/c4-model-reference.md` as the worked example, and
  `tests/test_reference_example.py` checks that the two match, that the model validates against facts
  freshly generated from this tree, and that every evidence path resolves here (SPEC-01).
- SPEC-17 (skill evaluation) and SPEC-21 (example output) reuse it as a gold fixture.

If you change a file here, re-run the tests and update `c4-model.json` (and the evidence lines in it)
in the same change.
