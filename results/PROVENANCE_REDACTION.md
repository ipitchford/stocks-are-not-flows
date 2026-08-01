# Public-result provenance boundary

The authoritative run manifests recorded exact local executable paths. Those
paths are operational metadata, not scientific inputs, and are not redistributed
in the anonymous public repository. Their byte identities are retained here:

| Run | Original private manifest SHA-256 |
|---|---|
| IDENT-0 v2 | `a23d17ea471eb7ed67a96e34b5fb85f7c50b34c7e231987498ed36963220ccda` |
| Gate A v2 | `3e1f92e436e3744d6702d8314c9f4c0f5602898d5b996f9a60fa0010af291c90` |
| Gate A v2 offline replay | `f00bfcace904d7a3cb6fcb8746d1fb0346b38e74de6d67224d868ccb0a03a57b` |
| Partial-ID design geometry v1 | `7e76a2930297e0b13ad2cd6aa1a6a4a43cbe0a478da2405011a30fadbaf51b5d` |

The reports, source receipts, derived tables, figures, and raw official inputs
are byte-identical to the internal release and are covered by
`PUBLIC_RESULT_MANIFEST.sha256`. This privacy redaction does not change a report
or any value cited by the manuscript.

The development commit hashes printed in the paper and README are preserved as
historical identities but the private Git bundle is not included. The public
repository starts from a single anonymous release commit.
