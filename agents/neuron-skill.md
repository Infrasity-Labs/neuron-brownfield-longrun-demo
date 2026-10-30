# How to call Neuron (arm C only)

This file describes the tool, not the project. It is added to the system prompt only when Neuron is the rule source.

## Asking

1. Call the Neuron ask tool with include_sources set to true. A vault is a name, never a path.
2. Read the response before you use it. Check these fields:
   - status and retrieval.synthesis_status. Only ok means a clean answer.
   - retrieval.finish_reason. Anything other than stop means the text is suspect. Say so.
   - vault_override_ignored. If it is present, Neuron used a different vault than the one you asked for. Say so.
3. For every rule you apply, give its source: the path, byte_start and byte_end from the sources list.

Use only the vaults your role file names. Other vaults may be listed on this machine. Never ask, explore or read them.

## When the answer is not ok

- provider_error means the model could not be reached. It does not mean the notes are empty. Never write "I couldn't find anything" or "there is no rule". Write that the model was unreachable.
- After a provider_error, call the explore tool on the same topic. Explore walks the graph and needs no model. Report what it returned and mark it as not synthesised and not verified.
- no_llm, empty, truncated and abnormal_stop: report the status by name and do not treat the text as a rule.
