# AWS Ops Agent

Managing AWS at scale is hard. Teams spend hours jumping between consoles, chasing down idle resources, triaging security alerts, and trying to make sense of cost spikes — often across dozens of accounts. The AWS Ops Agent brings all of that into one place.

It runs eleven scanning skills in parallel across every region and account in your organization. Cost-Anomaly catches week-over-week spending spikes and flags new services before they become budget surprises. Zombie-Hunter finds the resources nobody remembers — unattached EBS volumes, unused Elastic IPs, idle EC2 instances quietly burning money. Security-Posture pulls from GuardDuty, Security Hub, and your security group configs to surface misconfigurations that could lead to a breach. Resiliency-Gaps checks all six Well-Architected pillars, including sustainability, so you know where your architecture is fragile before something breaks.

Tag-Enforcer scans EC2, RDS, S3, and Lambda for missing mandatory tags and can apply them in one click. Lifecycle-Tracker flags deprecated Lambda runtimes and end-of-life RDS engines — the kind of thing that quietly becomes a compliance risk. Health-Monitor pulls AWS Health events and Trusted Advisor checks so you're not caught off guard by scheduled maintenance. Quota-Guardian watches your service limits and warns you before a scaling event hits a wall.

The Arch-Diagram skill discovers every resource in your account — compute, databases, serverless, networking, storage, queues, CDN — and uses Amazon Bedrock to generate a visual architecture diagram from real AWS Config relationships and CloudTrail data. No manual drawing required.

For sixteen of the most common findings, there's a one-click Fix It button with a confirmation step. Restrict an open security group, delete an orphaned volume, enable RDS backups, apply missing tags — all without leaving the dashboard.

The built-in chat assistant, powered by Claude on Amazon Bedrock, knows your scan results and can walk you through what to prioritize, explain the business impact of a finding, and guide you through manual remediation steps. It references your actual resources — no made-up data.

For organizations running multiple AWS accounts, the org-wide scan assumes a cross-account role into every member account, runs all skills, and groups findings by organizational unit. You see the full picture in one view.

The whole thing deploys as a single Python process — locally with one CLI command, in a Docker container, or on ECS Fargate behind an ALB. No infrastructure to manage, no build step, no external dependencies beyond pip.
