# Domain name ideas (task V11)

Prof. Abbas buys the domain (GoDaddy) from the names the team proposes. Each member adds names below before
the AWS deploy; availability and price must be checked on the registrar when choosing (not checked here).
Criteria: short, easy to spell aloud, keeps the PACT name (decision of 2026-11-17), no university trademark
(no "uottawa"), works for research and industry training too ("Brightspace plus").

| Name | Why | Proposed by |
|---|---|---|
| pacttutor.ca | the product name plus what it is; `.ca` for a Canadian service | Z |
| pact-tutor.com | the same with a dash, if the first is taken | Z |
| pactlearning.ca | not only university courses: training and research groups too | Z |
| getpact.ca | short product-style name | Z |
| privacyawaretutor.ca | says the main message, long but clear | Z |

Then: Prof. Abbas chooses, buys it, and points an `A` record at the AWS server's address; the deploy sets
`SITE_ADDRESS` to the name and Caddy obtains the certificate (SECURITY_REVIEW.md, before the public deploy).
