# Copilot Instructions For This Project

This repository targets a BeagleBoneBlack runtime environment.

## Validation Constraint (Critical)

- Do not claim to have validated runtime behavior with CLI commands.
- Do not state that build, flash, deploy, PRU bring-up, hardware I/O, or integration checks were executed unless the user explicitly confirms they ran them.
- Assume the coding machine is not the BeagleBoneBlack and cannot provide authoritative runtime validation for this project.

## Required Validation Workflow

When validation is needed:

1. Ask the user to run the exact command(s) on the BeagleBoneBlack or target environment.
2. Provide copy-paste command blocks and expected output shape.
3. Wait for the user to paste results.
4. Analyze the pasted output and then continue with fixes or next steps.

## Response Requirements

- Be explicit about what was and was not validated.
- Separate "code changes made" from "validation pending".
- If no validation output was provided by the user, mark validation status as "not run on target".
- Prefer safe static reasoning over assumptions about hardware behavior.

## Example Prompting Pattern

Use language like:

- "I can prepare the change, but I cannot validate hardware/runtime behavior from this machine."
- "Please run the following on your BeagleBoneBlack and paste the output so I can verify."
