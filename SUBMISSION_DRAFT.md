# AWS Ops Agent

I built this because I kept seeing the same problem across customer engagements — teams running dozens of AWS accounts with no single place to understand their operational health. They'd have cost spikes nobody caught until the bill landed, security groups wide open for months, deprecated runtimes piling up, and untagged resources making cost allocation a nightmare. Everything lived in different consoles, different tools, different dashboards.

So I built the AWS Ops Agent. It's a web dashboard that scans your entire AWS environment and gives you a clear picture of what needs attention — across cost, security, compliance, resiliency, and operations. It runs eleven scanning skills in parallel, covers all six Well-Architected pillars, and works across every account in your organization.

Here's what it does in practice. You open the dashboard, hit Run All, and within a minute you see every cost anomaly, every zombie resource burning money, every open security group, every deprecated Lambda runtime, every untagged resource, and every service quota approaching its limit. Each finding comes with severity, context, and a recommended action. For the most common issues — things like deleting orphaned EBS volumes, restricting open security groups, enabling RDS backups, or applying missing tags — there's a one-click Fix It button that walks you through what's about to happen and asks for confirmation before executing.

I also built an AI chat assistant into the dashboard, powered by Claude on Bedrock. It knows your scan results and can help you prioritize, explain what a finding means for your business, and guide you through manual remediation steps. It references your actual resources — it won't make things up.

The architecture diagram skill is something I'm particularly proud of. It discovers every resource in your account using AWS Config and CloudTrail, then sends that data to Bedrock to generate a visual Mermaid diagram of your actual infrastructure. No manual drawing, no guessing at connections — it maps what's really there.

The whole thing runs as a single Python process. You can start it locally with one CLI command, run it in a Docker container, or deploy it on ECS Fargate behind an ALB. No infrastructure to manage, no build step, no external dependencies beyond pip.

I'd love to get a few teams to try it and give me feedback. The setup takes about five minutes — clone the repo, pip install, and run `ops-agent dashboard`. If you're interested in piloting it or have thoughts on what would make this more useful for your customers, I'd really appreciate hearing from you.
