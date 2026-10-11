# Example drafts (illustrative: facts are placeholders, not real data)

## Email, security lead
```json
{
  "subject": "Quick note on your public-facing SSH hosts",
  "body": "Hi, while reviewing publicly visible infrastructure we noticed your organisation runs 14 internet-facing hosts, several on an outdated OpenSSH version. That is usually a quick fix but easy to miss at your size. We help mid-size fintech teams get a clear exposure picture without extra tooling. Would a 15-minute walkthrough of what we see be useful this week?",
  "signals_used": ["exposed_hosts=14", "outdated_ssh=true"],
  "channel": "email"
}
```

## LinkedIn, IT lead
```json
{
  "subject": "Exposure question",
  "body": "Hi, noticed 14 public hosts with an older OpenSSH build while mapping fintech footprints. Happy to share the list if useful, no strings attached.",
  "signals_used": ["exposed_hosts=14", "outdated_ssh=true"],
  "channel": "linkedin"
}
```

## Why the bad version fails
"Hackers are probably already inside your network, act now before it's too late!"
Fails validation: banned phrases, unsupported claim, no cited signal.
