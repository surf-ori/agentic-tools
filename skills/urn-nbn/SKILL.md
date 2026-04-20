---
name: urn-nbn
description: >
  Use this skill when the user needs to resolve, register, or look up URN:NBN
  (Uniform Resource Name: National Bibliography Number) identifiers for Dutch
  publications. Trigger on "URN:NBN", "Nationale Resolver", "resolve a URN",
  "register persistent identifier", "urn:nbn:nl:", or any question about the
  KB (Koninklijke Bibliotheek) resolver API.
---

# URN:NBN skill — SURF ORI

## What is URN:NBN?

URN:NBN is a persistent identifier scheme for Dutch publications, managed by the KB (Koninklijke Bibliotheek). Format: `urn:nbn:nl:<registrant>:<local-id>`.

Example: `urn:nbn:nl:ui:10-1234567`

## Nationale Resolver API

Base URL: `https://resolver.kb.nl/resolve`

### Resolve a URN to its URL

```python
import requests

urn = "urn:nbn:nl:ui:10-1234567"
resp = requests.get(
    "https://resolver.kb.nl/resolve",
    params={"identifier": urn, "format": "json"},
)
resp.raise_for_status()
data = resp.json()
# data["locations"] is a list of {"url": ..., "access": "open"|"restricted"}
for loc in data.get("locations", []):
    print(loc["url"], loc.get("access"))
```

### Resolve via HTTP redirect

```
GET https://resolver.kb.nl/resolve?identifier=urn:nbn:nl:ui:10-1234567
```

Returns HTTP 302 to the target URL. Use `allow_redirects=False` to capture the `Location` header without following.

### Batch resolution

There is no official batch endpoint. For bulk resolution, iterate with a short sleep between requests and cache results locally.

## Common patterns

```python
def resolve_urn(urn: str) -> list[str]:
    resp = requests.get(
        "https://resolver.kb.nl/resolve",
        params={"identifier": urn, "format": "json"},
        timeout=10,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [loc["url"] for loc in resp.json().get("locations", [])]
```

## Caveats

- URN:NBN resolution may return multiple locations (mirrors, open-access copies).
- Some URNs resolve to restricted-access resources; `access` field will say `"restricted"`.
- The resolver has rate limits — add a 0.5 s delay between requests in bulk harvesting.
