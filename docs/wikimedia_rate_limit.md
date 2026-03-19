In particular, clients should:

    include a meaningful User-Agent header according to the User-Agent policy.
    implement cookie support when using bot passwords or OAuth to authenticate.
    limit the number of concurrent requests to 3 or fewer.
    follow API-specific guidelines, such as Action API etiquette.
    respect the Retry-After header provided with a 429 Too Many Requests status code.

Clients that need a higher rate of access can:

    request the bot flag from your local wiki community. Community-approved bots get higher rate limits.
    where appropriate, consider running your bot in Toolforge or another Wikimedia Cloud Services offering.

The Wikimedia Enterprise APIs are also available for commercial, high-volume read-only usage. Free access can be provided for community and research projects upon request.
Limits

Rate limits take into account the client's identity and level of access. Below is an overview of rate limits grouped by the type of client (caveats apply). Specific limits for each group are currently being finalized based on experimentation and observation; see the timeline for more details.
Group 	Description 	Limit (req/hr)
Unidentified 	Requests that have no identifying characteristics other than an IP address 	500
User-Agent only 	Unauthenticated requests that provide a User-Agent header that is compliant with the User-Agent policy. 	low
Browser requests 	Unauthenticated browser requests (e.g. for the search bar or preview popups) 	1,000
Logged-in browser requests (including requests from Gadgets) 	medium
Authenticated 	Bots using an OAuth 2.0 access token or session cookie to authenticate 	10,000
Wikimedia Cloud Services (WMCS) 	Requests from Toolforge or WMCS using a User-Agent as the user identity 	very high
Approved bots 	Bots using an account that has a bot flag on any wiki 	very high
Known clients 	Requests from a client that is well-known to the Wikimedia Foundation 	very high
Action-based rate limits

In addition to limits based on client identity, actions (such as editing pages, moving pages, and uploading files) are rate limited to prevent vandalism and other harmful behaviors. Action-based limits depend on the status of the user account and on the policy of the individual wiki. For example, most Wikimedia projects limit logged-out users to eight edits per minute. To learn more about actions and specific limits, see Manual:Rate limits.
Errors

When a client exceeds its rate limit, the gateway responds with HTTP status code 429 (Too Many Requests). Other components involved in handling the request may also respond with status 429 when per-client limits are exceeded, or with status 503 (Service Unavailable) when a backend system such as a database server is overloaded.

Responses with status code 429 or 503 typically also have the Retry-After header set, indicating how long the client should wait until it retries the request. If no such header is present, clients should wait at least five seconds, or implement exponential back-off.
Timeline

Rate limits for API requests will be introduced in phases during March/April 2026. For more information, see the project timeline. Steps that affect users will be announced on the wikitech-l and mediawiki-api-announce mailing lists and on TechNews.
Caveats

Operators of legacy API clients should be aware of the following edge cases and pitfalls:

    The gateway limits described above do not apply to the legacy API gateway used for api.wikimedia.org and for the LiftWing APIs. These APIs are expected to be migrated to the new infrastructure (with new rate limits that more closely resemble the current limits) in 2026.
    OAuth 1 access tokens are not supported on their own by the rate limit infrastructure. Requests using OAuth 1 tokens will be treated as unauthenticated with respect to rate limiting, unless you also send cookies with the request.
    Elevated rate limits embedded directly in some older owner-only tokens are ignored by the new rate limiting infrastructure (but are still used for endpoints on api.wikimedia.org, see T409305). Going forward, rate limits will be determined by a user's current privileges, not limits assigned at the time of token creation.
    Generally, a refresh-token flow should be preferred over direct use of owner-only tokens for OAuth 2.0, but support for that is still limited (see T407987 and T412214 ). For now, clients should support session cookies to be used along with OAuth tokens. This allows the correct rate limit class to be applied.

Get help

Bot operators who are unsure how to get the access they need can contact the Wikimedia Foundation at bot-traffic@wikimedia.org.
See also

    Best practices for using the Action API on Wikimedia wikis
    Technical overview of rate limiting in Wikimedia infrastructure
