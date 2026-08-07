# Security notes

ArxMedia is built first for self-hosting.

## What this means

- Assume private or home-lab deployment by default.
- If you expose it to the public internet, harden your setup first.

## Self-hosting baseline

- Set a strong `SECRET_KEY`.
- Set `DEBUG=False`.
- Use strong database credentials.
- Keep `.env` private and never commit it.
- Put the app behind a reverse proxy with HTTPS.

## If you find a security issue

- Please do not post exploit details in a public issue.
- Open an issue with minimal details, then coordinate privately with the maintainer.
- Include repro steps and impact so it can be fixed quickly.

## Secrets hygiene

- Commit placeholders in `.env.example`, never real secrets.
- Rotate any key or token that is accidentally exposed.
