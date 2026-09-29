# Flo SMS and Twilio setup

## Number and ARIVE routing

- Flo's local sending number: `+19046829414`.
- The ARIVE incoming-message webhook remains `POST https://losapi.myarive.com/los/api/sms/webhook`.
- The voice webhook remains `POST https://demo.twilio.com/welcome/voice/`.
- Flo does not receive Twilio webhooks. It uses Twilio's REST API from Ashley's PC and polls message history every 90 seconds while Flo is running. The app creates no public listener or tunnel.
- Startup catch-up is capped at seven days. Twilio message SIDs deduplicate records; paginated history and message delivery updates are stored locally.

## Connect Twilio

Open **Settings → Communications → Text Messaging**. Create a dedicated Restricted API Key in Twilio Console called **Flo - Ashley PC**, limited to Messaging message create/read and active phone-number read permissions. Enter the Account SID, API Key SID, and API Key Secret in Flo. The app sends credentials only from Electron's main process and encrypts the secret through Electron `safeStorage` (Windows DPAPI). The credential record is in Flo's per-user app-data folder; it contains the encrypted secret, not its plaintext. The API key secret is not shown again after saving.

Flo verifies access by looking up `+19046829414`. It displays Connected, Not Connected, or Needs Attention. Twilio errors are reported by status/code; Flo does not set a fake Sent status.

## File contacts, approval, and history

In a Customer File's **Text Messages** area, add complete mobile numbers with a contact name and role. Numbers are normalized to E.164. The contact list in that file is the source used for recipient selection. Flo does not resolve recipients from a partial number or a remembered name.

For outside contacts, Ashley reviews the recipient and message, then selects **Send**. The main process validates the current file/contact pair, number, saved credentials, approval timestamp, and opt-out state before calling Twilio. Outbound records store the Twilio SID, returned status, recipient, file/contact IDs, and Ashley's approval metadata. Message bodies stay in Flo's local communications store and are excluded from general technical logs.

Twilio history is matched by exact E.164 number. A unique file/contact match is attached automatically. No match or multiple matches stay in **Settings → Communications → Needs Review** until Ashley assigns the message. Twilio message SIDs are the deduplication keys. Delivery states are refreshed from Twilio for pending outbound records.

An inbound STOP-family command marks every matching saved contact SMS Opted Out; sends are blocked locally, and Twilio remains authoritative. A START-family reply updates the locally recorded state. Flo does not interpret HELP or automatically answer messages.

MMS messages retain a media reference/content-type only and display “Attachment received.” Flo never downloads or analyzes the media automatically. Use the existing safe document-import flow only after Ashley chooses to add a file.

## Current account limitations and test process

Twilio Console currently flags A2P 10DLC registration as required for this US local number, shows no Messaging Service attached, and reports that US SMS/MMS routing is active. The account compliance CSV/status report has not been generated, so exact Brand/Campaign statuses and the definitive `Can Send Messages` value remain unverified. Do not change registration or webhooks as part of Flo setup. Resolve registration through Twilio's existing Console workflow before sending production US messages.

Test with a synthetic Customer File such as `Johnson-Test` and a test mobile entered directly into Flo. No real borrower/LO test, Windows package acceptance, or release should be marked complete until a designated test phone is entered in Flo and the test reply is received. Media import, cross-channel activity, and chat-driven automatic sending are not included; only an Ashley-approved send from the file's message panel can send SMS.
