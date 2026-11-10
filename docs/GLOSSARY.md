# Glossary of Compliance and System Terms

This glossary establishes standard terminology for Clearance Check. One term is used per concept across the interface, documentation, reports, and technical dossier.

| Term | Definition |
|---|---|
| **Adverse Finding** | A screening result indicating a potential match, designated airline restriction, or high-risk jurisdiction alert requiring compliance officer review. |
| **Audit Trail** | An append-only local database record documenting screening queries, timestamps, source versions evaluated, and operator actions. |
| **Beneficial Owner** | A natural person or legal entity holding direct or indirect shareholding or voting rights in a corporate entity. |
| **Candidate Match** | A listed record retrieved from regulatory lists that meets initial indexing and token similarity criteria prior to tiering. |
| **Clearance Check** | The official product name for the regulatory sanctions, export control, and aviation screening system. |
| **Control** | The ability to exercise dominant influence or operational governance over an entity, assessed under EU and UK criteria. |
| **Corroborating Data** | Secondary identifiers, including date of birth, nationality, passport number, or registration number, used to confirm or refute candidate matches. |
| **Direct Ownership** | A shareholding stake held directly by an immediate shareholder in a target entity without intermediate holding entities. |
| **Drawn Status Marker** | A visual status indicator consisting of a solid filled circle in the defined status colour paired with uppercase status text. |
| **Indirect Ownership** | A shareholding stake held through one or more intermediate holding entities, calculated via multiplication of successive shareholding percentages. |
| **List Refresh** | The automated or manual process of verifying and downloading updated official regulatory source files. |
| **Name Screening** | The algorithmic evaluation of counterparty names against official lists using Jaro-Winkler token scoring, phonetics, and transliteration. |
| **Ownership Check** | The evaluation of corporate shareholding hierarchies to aggregate beneficial ownership stakes against the 50% rule and control criteria. |
| **Potential Match** | High-confidence screening result (score >= 0.80 or exact identifier match) requiring mandatory compliance review and escalation. |
| **Possible Match** | Moderate-confidence screening result (score >= 0.70 or phonetic similarity) requiring manual analysis. |
| **Raw Search** | Direct full-text keyword queries executed against the local SQLite FTS5 database across all regulatory list fields. |
| **Sanction checK** | The primary screen and window header title of the application. |
| **Sub-threshold Match** | A weak similarity match (score < 0.70) displayed for informational and advisory awareness only. |
| **Transliteration** | The systematic phonetic conversion of non-Latin characters (such as Cyrillic or Arabic) into Latin characters using rule tables. |
| **50% Rule** | Regulatory rule (under US OFAC, EU, and UK regimes) under which an entity owned 50% or more by blocked persons is treated as blocked. |
