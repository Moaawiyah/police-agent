# Gmail report delivery

## What this enables

The Police agent can send the mandatory final `result_<game_id>.json` as a
JSON attachment through the Gmail API. It requests only
`https://www.googleapis.com/auth/gmail.send`: it cannot read, list, modify, or
delete mailbox content. Email is disabled by default, and local practice needs
no Google account.

## Safe offline rehearsal

Keep `email.enabled = true` and `email.mode = "draft"` in the ignored
`config/police/game.toml`, then run a report-producing match. Draft mode writes
a local `.eml` file and makes no Google API call.

## One-time Google setup

1. Create or select a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen and add the sending account as a test
   user while the application is in testing mode.
3. Add only the `gmail.send` scope.
4. Create an OAuth client of type **Desktop app**. This is the Google client
   type, not a Gmail desktop program.
5. Download the client JSON as `credentials.json` in the repository root.
   Never paste its contents into documentation, logs, issues, or chat.
6. Install the optional dependency with `uv sync --extra gmail`.
7. In the ignored `game.toml`, set `email.enabled = true` and
   `email.mode = "send"`, then deliberately run a report-producing match.
   On the first send, the client opens Google's consent flow and writes the
   resulting `token.json`; later sends reuse or refresh it.

There is no separate authorization CLI flag. Authorization happens only when
an enabled send actually needs credentials.

## Files and failure behavior

Both `credentials.json` and `token.json` are ignored by exact name and must
never be committed. A real send passes through the persisted daily quota and
the Gmail-specific Gatekeeper. Rate-limit or provider failure leaves the report
unsent and does not rewrite the game result. Treat delivery as live-verified
only after Gmail returns a real message ID.
