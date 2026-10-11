# Prompt Log: Room Booker

You are a senior AWS full-stack engineer. Build a working, publicly accessible meeting-room booking application that satisfies the assignment below.

### Mandatory architecture

* **Frontend:** HTML, CSS and JavaScript hosted on Amazon S3.
* **Backend:** AWS Lambda exposed through a Function URL or API Gateway.
* **Database:** Amazon DynamoDB for persistent application data.
* **Deployment:** Automate deployment using scripts and AWS CLI where practical.

### Functional requirements

1. Users can view available meeting rooms.
2. Users can create a booking and retrieve saved bookings.
3. Users receive clear success and error messages.
4. All application data must persist in DynamoDB.
5. The frontend must communicate with Lambda through the configured API endpoint.

### Engineering requirements

* Follow least-privilege IAM principles.
* Validate and sanitize inputs on the backend.
* Configure CORS for the intended frontend origin.
* Handle missing fields, invalid requests, database errors and duplicate submissions.
* Keep AWS credentials and secrets out of frontend code.
* Include automated tests for core business logic.
* Provide clear deployment instructions and a cleanup procedure.

### Working process

1. Inspect the environment and repository before making changes.
2. Propose the architecture, DynamoDB schema, API contract and deployment plan.
3. Implement the application in small, verifiable stages.
4. Run tests after each significant change.
5. Deploy to AWS only after confirming the account, region, permissions and expected costs.
6. Test the deployed application end-to-end, including creating and retrieving records.
7. Report the public URL, deployed resources, test results, limitations and any outstanding risks.

Do not claim that the application works unless you have verified it. Ask questions only when a decision materially affects the implementation.

Deliver:

* A working public URL.
* A one-page AI Collaboration Snapshot, maximum approximately 500 words.
* At least two genuine prompts used during development, an actual AI error or limitation, and an honest explanation of how it was corrected.

Treat the assignment brief below as the acceptance criteria. Preserve all mandatory requirements and distinguish optional enhancements from the minimum deliverable.

Assisgnment brief: 

You frequently use AI tools, including AI agents, to generate applications. We want to see you take it a step further by
using AI to directly orchestrate cloud services and deliver a real, working app.
Your task: build a simple web application on AWS using S3, Lambda, and DynamoDB, with AI as your primary
coding and configuration partner.
The core deliverable is a publicly accessible URL where we can actually use the app.
What You Need to Do
1. Pick your own real-world scenario
Define a simple but meaningful use case that requires both writing data and reading it back.
- Examples: a meeting room sign-up, an anonymous message board, a to-do list, or a live poll.
Be creative, but keep it small and functional.
2. Use these three AWS services - no exceptions
Service Required use
S3 Host your frontend as a static website.
Lambda Run backend logic, exposed via a Function URL or API Gateway.
DynamoDB Store and retrieve all data.
Use AI tools, such as ChatGPT, Copilot, Cursor, or AI agents, to generate the frontend code, Lambda function,
DynamoDB table design, IAM policy, and any other configuration.
3. Deliver just two things
- A working URL - click it, and the application should function end-to-end. At minimum, it must allow a user to create
one item and view all items.
- A one-page "AI Collaboration Snapshot", maximum approximately 500 words.
The AI Collaboration Snapshot must include:
- Your chosen scenario and a one-sentence architecture summary.
- At least two actual prompts you gave the AI, copied and pasted, plus what they helped you achieve.
- One instance where the AI got something wrong, and how you refined your prompt or manually fixed it.
No long documents and no slide decks. We only need a live app and a concise view into how you worked with AI.

Candidate Homework Assignment Page 1 of 2

What We Will Evaluate
Evaluation area What we look for
Working application Does the app actually work? Can we submit data and see it displayed correctly?
Service integration Are the services wired correctly? The S3 -> Lambda -> DynamoDB interaction must be

sound.

Prompt quality Are the prompts precise, task-oriented, and capable of generating usable outputs?
Production thinking Consider least-privilege IAM roles, CORS handling, and basic input validation. Even if AI

wrote it, you are responsible for asking the right questions.

Clarity and honesty Is the one-pager clear and honest? We value real learning and iteration over polished stories.
Bonus Points - Optional
- Share a link to your full AI chat transcript, for example a shared ChatGPT link.
- Add update or delete functionality beyond the basic create/read operations.
Timeframe
We are not setting a hard deadline. Instead, please reply within one business day of receiving this assignment to let
us know how much time you will need and when you expect to submit.
Once you are ready, send us your working URL and the one-page AI Collaboration Snapshot. We trust you to
manage your own schedule.
Submission checklist
1. Public working URL
2. One-page AI Collaboration Snapshot, max approximately 500 words
3. Optional: full AI transcript link
4. Optional: update/delete functionality
```

*Outcome:* the agent chose a meeting-room booking scenario and built the Lambda, frontend, boto3 deploy script and least-privilege IAM, with 14 tests run against a mocked DynamoDB.

---

## Prompt 2: Prepare AWS and deploy the application

Help me configure AWS and deploy the existing Room Booker application from VS Code on Windows.

First inspect the repository, installed tools and current AWS configuration. Then guide me through the process step by step.

1. Check whether AWS CLI, Python, required packages and other project dependencies are installed.
2. Help me configure AWS authentication using the supported AWS sign-in method.
3. Verify the AWS account ID, identity, selected region and required permissions.
4. Review the deployment script and identify missing dependencies or configuration.
5. Deploy the application only after confirming that the target account and expected costs are understood.
6. Verify that the frontend, Lambda backend and DynamoDB integration work together.

Use PowerShell commands compatible with my environment. Explain what each important command does. Never ask me to paste access keys, secret keys, passwords or session tokens into chat.

Stop and explain any error before proceeding to the next stage.

---

## Prompt 3: Fix the AWS CLI command-not-found error

I ran `aws login` in the VS Code PowerShell terminal and received:

Diagnose why PowerShell cannot find the AWS CLI executable.

Please:

1. Check whether AWS CLI is installed and identify its installation path.
2. Check the current PowerShell PATH and whether VS Code inherited an outdated environment.
3. Give me the safest, shortest fix appropriate to the diagnosis.
4. If necessary, explain how to update PATH or restart VS Code.
5. Verify the fix with `aws --version` and then verify authentication with the appropriate AWS CLI identity command.

Do not reinstall AWS CLI or change system-wide configuration unless necessary. Explain whether the original `aws login` command is appropriate for the installed CLI version and authentication method.

---

## Prompt 4: AWS login is complete — diagnose deployment failures

AWS authentication is now complete.

Please resume the Room Booker deployment from the current state rather than restarting the setup.

Inspect the latest deployment output and identify the exact cause of each failure.

For any missing Python package, verify the project's dependency configuration and install the package into the correct environment.

For any AWS account, billing or subscription error:

* Identify the affected AWS service and the exact error.
* Check the account's actual activation and verification status using the available AWS tools.
* Distinguish an authentication problem from an account activation or service-access problem.
* Explain the required action and wait for confirmation before making billing-related changes.

Do not repeatedly retry a deployment that cannot succeed until the underlying issue is resolved. Preserve the existing code and configuration.

---

## Prompt 5: I have completed the AWS payment step

I have completed the requested AWS payment step. Please check whether the account and required services are now active.

1. Verify the current account status and the exact error from the previous deployment.
2. Retry the relevant read-only checks before attempting deployment again.
3. If the account remains pending verification or activation, explain the next action and what evidence would confirm readiness.
4. If the account is ready, resume deployment and test the result.

Do not assume that payment automatically activates the account. Do not run indefinite background polling or repeatedly incur charges. Report the actual state and the next step.

---

## Prompt 6: Recheck account activation and finish deployment

Please recheck AWS account activation and service access now.

If the account is verified and the required services are available:

1. Confirm the AWS identity and region.
2. Retry the deployment using the existing project configuration.
3. Resolve any remaining dependency, IAM or resource-creation errors.
4. Test the public frontend, backend API and DynamoDB read/write operations.
5. Report the deployment URL, test evidence and any remaining issues.

If activation is still pending, stop and explain what must happen next. Do not report success until the live application has passed end-to-end tests.

---

## Prompt 7: Evaluate the application against the assignment

Evaluate the current Room Booker implementation against the original assignment and the following criteria.

### Evaluation areas

* Working application: users can create and retrieve records.
* AWS integration: S3, Lambda and DynamoDB are correctly connected.
* Prompt quality: development prompts are specific, testable and effective.
* Production thinking: least-privilege IAM, CORS, input validation, error handling and operational monitoring.
* Clarity and honesty: documentation accurately reflects what was built and tested.

For each criterion:

1. Identify the relevant implementation or configuration.
2. Verify the behavior where possible.
3. Mark it as Pass, Partial or Fail.
4. Explain any evidence gaps or unresolved risks.
5. Recommend the smallest change that would improve the result.

Check whether update/delete functionality would be valuable without disturbing the working application.

Do not change production resources during this assessment. Produce a prioritized remediation plan, addressing correctness and security before visual enhancements.

---

## Prompt 8: Harden the application for production-oriented use

Improve the existing Room Booker application to a production-oriented standard while preserving its working functionality.

### Decisions already made

* No mandatory login in this phase.
* Use CloudFront for HTTPS delivery.
* Use CloudFormation for infrastructure as code.

### Architecture and security requirements

1. Host the frontend in a private S3 bucket accessible through CloudFront Origin Access Control (OAC).
2. Serve the frontend over HTTPS and configure appropriate security headers.
3. Replace any publicly accessible Lambda Function URL with a more suitable authenticated or protected API design if required by the security model.
4. Apply least-privilege IAM permissions to every resource.
5. Validate requests on the backend and implement appropriate throttling.
6. Prevent duplicate bookings and enforce booking rules atomically where concurrent requests are possible.
7. Use DynamoDB queries and indexes rather than table scans for normal application operations.
8. Configure backups, logging, monitoring and actionable alarms.
9. Define the infrastructure in a repeatable CloudFormation template.
10. Add automated tests and a deployment pipeline where proportionate.

### Implementation process

* Audit the current application and produce a prioritized change plan.
* Identify any changes that could cause downtime, data loss or additional cost.
* Implement and validate changes incrementally.
* Validate CloudFormation templates before deployment.
* Test the deployed application and security controls.
* Document rollback and cleanup procedures.

Do not claim enterprise-grade security or compliance without evidence. Explain remaining limitations and obtain approval before destructive changes or significant cost increases.

---

## Prompt 9: Confirm the agreed implementation plan

Understood. Proceed with the agreed implementation plan.

Before making further changes, summarize the selected architecture, the changes already completed and the remaining tasks.

Continue from the current repository and AWS state. Do not recreate resources unnecessarily or undo working changes. Implement the next highest-priority task, run the relevant tests and report the verified result before proceeding.

---

## Prompt 10: Check deployment progress

Please check the current deployment status and report the actual state.

Tell me:

* Which task is currently running or has completed.
* Whether any command is waiting for input.
* Whether there are errors requiring my intervention.
* Whether the AWS resources have been deployed successfully.
* What I should do next, if anything.

Do not launch duplicate deployment processes or repeat successful steps. If an operation is still running, explain what it is waiting for and whether it is safe to wait.

---

## Prompt 11: Employee login, booking limits and premium UI

Extend Room Booker with employee authentication, booking limits and a polished interface.

### Employee access

* Employees must authenticate before making employee bookings.
* Each authenticated employee may have no more than three active/upcoming bookings, according to a clearly defined booking policy.
* Enforce the limit on the backend, not just in the frontend.
* Handle simultaneous booking requests safely using DynamoDB transactions or an equivalent atomic design.
* Show a clear message when the limit has been reached.

### Visual design

* Create a premium, minimalist interface inspired by the clarity, typography, spacing and transitions of Apple products.
* Make the application responsive on desktop, tablet and mobile.
* Use polished room cards, clear availability indicators, accessible controls and subtle animations.
* Support Prudential branding using an official logo asset supplied or approved by the company. Do not recreate the logo or imply corporate endorsement without authorization.
* If the official asset is unavailable, use a neutral placeholder that can be replaced later.

### Implementation requirements

Inspect the existing code before changing the authentication model or database schema. Document migration requirements, test booking-limit enforcement under concurrency and verify that existing bookings remain accessible.

---

## Prompt 12: Guest booking, email-based access and room filtering

Extend Room Booker with the following features while preserving existing employee booking functionality.

### Access options

* Offer employees an employee sign-in option and guests a separate "Continue as Guest" option.
* Guests may create no more than one booking under the guest-booking policy.
* Employees remain subject to the three-booking limit.
* Provide a way for authenticated employees to retrieve their own bookings across devices.

### Email and identity requirements

The intended employee email domain is `@prudential.com`.

A domain check alone does not prove that someone owns an email address. Before implementing email-only access, explain this security limitation and recommend email verification through a one-time code or secure magic link. Keep guest access separate from employee identity.

If this is only a demonstration environment and trust-based email entry is retained, label it clearly as unverified and do not represent it as secure corporate authentication.

### Room data and filtering

Each room must have:

* A unique room ID and display name.
* Seating capacity.
* A list of features.
* Video-conferencing availability.
* TV/display availability.
* Booking availability for the requested date and time.

Before displaying matching rooms, allow the user to specify:

* Meeting date.
* Start and end times.
* Number of attendees.
* Whether video-conferencing equipment is required.
* Whether a TV/display is required.

Only return rooms that satisfy all selected requirements and are available for the requested time.

Enforce validation, availability and booking limits on the backend. Handle overlapping bookings, invalid dates, concurrent requests and duplicate submissions.

Add automated tests for each filter and booking rule, including boundary conditions.

---

## Prompt 13: My bookings and an immersive meeting-room background

Continue from the existing Room Booker implementation.

### My bookings

When an employee signs in, display all bookings belonging to that verified employee, including bookings created on other devices.

Add:

* An Upcoming tab.
* A Past tab.
* Booking date, time, room, attendee count and status.
* Clear empty states and loading/error messages.

Use a stable, verified user identifier as the ownership key. Do not rely on a user-entered email address alone to authorize access to booking records.

### Visual enhancement

Create an elegant meeting-room atmosphere featuring:

* A modern executive boardroom.
* Panoramic ocean views.
* A distant airplane visible through the windows.
* Subtle, smooth day/night transitions.
* A restrained, premium visual style that keeps room availability and booking controls readable.

Use optimized local assets or appropriately licensed assets. Respect reduced-motion preferences and provide a fallback for slow devices. Avoid distracting animations and excessive CPU usage.

### Verification

Test the booking history across sessions and devices. Confirm that one employee cannot view another employee's bookings. Run the existing tests and add tests for upcoming/past classification, time zones and empty states.

---

## Prompt 14: How long will the public URL remain accessible?

The deployed application is available at:

https://d3tn1rxaqj7h0y.cloudfront.net/

Inspect the actual AWS resources and account configuration to determine how long this URL is expected to remain accessible.

Check:

* Whether the CloudFront distribution is deployed and enabled.
* Whether its origin and certificate configuration are valid.
* Whether the AWS account and relevant services remain active.
* Whether any temporary credentials, scheduled deletion, resource expiration or unpaid charges could affect availability.
* Whether the domain is a default CloudFront hostname or a custom domain.

Explain which factors affect availability and whether any action is needed to keep the application online.

Do not infer permanent availability solely from the account's paid status.

---

## Prompt 15: Replace the default CloudFront hostname

I want to replace the default hostname:

https://d3tn1rxaqj7h0y.cloudfront.net/

with a professional custom domain for Room Booker.

Inspect the current deployment and propose the simplest supported approach using a domain I own or am authorized to use.

Explain:

1. Domain registration and DNS requirements.
2. The Route 53 configuration, if applicable.
3. ACM certificate requirements, including the AWS region required for CloudFront certificates.
4. CloudFront alternate domain name configuration.
5. HTTPS validation and DNS propagation.
6. Cost implications and rollback steps.

Do not purchase a domain, modify production DNS or incur new charges without my approval.

Do not use a company trademark or domain that I am not authorized to control. Preserve the existing CloudFront URL until the custom domain has been verified.

---

## Prompt 16: Document architecture and the complete prompt history

Inspect the entire current repository and document the actual Room Booker implementation.

### Architecture documentation

Create or update `ARCHITECTURE.md` with:

* System architecture and component responsibilities.
* A Mermaid architecture diagram.
* Frontend-to-backend request flow.
* AWS resource names and roles.
* DynamoDB table design, keys and indexes.
* Authentication and authorization flow.
* Booking rules and concurrency controls.
* CloudFront, S3 and HTTPS configuration.
* Deployment and rollback procedures.
* Monitoring, backups and known limitations.

Distinguish implemented features from proposed or unverified features. Never include credentials, tokens, personal information or other secrets.


## Prompt 17: Fix the calendar that displays only a few days

The meeting-room booking calendar is not displaying the entire calendar. Only a few days are visible.

Diagnose and fix the underlying problem in the existing Room Booker application. Do not simply reduce font sizes or apply arbitrary CSS changes to hide the issue.

### Investigation

1. Identify the calendar component and determine whether it uses a native date input, a custom calendar, a third-party library or a date-picker component.
2. Inspect its rendering logic, container dimensions, CSS overflow settings, grid layout, responsive breakpoints and date-generation logic.
3. Determine whether the missing days are caused by clipping, an incorrect grid definition, incorrect month calculations, time-zone conversion or another issue.
4. Reproduce the problem and identify the root cause before editing code.

### Expected behavior

* Display the complete month, including every date in that month.
* Correctly handle months containing four, five or six calendar weeks.
* Show weekday headings aligned with their corresponding date columns.
* Support previous-month and next-month navigation.
* Correctly handle leap years and month/year boundaries.
* Make the calendar fully usable on desktop, tablet and mobile without clipping dates.
* Keep booking availability and date-selection behavior intact.
* Clearly distinguish unavailable dates, selected dates, today's date and dates outside the current month.
* Maintain accessible keyboard navigation, focus states and readable contrast.

### Acceptance tests

* Test February in a leap year and a non-leap year.
* Test a month requiring six calendar rows.
* Test navigation from December to January and January to December.
* Test narrow mobile widths and larger desktop layouts.
* Verify that every date is visible and selectable when appropriate.
* Confirm that the selected date sent to the backend is correct and is not shifted by time-zone conversion.
* Run the existing application tests and add regression tests for the discovered issue.

Implement the smallest reliable fix, explain the root cause and list the tests that passed. Inspect the live application after deployment if access is available; otherwise, state clearly that live verification remains outstanding.

## Prompt 17: Commit this entire code to github public repo name: meeting-room-booking-aws username: dileepnsp. create pull request and setup git locally and commit the code.

## Prompt 18: Compose an email that covers below 

Submission checklist
1. Public working URL
2. One-page AI Collaboration Snapshot, max approximately 500 words
3. Optional: full AI transcript link
4. Optional: update/delete functionality

### Prompt history

Create or update `PROMPTS.md` with all development prompts in their original chronological order.

Preserve the original user prompts verbatim, including typos, and label agent questions and my answers separately. Add a second section containing the improved prompts, clearly marked as rewritten versions.

For each entry, record the actual outcome only when it can be verified from the repository, terminal history or conversation. Do not invent missing prompts or test results.

Include a final summary of the most important changes made through AI-assisted development.

Verify that both files exist and are readable after writing them.

---
