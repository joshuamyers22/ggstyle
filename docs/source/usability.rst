Usability evidence
==================

The v0.4 API shape is backed by ten checked fixtures spanning analysts, researchers,
reporting engineers, library authors, and users arriving from ggplot2. The fixture gate
counts Python statements with the AST, so formatting does not affect the result:

.. code-block:: console

   $ python tools/finishing_usability.py
   finishing usability: 10 cases, 5 personas, 40 -> 11 statements (72.5% reduction)

Every candidate keeps native axes access, avoids data mutation, and is shorter than its
idiomatic Matplotlib baseline. The aggregate exceeds the roadmap's 35 percent reduction
threshold. Geometry, visual, typing, compatibility, and installed-wheel tests remain
separate gates because brevity alone does not demonstrate correctness.

External pilot protocol
-----------------------

Before tagging v0.4.0, the release owner must record at least five uncoached pilot
sessions against representative fixtures. For each session record the participant's
background, selected task, whether documentation search was needed, completion outcome,
misleading or missing API vocabulary, and resulting action. Do not record personal or
sensitive data.

Pilot evidence is a human release approval and cannot be manufactured by CI. The tag
checklist in ``CONTRIBUTING.md`` keeps it explicit alongside the automated gates.
