# Third-party notices

## app/ (the target application)

`app/` is a copy of [gothinkster/node-express-realworld-example-app](https://github.com/gothinkster/node-express-realworld-example-app),
upstream commit `30b68e1e881462b2f4164ea09ab4c4f5699c7b0b` (2024-01-04), with the `.git` folder removed. In the
repository's own working copy, the three demo features were added by the Builder sessions of the pilot run. Those edits
are no longer in `app/`: `app/` holds the starting state, and the pilot's edits are kept as
[demo-state/pilot-builder-edits.patch](demo-state/pilot-builder-edits.patch).

How `app/` was restored to the starting state: the pilot's Builder edits were reversed using the Edit and Write tool calls
recorded in `demo-state/transcripts/step*-builder.jsonl`. The result agrees with the notes in `vault/` that describe the
code (for example `take: Number(query.limit) || 10` in `getArticles`, four migrations, a Comment model without `editedAt`
or `deletedAt`). It was not compared with a fresh download of the upstream commit, because no network was used.

**Licence of that code: not established by this repository.** The upstream `package.json` declares `"license": "MIT"`
(`app/package.json`, line 4). The upstream repository publishes no `LICENSE` file at that commit (its root holds no such file,
and GitHub's licence endpoint for the repository answers 404, both checked on 2026-10-30). MIT requires the copyright
notice to travel with the code, and there is no copyright line to copy. **Decision needed from the repository owners:**
ask the upstream authors for the notice, or replace the target app with a project that ships one. Nothing here invents a
holder.

## Okto Neuron

Okto Neuron is not part of this repository. It is licensed by Okto Labs under the Elastic License 2.0 with the Okto Labs
addendum; see the README and the Okto Neuron repository.

## This repository's own licence

MIT, copyright OktoLabs AI, for the demo code only: see [LICENSE](LICENSE). The holder was decided by the repository
owners. The licence type (MIT) was chosen to match the two sibling demo repositories (Grafx shared store, Pulse and Grafx
decision memory) and has not been confirmed by the owners. It does not cover `app/` (see above) or Okto Neuron.
