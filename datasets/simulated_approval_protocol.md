# Deterministic simulated-approval protocol

This protocol replaces the previously mischaracterized ASK condition.
It is a deterministic software policy and **not** a human-participant or human-response-time experiment.
The policy denies secret/environment access, shell/process execution, attacker-indicative payloads,
and high-risk calls; it approves only narrow project-like filesystem writes that reach ASK.
No artificial sleep/delay is inserted. The separately available `interactive` mode is excluded from
reported manuscript results unless a human session is explicitly executed and recorded.
