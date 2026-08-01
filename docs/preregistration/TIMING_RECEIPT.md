# Internal protocol timing receipt

## Assurance boundary

This receipt records the byte identities and local filesystem chronology of the
prospective internal analysis protocol and its three amendments. It is not an OSF,
AEA RCT Registry, cryptographic timestamp-authority, or other third-party
registration. The copied files are byte-identical to the Stage 1 working records;
their Git commit occurs later and does not retroactively create external
preregistration.

## Frozen documents and chronology

| Document | SHA-256 | Original local birth / last modification (Europe/London) | Relationship to authoritative run |
|---|---|---|---|
| `PUBLIC_DATA_PILOT_PREREGISTRATION.md` | `1f491aae0819da5cf3a9f567bb331e43596a41141333b37794554f66e64260fe` | 07:46:26 / 07:47:27, 2026-08-01 | before IDENT-0 v2 and Gate A v2 |
| `PUBLIC_DATA_PILOT_PREREGISTRATION_AMENDMENT_01.md` | `a170eb6309f9cafba0c07fc669368cc8511d315a822e7267bbe2ee33be22ef91` | 08:04:10 / 08:04:10, 2026-08-01 | before IDENT-0 v2 and Gate A v2 |
| `PUBLIC_DATA_PILOT_PREREGISTRATION_AMENDMENT_02.md` | `24f790e7f89932832635111236d7b8d317c1c7841e0c29fd6659b56d533e7a92` | 08:49:06 / 09:02:00, 2026-08-01 | before IDENT-0 v2 |
| `PUBLIC_DATA_PILOT_PREREGISTRATION_AMENDMENT_03.md` | `74fa8e2d8e5b861c665b0fb497b288ec5934dfdc01e2628af59819430cd2a54a` | 09:27:43 / 10:08:26, 2026-08-01 | after IDENT-0 v2; before Gate A v2 |

The authoritative IDENT-0 v2 manifest was created at 09:08:28 and is bound to
commit `1e04a181783105051c819af190b9546340bbb1fd`. The authoritative Gate A v2
manifest was created at 10:16:38 and is bound to commit
`836e3391355f84438af0d321f69e94281050c00d`. Those local times corroborate the
declared ordering but are not independently trusted timestamps.

Amendment 03 explicitly records the EHS and HPI/PIPR outcomes viewed during
feasibility work and the pre-run net-supply tolerance. Consequently the paper
uses “prospectively frozen internal protocol,” discloses outcome viewing, and
does not describe the public accounting facts as untouched confirmation.
