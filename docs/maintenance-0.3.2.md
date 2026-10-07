# 0.3.2 maintenance candidate

This patch bundles the reviewed exposure worksheets, PBPK denominator correspondence and evidence severity fixes already on main into a distinct local release. It also corrects regional population warning attribution: an EU/US lookup using global defaults no longer claims an active regional override. Numeric defaults and screening equations are unchanged.

Dependencies advance to anyio 4.15.1, pydantic-settings 2.15.0, pytest 9.1.1 and mypy 2.3.1. Production floors match the reviewed anyio/settings versions. Stable MCP SDK 2.2.0 remains pinned. Generated current-release assets reflect 0.3.2; prior release records remain preserved.

The fresh-agent worksheet evaluation scored 10/10 against a withheld verified key after 19 substantive SDK calls. Four real SDK2 worksheet runs retain incomplete coverage, unresolved absorption transfer where appropriate, null approval and false assessment-stop authority. Some invalid-input branches were explained from the guide; focused tests separately exercise those branches. PBPK export consumers must inspect the structured compatibility report even when the outer call succeeds.

The TTC consumer requires its separately reviewed 0.3.2 producer-version compatibility patch before an installed Exposure upgrade. An exact version label must agree with payload provenance; neither mapping nor a completed calculation establishes qualification.

This change consolidates #20, #26, #29, #32 and #33 after validation. #5 and #9 are superseded by existing configuration/security floors. #16 is superseded by SDK2 error delivery, verified by actual protocol checks. The broader roadmap #4, additional Semgrep workflow #8 and scientific transfer-default proposal #17 remain separate review work.

Deployment uses a new immutable release directory, hash-pinned requirements and a private backup of the existing launcher configuration. Rollback restores the preceding launch configuration and runtime. Package publication and scientific-policy/default changes are separate steps.
