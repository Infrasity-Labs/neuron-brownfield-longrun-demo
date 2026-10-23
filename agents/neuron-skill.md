# How to use Neuron (shared by all roles)

You start every session with no memory of earlier sessions. Every project rule you follow must come from Neuron. Do not rely on rules you think you remember.

## Asking

1. Call the Neuron ask tool with include_sources set to true. Pass the vault name your role file names. A vault is a name, never a path.
2. Read the response before you use it. Check these fields:
   - status and retrieval.synthesis_status. Only ok means a clean answer.
   - retrieval.finish_reason. Anything other than stop means the text is suspect. Say so.
   - vault_override_ignored. If it is present, Neuron used a different vault than the one you asked for. Say so.
3. For every rule you apply, quote its source: the path, byte_start and byte_end from the sources list.

Use only the vaults team and reviewer-private. Other vaults may be listed on this machine. Never ask, explore or read them.

## When the answer is not ok

- provider_error means the model could not be reached. It does not mean the notes are empty. Never write "I couldn't find anything" or "there is no rule". Write that the model was unreachable.
- After a provider_error, call the explore tool on the same topic. Explore walks the graph and needs no model. Report what it returned and mark it as not synthesised and not verified.
- no_llm, empty, truncated and abnormal_stop: report the status by name and do not treat the text as a rule.

## When a rule was replaced

If Neuron shows an older value as replaced, or an answer mentions two values, follow the current rule. Say which value was replaced and where each value came from. If a note outside the rules, such as a runbook, disagrees with the current rule, follow the rule and tell the Maintainer about the disagreement.

## Style

Write plain English. Do not use em dashes.
