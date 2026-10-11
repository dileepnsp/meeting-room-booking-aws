# AI Collaboration Snapshot: Room Booker

**Live app:** https://d3tn1rxaqj7h0y.cloudfront.net (sign in with any `@prudential.com` address, or continue as guest)
**AI partner:** Claude Code (an agent in VS Code). It wrote the code and the CloudFormation template, ran the tests, and deployed to my AWS account.

## Scenario & architecture
Prudential staff book meeting rooms by the hour. You choose how many people are coming and whether you need video/TV, and only rooms that fit are shown. Employees can hold 3 upcoming bookings, guests 1.
**Architecture:** a CloudFront-fronted S3 static site calls an IAM-protected Lambda Function URL, which issues signed sessions and reads and writes bookings in DynamoDB. One CloudFormation template defines all of it.

## Prompts I used
**1. The full assignment brief, pasted verbatim** ("…build a simple web application on AWS using S3, Lambda, and DynamoDB… Consider least-privilege IAM roles, CORS handling, and basic input validation…"). The evaluation criteria drove the design: a conditional write prevents double-booking, the role is least-privilege, and tests ran before anything touched AWS.

**2.** *"Make this to enterprise production grade application"*
This was vague. The agent asked me three decisions instead of guessing (login, CloudFront, infrastructure as code). The result: HTTPS and security headers, Lambda and S3 reachable only through CloudFront, no CORS needed, backups, alarms and CI.

**3.** *"add continue as guest for those who wants to book room without login… password not required to login… just email id that ends with @prudential.com is required… you also must select the no.,of people and video/tv required? then show only those rooms depends on audien size."*
- **Testable rules gave usable results:** guest sessions, a room filter with a "Best fit" badge, and capacity and video/TV rules enforced on the server too.
- **The AI pushed back:** it pointed out that email-only login lets anyone act as any colleague. It offered emailed one-time codes instead, explaining these would need Amazon SES approval. I chose email-only for demo simplicity, so that's a known gap below.
- **Guest loophole:** it asked how to stop guests getting around the limit. We settled on 1 booking per guest, plus a limit on new guest sessions per network.

## Where the AI got it wrong
1. **The first CloudFormation deploy failed.** The AI turned on DynamoDB encryption with an AWS-managed KMS key that a new account doesn't have yet. CloudFormation rolled back. The agent read the stack events, fixed it, and found a silent bug of the same kind: alarms can't publish to an SNS topic encrypted with `aws/sns`.
2. **Tests caught its quota code.** It serialized DynamoDB values twice, and it returned a 500 instead of a 403 on one edge case. When a threaded test failed, it worked out the simulator wasn't thread-safe, rewrote the test deterministically, and then proved the limit on real DynamoDB: 6 parallel requests produced exactly 3 bookings.
3. **It deleted something without checking.** While removing the old Cognito user pool, it listed and deleted in one command. It wiped a test account I'd registered (`dileep@cowork.com`) before noticing it was there. The agent told me straight away and confirmed no bookings were lost. Lesson: review before running destructive commands.

**Lesson:** precise prompts with testable rules beat vague ones. And verify it deploys and behaves correctly, not just that it looks secure.

## Verified live
- A non-company or look-alike email returns 400.
- Too many people for a room returns `capacity`; video in a room without a screen returns `av`.
- A 4th employee booking or 2nd guest booking returns `quota`.
- Other people's bookings return 403 on edit or cancel.
- A tampered session returns 401.
- 55 unit tests pass.

**Honest gaps:** email-only sign-in proves nothing (anyone can type a colleague's address), no WAF, default domain.

*Transcript:* TODO_LINK (optional)
