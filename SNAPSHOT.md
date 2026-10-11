# AI Collaboration Snapshot: Room Booker

**Live app:** https://d3tn1rxaqj7h0y.cloudfront.net (sign in with any `@prudential.com` address, or continue as guest)
**AI partner:** Claude Code (VS Code agent). It wrote the code and infrastructure, ran the tests, and deployed to my AWS account.

## Scenario & architecture
Prudential staff book meeting rooms by the hour. They pick a group size and whether they need video/TV, and see only the rooms that fit. Employees hold up to 3 upcoming bookings, guests 1; owners can edit or cancel.
**Architecture:** CloudFront serves an S3 static website and routes `/api/*` to an IAM-protected Lambda Function URL, which reads and writes bookings in DynamoDB.

## Prompts I used
**1. The full assignment brief, pasted verbatim** ("…build a simple web application on AWS using S3, Lambda, and DynamoDB… Consider least-privilege IAM roles, CORS handling, and basic input validation…").
Because the criteria were in the prompt, they shaped the design: a conditional write prevents double-booking, the IAM role is least-privilege, and tests ran before anything touched AWS.

**2.** *"Make this to enterprise production grade application"*
This was vague. Instead of guessing, the agent asked me three decisions: login, CloudFront, and infrastructure as code. The result: HTTPS, security headers, Lambda and S3 reachable only through CloudFront (so no CORS is needed), backups, alarms and CI.

**3.** *"add continue as guest for those who wants to book room without login… password not required to login… just email id that ends with @prudential.com is required… you also must select the no.,of people and video/tv required? then show only those rooms depends on audien size."*
- **Clear rules gave usable results:** guest sessions, a room filter with a "Best fit" badge, and capacity and video/TV rules enforced on the server.
- **The AI pushed back:** email-only login lets anyone act as a colleague. It proposed emailed one-time codes, which need Amazon SES approval. I chose email-only for the demo, a known gap.
- **It closed the guest loophole:** 1 booking per guest, and a limit on new guest sessions per network.

## Where the AI got it wrong
1. **The first CloudFormation deploy failed.** The AI enabled DynamoDB encryption with an AWS-managed KMS key that a new account doesn't have yet, and the stack rolled back. The agent read the stack events and fixed it. It then found a silent bug of the same kind: alarms can't publish to an SNS topic encrypted with `aws/sns`.
2. **Tests caught bugs in its quota code.** A threaded test turned out to be unreliable in the simulator, so the agent proved the limit on real DynamoDB instead: 6 parallel requests produced exactly 3 bookings.
3. **It deleted without checking.** While removing an old Cognito user pool, it listed and deleted in one command, wiping a test account I had registered. It told me immediately; no bookings were lost.

**Lessons:** clear, testable rules beat vague prompts. Verify that it deploys and works, not just that it looks secure.

**Verified live:** wrong-domain emails, oversized groups, quota breaches, edits to others' bookings and tampered sessions are all rejected. 55 tests pass in CI.

**Honest gaps:** email-only sign-in proves nothing, no WAF, default domain.

*Prompt log:* https://github.com/dileepnsp/meeting-room-booking-aws/blob/main/PROMPTS.md
