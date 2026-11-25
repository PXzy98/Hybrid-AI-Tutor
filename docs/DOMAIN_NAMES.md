# Domain name ideas (task V11)

Prof. Abbas buys the domain (GoDaddy) from the names the team proposes. Each member adds names below before
the AWS deploy; availability and price must be checked on the registrar when choosing (not checked here).
Criteria: short, easy to spell aloud, keeps the product name ScholarMind AI (renamed on 2026-11-25; the PACT
names proposed before are dropped), no university trademark (no "uottawa"), works for research and industry
training too ("Brightspace plus").

| Name | Why | Proposed by |
|---|---|---|
| scholarmind.ai | the product name on the `.ai` domain | Z |
| scholarmindai.ca | the full name; `.ca` for a Canadian service | Z |
| scholarmind-ai.com | the same with a dash, if the others are taken | Z |
| scholarmindlearning.ca | not only university courses: training and research groups too | Z |
| getscholarmind.ca | short product-style name | Z |

Then: Prof. Abbas chooses, buys it, and points an `A` record at the AWS server's address; the deploy sets
`SITE_ADDRESS` to the name and Caddy obtains the certificate (SECURITY_REVIEW.md, before the public deploy).
