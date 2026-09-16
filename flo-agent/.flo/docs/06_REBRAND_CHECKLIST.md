# Rebrand Checklist

## Rule

Rebrand **visible product identity** aggressively. Rebrand **internal upstream machinery** conservatively.

## Desktop packaging

Inspect the tagged `apps/desktop/package.json` and related build scripts.

Expected targets include:

- `productName` -> Flo
- build `appId` -> project-owner-selected reverse-DNS ID
- `executableName` -> Flo
- protocol display name -> Flo Protocol
- protocol scheme -> `flo`
- artifact name -> Flo-based
- platform display/bundle strings
- permission descriptions mentioning Hermes
- app category if the mortgage productivity positioning warrants a change
- icons

Do not invent a production reverse-DNS ID if ownership/domain has not been supplied. Use a clearly marked placeholder such as `com.example.flo` until the owner chooses it.

## User-facing source scan

Search for case variants:
- Hermes
- HERMES
- Hermes Agent
- hermes://

Categorize every match:
1. must rebrand;
2. internal compatibility - keep;
3. upstream attribution/license - keep;
4. developer documentation - keep or annotate;
5. uncertain - record.

Do not mass-replace.

## Updater

Find all update code paths.

Before shipping Flo:
- updater must use a Flo-owned feed/release source; or
- updater must be disabled with clear product messaging.

Do not let an upstream update silently replace Flo.

## Onboarding

Flo onboarding should focus on:
- who Flo is;
- connecting the model/provider;
- connecting approved work sources;
- choosing permissions;
- privacy/approval behavior;
- first pipeline brief.

Generic developer tooling belongs under Advanced.

## Verification

Add automated checks for:
- prohibited user-visible Hermes labels;
- expected Flo package metadata;
- `flo://` deep-link routing;
- preserved upstream license;
- no upstream updater endpoint used as Flo's production release channel.
